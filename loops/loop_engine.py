#!/usr/bin/env python3
"""SDLC loop engine with two-way Telegram control (#SDLC loop).

Safety model (see scripts/telegram-*.sh):
- Secrets come only from the environment (a gitignored .env), never hardcoded.
- Inbound commands are allow-listed to the owner chat AND must carry a shared
  secret, so a leaked bot token alone cannot drive the loop.
- Telegram text is only ever matched to a fixed verb set; a RUN payload is a task
  STRING handed to the skill layer, never eval'd or shelled.
- The planning->main promotion keeps a human gate: a PR is opened and the loop
  pauses until the owner merges and sends /continue.

NOTE: run_skill() is a simulation placeholder — wire it to real skill invocations
(wayfinder/tdd/code-review/...) before relying on the evidence gates.
"""
import json
import os
import sys
import time
import subprocess
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List

MAX_RETRIES = 3
BUDGET_LIMIT = 10.0
ARCH_IMPROVEMENT_INTERVAL = 3


@dataclass
class LoopState:
    iterations: int = 0
    phase: str = "planning"
    context: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    budget_used: float = 0.0
    completed_issues: int = 0
    tech_stack: Dict[str, Any] = field(default_factory=dict)
    paused: bool = False


class SDLCLoopEngine:
    def __init__(self, max_retries=MAX_RETRIES, budget_limit=BUDGET_LIMIT):
        self.max_retries = max_retries
        self.budget_limit = budget_limit
        self.state = LoopState()
        self.history: List[Dict[str, Any]] = []
        self.load_session()

    def load_session(self):
        path = "memory/session/current.json"
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.state.completed_issues = data.get("completed_issues", 0)
            self.state.phase = data.get("phase", "planning")
            self.state.context = data.get("context", "")
            self.state.tech_stack = data.get("tech_stack", {})
            self.state.paused = data.get("paused", False)

    def save_session(self):
        path = "memory/session/current.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "completed_issues": self.state.completed_issues,
                "phase": self.state.phase,
                "context": self.state.context,
                "tech_stack": self.state.tech_stack,
                "paused": self.state.paused,
                "timestamp": time.time(),
            }, f, indent=2)

    # ── Telegram control (fixed verbs only) ──────────────────────────────────
    def check_telegram_command(self) -> str:
        try:
            r = subprocess.run(["./scripts/telegram-route.sh"],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        except Exception:
            return "NONE"

    def notify(self, msg: str):
        subprocess.run(["./scripts/telegram-notify.sh", msg], check=False)

    def wait_for_command(self, expected: List[str]) -> str:
        while True:
            cmd = self.check_telegram_command()
            if cmd != "NONE" and any(cmd.startswith(e) for e in expected):
                return cmd
            time.sleep(5)

    # ── Skill layer (STUB — wire to real invocations) ────────────────────────
    def run_skill(self, skill_name: str, input_text: str) -> Dict[str, Any]:
        low = input_text.lower()
        return {"output": f"Simulated /{skill_name} output.", "evidence": {
            "tests_passed": "test pass" in low,
            "review_approved": "approve" in low,
            "spec_validated": "spec" in low,
            "architecture_healthy": "arch" in low,
            "best_practices_fetched": "best practices" in low,
        }}

    def check_phase_evidence(self, phase: str) -> bool:
        e = self.state.evidence
        if phase in ("planning", "spec"):
            return e.get("spec_validated", False)
        if phase == "implement":
            return e.get("tests_passed", False) and e.get("best_practices_fetched", False)
        if phase == "review":
            return e.get("review_approved", False)
        if phase == "maintain":
            return e.get("architecture_healthy", False)
        return False

    def should_stop(self) -> bool:
        return (self.state.paused
                or self.state.iterations >= self.max_retries
                or self.state.budget_used >= self.budget_limit
                or len(self.state.failures) >= self.max_retries)

    def create_pr(self):
        subprocess.run(["git", "push", "origin", "staging"], check=False)
        subprocess.run(["gh", "pr", "create", "--title", "Auto PR",
                        "--body", "Review and merge"], check=False)

    def run(self, initial_context: str) -> Dict[str, Any]:
        self.state.context = initial_context
        phase_order = ["planning", "spec", "implement", "review", "maintain"]
        skill_map = {
            "planning": ["wayfinder", "grill-me"],
            "spec": ["to-spec", "to-tickets"],
            "implement": ["implement", "tdd"],
            "review": ["code-review"],
            "maintain": ["improve-codebase-architecture"],
        }
        while not self.should_stop():
            self.state.iterations += 1
            print(f"\n--- Iteration {self.state.iterations} --- Phase: {self.state.phase}")

            cmd = self.check_telegram_command()
            if cmd.startswith("PAUSE"):
                self.state.paused = True
                self.save_session()
                self.notify("⏸️ Paused. Send /continue to resume.")
                return {"status": "paused"}
            if cmd.startswith("STATUS"):
                self.notify(f"Phase: {self.state.phase}, Completed: "
                            f"{self.state.completed_issues}, Failures: {len(self.state.failures)}")
            if cmd.startswith("RESET"):
                self.notify("⚠️ /reset requested. Reply '/reset <secret> CONFIRM' to wipe state.")
                if self.wait_for_command(["RESET:CONFIRM"]):
                    self.state = LoopState()
                    self.save_session()
                    self.notify("State reset.")

            if (self.state.completed_issues > 0
                    and self.state.completed_issues % ARCH_IMPROVEMENT_INTERVAL == 0):
                arch = self.run_skill("improve-codebase-architecture", self.state.context)
                if not arch["evidence"].get("architecture_healthy"):
                    self.state.context = arch["output"]
                    self.state.phase = "planning"
                    continue

            # Planning -> human-gated promotion to main.
            if self.state.phase == "planning":
                res = self.run_skill("wayfinder", self.state.context)
                if res["evidence"].get("spec_validated"):
                    self.create_pr()
                    self.notify("📬 PR opened from staging. Merge it, then send /continue.")
                    self.state.paused = True
                    self.save_session()
                    self.wait_for_command(["CONTINUE"])
                    self.state.paused = False
                    subprocess.run(["git", "checkout", "main"], check=False)
                    subprocess.run(["git", "pull"], check=False)
                    subprocess.run(["git", "checkout", "staging"], check=False)
                    subprocess.run(["git", "merge", "main"], check=False)
                self.state.phase = "spec"
                continue

            skills = skill_map.get(self.state.phase, [])
            current_input = self.state.context
            phase_success = False
            for skill in skills:
                result = self.run_skill(skill, current_input)
                self.state.evidence = result["evidence"]
                if self.check_phase_evidence(self.state.phase):
                    phase_success = True
                    self.state.context = result["output"]
                    self.history.append({"iteration": self.state.iterations,
                                         "phase": self.state.phase,
                                         "evidence": self.state.evidence})
                    idx = phase_order.index(self.state.phase)
                    if idx < len(phase_order) - 1:
                        self.state.phase = phase_order[idx + 1]
                    else:
                        self.state.completed_issues += 1
                        self.notify(f"✅ Issue completed! Total: {self.state.completed_issues}")
                        self.save_session()
                        return {"status": "success", "final_output": self.state.context,
                                "iterations": self.state.iterations,
                                "completed_issues": self.state.completed_issues}
                    break
                self.state.context = f"{current_input}\n[Feedback from /{skill}]: {result['output']}"
                self.state.failures.append(f"Phase {self.state.phase} failed at /{skill}")
                if len(skills) == 1:
                    break

            if not phase_success and self.state.phase != "maintain":
                continue
            self.state.budget_used += 0.5
            self.save_session()

        return self.escalate("Max retries or budget exceeded")

    def escalate(self, reason: str) -> Dict[str, Any]:
        report = {"status": "escalated", "reason": reason,
                  "state": asdict(self.state), "history": self.history}
        self.save_session()
        return report


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Continue the wayfinder map #84."
    engine = SDLCLoopEngine()
    print(json.dumps(engine.run(task), indent=2))
