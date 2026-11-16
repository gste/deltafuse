"""Audit 2026-11-16 (df-leash): what the Artifact Writer must refuse a Worker, and must not refuse it."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.artifact_write import write_artifact
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

TASK = {
    "slice": "SLICE-01", "title": "T", "kind": "feature", "depends_on": [],
    "requirement_delta": "none", "spec_refs": ["docs/spec/core.md#REQ-01"],
    "allowed_paths": ["src/app.py"], "forbidden_paths": [],
}
ROUTING = {"route": "code", "claims": {"CR-001": {"primary_capability": "core"}}}


def _specified(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    root = tmp_path / "prod"
    root.mkdir()
    install(target_dir=root, framework_root=repo_root)
    builder = MockChangeBuilder(root, change_id="CHG-001", title="W")
    builder.step_intake().step_analyze().step_specify()
    return builder


@pytest.mark.parametrize("identity", ["../../../src/evil.yaml", "../CHG-002/routing.yaml", "../../spec/x.yaml"])
def test_a_writer_target_stays_inside_its_change(tmp_path: Path, repo_root: Path, identity: str):
    """df-leash #12: `../../../src/evil.yaml` resolved before the Change boundary check, which only looked
    at paths under docs/changes/, so the Writer created src/evil.yaml."""
    builder = _specified(tmp_path, repo_root)
    root = builder.root_dir
    other = root / "docs" / "changes" / "CHG-002"
    other.mkdir(parents=True, exist_ok=True)
    (other / "change.yaml").write_text("id: CHG-002\nstatus: normalized\n", encoding="utf-8")
    before = {p for p in root.rglob("*.yaml")}
    with pytest.raises(Exception, match="outside|escapes"):
        write_artifact(builder.change_dir, "routing", identity=identity, fields=dict(ROUTING))
    assert {p for p in root.rglob("*.yaml")} == before


def test_a_writer_update_works_on_a_crlf_checkout(tmp_path: Path, repo_root: Path):
    """df-leash #10: with core.autocrlf=true (the owner's machines) git checks a task out with CRLF, and
    every later update was refused with format_change_required."""
    from deltafuse.core.frontmatter import parse_frontmatter
    from tests.fixtures.git import git

    builder = _specified(tmp_path, repo_root)
    root = builder.root_dir
    write_artifact(builder.change_dir, "task", identity="TASK-001", fields=dict(TASK), body="P\n")
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "true")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "base")
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.unlink()
    git(root, "checkout", "--", task.relative_to(root).as_posix())
    assert b"\r\n" in task.read_bytes(), "checkout did not produce CRLF"
    write_artifact(builder.change_dir, "task", identity="TASK-001",
                   fields={"allowed_paths": ["src/app.py", "src/b.py"]})
    data = task.read_bytes()
    meta, body = parse_frontmatter(data.decode("utf-8"))
    assert meta["allowed_paths"] == ["src/app.py", "src/b.py"]
    assert "P" in body
    assert b"\r\n" not in data, "the Writer writes one line ending, LF, so the receipt digest is git's blob"


def _analyzed_change(tmp_path: Path, repo_root: Path) -> dict:
    import yaml

    builder = _specified(tmp_path, repo_root)
    meta = yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))
    meta["analysis"] = {"routing": "routing.yaml", "summary": "old"}
    return meta


@pytest.mark.parametrize("patch", [
    {"set": [{"path": "/analysis", "value": {"routing": "forged.yaml", "summary": "s"}}]},
    {"set": [{"path": "/analysis/routing", "value": "forged.yaml"}]},
    {"remove": ["/analysis"]},
])
def test_a_nested_core_owned_field_is_guarded_by_its_full_pointer(tmp_path: Path, repo_root: Path, patch: dict):
    """df-leash #17: change.descriptor.yaml makes `analysis/routing` Core-owned; the patch compared only a
    pointer's first token ('analysis') with the Core-owned names, so setting /analysis rewrote it."""
    from deltafuse.core.artifact_patch import ArtifactPatchError, apply_artifact_patch

    meta = _analyzed_change(tmp_path, repo_root)
    with pytest.raises(ArtifactPatchError, match="analysis/routing"):
        apply_artifact_patch(meta, patch, kind="change")


def test_a_sibling_of_a_nested_core_owned_field_stays_writable(tmp_path: Path, repo_root: Path):
    from deltafuse.core.artifact_patch import apply_artifact_patch

    meta = _analyzed_change(tmp_path, repo_root)
    out = apply_artifact_patch(meta, {"set": [{"path": "/analysis/summary", "value": "new"}]}, kind="change")
    assert out.updated_metadata["analysis"] == {"routing": "routing.yaml", "summary": "new"}
    same = {"set": [{"path": "/analysis", "value": {"routing": "routing.yaml", "summary": "new"}}]}
    assert apply_artifact_patch(meta, same, kind="change").updated_metadata["analysis"]["summary"] == "new"
