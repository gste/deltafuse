"""Unit tests for Artifact Writer documentation and packaged asset synchronization (AW-15)."""

from pathlib import Path
import subprocess
import sys
import pytest


def test_artifact_writer_contract_docs_exist(repo_root: Path):
    en_contract = repo_root / "docs" / "contracts" / "artifact-writer.md"
    ru_contract = repo_root / "docs" / "contracts" / "artifact-writer.ru.md"

    assert en_contract.is_file(), "docs/contracts/artifact-writer.md must exist"
    assert ru_contract.is_file(), "docs/contracts/artifact-writer.ru.md must exist"

    en_text = en_contract.read_text(encoding="utf-8")
    ru_text = ru_contract.read_text(encoding="utf-8")

    for term in ("Artifact Writer", "describe", "create", "update", "validate", "update-index"):
        assert term in en_text, f"Missing term '{term}' in artifact-writer.md"
        assert term in ru_text, f"Missing term '{term}' in artifact-writer.ru.md"


def test_asset_bundle_sync_check(repo_root: Path):
    cmd = [sys.executable, str(repo_root / "scripts" / "sync_assets.py"), "--check"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
    assert res.returncode == 0, f"sync_assets.py check failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"
