#!/usr/bin/env python3
"""SDLC loop driver.

Walks planning -> spec -> implement -> review -> maintain, invoking the repo's
real Claude Code skills and advancing a phase only when that phase's gate
commands actually pass. State persists to memory/session/current.json so a run
can be resumed after an interruption.

The loop never pushes or opens a pull request. Publishing stays a human step,
consistent with this repo's GitHub Issues workflow (docs/agents/issue-tracker.md).
"""
import argparse
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from gates import current_head, run_gates
from skill_runner import SkillBlocked, SkillUnavailable, run_skill

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_PATH = REPO_ROOT / "memory" / "session" / "current.json"

PHASE_ORDER = ["planning", "spec", "implement", "review", "maintain"]
PHASE_SKILLS = {
    "planning": ["wayfinder"],
    "spec": ["to-spec", "to-tickets"],
    "implement": ["tdd", "implement"],
    "review": ["code-review"],
    "maintain": ["improve-codebase-architecture"],
}
MAX_ATTEMPTS_PER_PHASE = 3


@dataclass
class LoopState:
    task: str = ""
    phase: str = "planning"
    context: str = ""
    attempts: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)
    completed_issues: int = 0

    def attempts_for(self, phase: str) -> int:
        return self.attempts.get(phase, 0)


def load_state() -> LoopState:
    if not SESSION_PATH.exists():
        return LoopState()
    data = json.loads(SESSION_PATH.read_text())
    return LoopState(**{k: v for k, v in data.items() if k in LoopState.__annotations__})


def save_state(state: LoopState) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(state) | {"updated_at": time.time()}
    SESSION_PATH.write_text(json.dumps(payload, indent=2))


def describe(state: LoopState) -> str:
    return (
        f"task={state.task or '(none)'} phase={state.phase} "
        f"attempts={state.attempts_for(state.phase)} "
        f"completed_issues={state.completed_issues} failures={len(state.failures)}"
    )


def run_phase(state: LoopState) -> tuple[bool, str]:
    """Run every skill for the phase, then its gates. Returns (passed, report)."""
    prompt = state.context or state.task
    transcript = []
    # Pin the starting commit so the diff gate still sees work a skill commits
    # itself, not just what it leaves uncommitted.
    baseline = current_head()

    for skill in PHASE_SKILLS[state.phase]:
        try:
            result = run_skill(skill, prompt)
        except SkillUnavailable as exc:
            return False, f"cannot run /{skill}: {exc}"
        transcript.append(f"[/{skill}] {result.output}")
        if not result.ok:
            return False, "\n".join(transcript)
        prompt = result.output

    passed, gate_results = run_gates(state.phase, baseline)
    for gate in gate_results:
        status = "SKIP" if gate.skipped else ("PASS" if gate.passed else "FAIL")
        transcript.append(f"[gate:{gate.name}] {status}\n{gate.detail}")

    return passed, "\n".join(transcript)


def run(state: LoopState) -> dict:
    while True:
        if state.attempts_for(state.phase) >= MAX_ATTEMPTS_PER_PHASE:
            return escalate(state, f"phase '{state.phase}' exhausted retries")

        state.attempts[state.phase] = state.attempts_for(state.phase) + 1
        print(f"\n=== {describe(state)} ===", flush=True)

        try:
            passed, report = run_phase(state)
        except SkillBlocked as exc:
            # Not a failed attempt — the wall is outside the loop's control, so
            # spending the remaining retries on it would change nothing.
            state.context = str(exc)
            state.attempts[state.phase] = state.attempts_for(state.phase) - 1
            return escalate(state, f"blocked, not retryable: {exc}")

        state.context = report
        save_state(state)

        if not passed:
            state.failures.append(f"{state.phase}: gate not satisfied")
            print(f"--- phase '{state.phase}' did not pass, retrying ---", flush=True)
            continue

        idx = PHASE_ORDER.index(state.phase)
        if idx == len(PHASE_ORDER) - 1:
            state.completed_issues += 1
            state.phase = PHASE_ORDER[0]
            state.attempts = {}
            save_state(state)
            return {"status": "success", "completed_issues": state.completed_issues}

        state.phase = PHASE_ORDER[idx + 1]
        save_state(state)


def escalate(state: LoopState, reason: str) -> dict:
    save_state(state)
    return {"status": "escalated", "reason": reason, "state": asdict(state)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", help="what the loop should work on")
    parser.add_argument("--status", action="store_true", help="print state and exit")
    parser.add_argument("--reset", action="store_true", help="clear saved state and exit")
    parser.add_argument(
        "--phase",
        choices=PHASE_ORDER,
        help="start at this phase instead of planning (for work already specified)",
    )
    args = parser.parse_args()

    if args.reset:
        SESSION_PATH.unlink(missing_ok=True)
        print("session state cleared")
        return

    state = load_state()

    if args.status:
        print(describe(state))
        return

    if args.task:
        state.task = args.task
        state.context = ""
        state.phase = args.phase or PHASE_ORDER[0]
        state.attempts = {}
    elif not state.task:
        parser.error("no saved task to resume; pass a task description")
    elif args.phase:
        state.phase = args.phase
        state.attempts = {}

    print(json.dumps(run(state), indent=2))


if __name__ == "__main__":
    main()
