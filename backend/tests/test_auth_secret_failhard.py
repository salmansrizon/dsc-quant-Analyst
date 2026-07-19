"""JWT_SECRET_KEY fail-hard on Vercel with no override (#68 security launch-blocker).

The default signing key is public in this repo's history — signed with it, a
reset or refresh token is forgeable, which is an account takeover. A subprocess
is the only way to exercise module-import-time behavior without disturbing the
already-imported backend.auth every other test relies on.
"""
import os
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_IMPORT_AUTH = "import sys; sys.path.insert(0, '.'); from backend import auth"


def _run(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", _IMPORT_AUTH], cwd=REPO_ROOT,
        capture_output=True, text=True, env=env,
    )


def test_missing_secret_on_vercel_raises_at_import():
    # An empty string is falsy just like unset — both must fail hard.
    proc = _run({"VERCEL": "1", "JWT_SECRET_KEY": ""})
    assert proc.returncode != 0
    assert "JWT_SECRET_KEY" in proc.stderr


def test_missing_secret_without_vercel_falls_back():
    proc = _run({"JWT_SECRET_KEY": "", "VERCEL": ""})
    assert proc.returncode == 0, proc.stderr


def test_secret_set_on_vercel_starts_clean():
    proc = _run({"VERCEL": "1", "JWT_SECRET_KEY": "a-real-secret"})
    assert proc.returncode == 0, proc.stderr
