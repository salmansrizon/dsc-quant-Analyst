"""Phase gates: real commands whose exit codes decide whether a phase passed."""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_TIMEOUT = 1800


@dataclass
class GateResult:
    name: str
    passed: bool
    skipped: bool
    detail: str


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=GATE_TIMEOUT
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return proc.returncode, "\n".join(tail[-25:])


def frontend_tests() -> GateResult:
    if not (REPO_ROOT / "node_modules").is_dir():
        return GateResult("frontend-tests", False, True, "node_modules absent; run npm ci")
    code, out = _run(["npm", "run", "test:run"])
    return GateResult("frontend-tests", code == 0, False, out)


def _python() -> str | None:
    """Prefer the project venv — a bare `pytest` on PATH usually lacks the
    project's dependencies and fails at conftest import."""
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    return shutil.which("python3")


def backend_tests() -> GateResult:
    python = _python()
    if python is None:
        return GateResult("backend-tests", False, True, "no python interpreter found")
    code, out = _run([python, "-m", "pytest", "-m", "not integration", "-q"])
    if code == 5:
        return GateResult("backend-tests", False, True, "pytest not installed in venv")
    return GateResult("backend-tests", code == 0, False, out)


def lint() -> GateResult:
    if not (REPO_ROOT / "node_modules").is_dir():
        return GateResult("lint", False, True, "node_modules absent; run npm ci")
    code, out = _run(["npm", "run", "lint"])
    return GateResult("lint", code == 0, False, out)


def diff_present(baseline: str | None = None) -> GateResult:
    """Did this phase actually change anything?

    Work may be left uncommitted *or* committed by the skill itself, so both
    count. Checking only the working tree reports a false failure the moment a
    skill commits — and, worse, a false pass when it leaves stray scratch files
    behind.
    """
    _, dirty = _run(["git", "status", "--porcelain"])
    detail = dirty
    changed = bool(dirty.strip())

    if baseline:
        code, committed = _run(["git", "diff", "--stat", f"{baseline}..HEAD"])
        if code == 0 and committed.strip():
            changed = True
            detail = f"{detail}\ncommitted since {baseline[:8]}:\n{committed}".strip()

    return GateResult("diff-present", changed, False, detail or "no files changed")


PHASE_GATES = {
    "planning": [],
    "spec": [],
    "implement": [diff_present, backend_tests, frontend_tests, lint],
    "review": [backend_tests, frontend_tests],
    "maintain": [],
}

# Gates needing the phase's starting commit to judge "did anything change".
_BASELINE_GATES = {diff_present}


def run_gates(phase: str, baseline: str | None = None) -> tuple[bool, list[GateResult]]:
    """A phase passes only if every non-skipped gate passes.

    A skipped gate never counts as a pass — it blocks, so a missing toolchain
    surfaces as an escalation instead of silently green-lighting the phase.

    `baseline` is the commit HEAD pointed at when the phase started.
    """
    results = [
        gate(baseline) if gate in _BASELINE_GATES else gate()
        for gate in PHASE_GATES.get(phase, [])
    ]
    passed = all(r.passed for r in results)
    return passed, results


def current_head() -> str | None:
    code, out = _run(["git", "rev-parse", "HEAD"])
    return out.strip() if code == 0 else None
