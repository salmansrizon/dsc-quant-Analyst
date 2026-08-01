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


def working_tree_has_changes() -> GateResult:
    code, out = _run(["git", "status", "--porcelain"])
    changed = bool(out.strip())
    detail = out if changed else "no files changed"
    return GateResult("diff-present", changed, False, detail)


PHASE_GATES = {
    "planning": [],
    "spec": [],
    "implement": [working_tree_has_changes, backend_tests, frontend_tests, lint],
    "review": [backend_tests, frontend_tests],
    "maintain": [],
}


def run_gates(phase: str) -> tuple[bool, list[GateResult]]:
    """A phase passes only if every non-skipped gate passes.

    A skipped gate never counts as a pass — it blocks, so a missing toolchain
    surfaces as an escalation instead of silently green-lighting the phase.
    """
    results = [gate() for gate in PHASE_GATES.get(phase, [])]
    passed = all(r.passed for r in results)
    return passed, results
