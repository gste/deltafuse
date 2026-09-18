"""QF-010: durable wheel evidence is created only by the explicit script."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys = pytest.importorskip("sys")
sys.path.insert(0, "scripts")

import wheel_evidence  # noqa: E402
import build_qual_image  # noqa: E402


def test_release_tools_read_canonical_version_file(tmp_path):
    """Dynamic pyproject metadata must never be mistaken for a version string."""
    (tmp_path / "VERSION").write_text("4.2.1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "deltafuse"\ndynamic = ["version"]\n\n'
        '[tool.setuptools.dynamic]\nversion = {file = ["VERSION"]}\n',
        encoding="utf-8",
    )
    assert wheel_evidence._expected_stem(tmp_path) == "deltafuse-4.2.1-py3-none-any"
    assert build_qual_image.package_version(tmp_path) == "4.2.1"


def test_evidence_written_only_on_explicit_call(tmp_path, monkeypatch):
    """The explicit command builds, smokes and writes schema-valid evidence."""
    # The clean-tree guard itself is covered by test_evidence_refuses_dirty_tree;
    # here it is bypassed so the test does not depend on the developer's tree.
    monkeypatch.setattr(wheel_evidence, "tree_dirty", lambda repo: [])
    rc = wheel_evidence.main(["--output-dir", str(tmp_path)])
    assert rc == 0
    files = list(tmp_path.glob("*-build-manifest.json"))
    assert len(files) == 1
    evidence = __import__("json").loads(files[0].read_text(encoding="utf-8"))
    assert len(evidence["commit"]) == 40
    assert evidence["tree_clean"] is True
    assert len(evidence["sha256"]) == 64
    assert evidence["commands"] and all("rc" in c for c in evidence["commands"])
    wheel_evidence._validate(evidence)  # schema-valid


def test_evidence_refuses_dirty_tree(tmp_path, monkeypatch):
    """A dirty tree blocks the evidence command before anything runs."""
    monkeypatch.setattr(wheel_evidence, "tree_dirty", lambda repo: [" M src/x.py"])
    rc = wheel_evidence.main(["--output-dir", str(tmp_path)])
    assert rc == 3
    assert not list(tmp_path.glob("*-build-manifest.json"))


def test_evidence_no_silent_overwrite(tmp_path, monkeypatch):
    """An existing evidence file is never overwritten without --force."""
    monkeypatch.setattr(wheel_evidence, "tree_dirty", lambda repo: [])
    release = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
    target = tmp_path / f"deltafuse-{release}-py3-none-any-build-manifest.json"
    target.write_text('{"existing": true}\n', encoding="utf-8")
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    rc = wheel_evidence.main(["--output-dir", str(tmp_path)])
    assert rc == 1
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
