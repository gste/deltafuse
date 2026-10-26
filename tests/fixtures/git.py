"""git for test repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> str:
    """Run git in `root` with a throwaway identity and no signing; a non-zero exit fails the test."""
    return subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=test", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()
