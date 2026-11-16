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
