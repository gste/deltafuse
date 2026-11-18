"""The Core's per-clone bookkeeping is ignored; what it needs across clones is not (B-12).

Audit 3: `.deltafuse/tmp/*.json` (the Worker's Writer inputs, runner reports) and
`.deltafuse/journal/tx-*.json` (the Writer's crash-recovery journal, absolute paths with the
user's name) were picked up by `git add -A`. Neither is read across clones: the journal finishes
an interrupted write in this working copy, tmp/ holds inputs and reports. The Writer's receipts
(.deltafuse/receipts/) are what the leash vouches by in every clone and CI, and stay tracked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deltafuse.core.installer import install


def _ignored(root: Path, rel: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", rel], cwd=root, check=False).returncode == 0


@pytest.mark.parametrize("rel, ignored", [
    (".deltafuse/tmp/task.json", True),
    (".deltafuse/tmp/reports/junit.xml", True),
    (".deltafuse/journal/tx-0123.json", True),
    (".deltafuse/receipts/tx-0123.json", False),
    (".deltafuse/transitions.jsonl", False),
    (".deltafuse/journal-head", False),
])
def test_the_installer_ignores_only_per_clone_bookkeeping(tmp_path: Path, repo_root: Path, rel: str, ignored: bool):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    install(target_dir=tmp_path, framework_root=repo_root)
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    assert _ignored(tmp_path, rel) is ignored
