"""Invoke real Claude Code skills headlessly."""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_TIMEOUT = 3600

# Nested `claude -p` runs unattended: no human can answer a permission prompt,
# so anything not listed here deadlocks the phase rather than failing loudly.
# Deliberately narrow — the build/test toolchain and file edits, not blanket
# shell access. Widen only with a specific reason.
ALLOWED_TOOLS = [
    "Bash(npm:*)",
    "Bash(npx:*)",
    "Bash(node:*)",
    "Bash(git:*)",
    "Bash(.venv/bin/python:*)",
    "Bash(.venv/bin/pytest:*)",
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
]


class SkillUnavailable(RuntimeError):
    pass


class SkillBlocked(Exception):
    """A failure that retrying cannot fix — quota, auth, or a permission wall."""


# Retrying these just burns the remaining attempts against the same wall, and
# the run escalates having spent three times the tokens for one answer.
_NON_RETRYABLE = (
    "session limit",
    "usage limit",
    "rate limit",
    "quota",
    "credit balance",
    "authentication_error",
    "invalid api key",
    "please run /login",
)


@dataclass
class SkillResult:
    skill: str
    ok: bool
    output: str


def available_skills() -> set[str]:
    skills_dir = REPO_ROOT / ".claude" / "skills"
    if not skills_dir.is_dir():
        return set()
    return {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}


def run_skill(skill: str, prompt: str) -> SkillResult:
    if shutil.which("claude") is None:
        raise SkillUnavailable("the `claude` CLI is not on PATH")
    if skill not in available_skills():
        raise SkillUnavailable(f"skill /{skill} is not installed in .claude/skills")

    proc = subprocess.run(
        ["claude", "-p", f"/{skill} {prompt}".strip(), "--allowed-tools", *ALLOWED_TOOLS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=SKILL_TIMEOUT,
    )
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0 or not output:
        lowered = output.lower()
        for marker in _NON_RETRYABLE:
            if marker in lowered:
                raise SkillBlocked(f"/{skill}: {output.splitlines()[0][:200]}")
    return SkillResult(skill, proc.returncode == 0, output)
