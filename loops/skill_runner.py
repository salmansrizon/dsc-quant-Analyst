"""Invoke real Claude Code skills headlessly."""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_TIMEOUT = 3600


class SkillUnavailable(RuntimeError):
    pass


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
        ["claude", "-p", f"/{skill} {prompt}".strip()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=SKILL_TIMEOUT,
    )
    return SkillResult(skill, proc.returncode == 0, (proc.stdout + proc.stderr).strip())
