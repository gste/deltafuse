"""E2E workflow integration tests: Full lifecycle using Artifact Writer and Core commands (AW-16)."""

import json
from pathlib import Path
import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.archiver import archive_change
from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def test_e2e_artifact_writer_workflow_feature(tmp_path: Path, repo_root: Path):
    # 0. Product installation
    install(target_dir=tmp_path, framework_root=repo_root)

    # Initialize builder
    builder = MockChangeBuilder(tmp_path, change_id="CHG-165", title="E2E Artifact Writer Flow")
    change_dir = builder.change_dir
    assert change_dir.is_dir()

    # Gate 1: Intake
    builder.step_intake(["CR-001"])
    assert check_gate(change_dir, "intake") == []

    # Gate 2: Analyze & Coverage
    builder.step_analyze(slices=["SLICE-01"])
    assert check_gate(change_dir, "analyzed") == []

    # Gate 3: Specify
    builder.step_specify()
    assert check_gate(change_dir, "specified") == []

    # Gate 4: Decompose via Artifact Writer CLI 'create'
    task_payload = {
        "identity": "TASK-001",
        "title": "Implement feature task",
        "kind": "feature",
        "depends_on": [],
        "requirement_delta": "none",
        "spec_refs": ["docs/spec/core.md#REQ-01"],
        "allowed_paths": ["src/app.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 1000, "max_files": 5},
    }
    input_file = tmp_path / "task_input.json"
    input_file.write_text(json.dumps(task_payload), encoding="utf-8")

    res = main(["artifact", "create", "-k", "task", "-c", str(change_dir), "-i", str(input_file), "--json"])
    assert res == 0, "artifact create task failed"

    # Update change.yaml child index explicitly via CLI 'update-index'
    res = main(["artifact", "update-index", "-c", str(change_dir), "-k", "task", "-id", "TASK-001", "--json"])
    assert res == 0, "artifact update-index task failed"

    builder._core_advance("decomposed")
    assert check_gate(change_dir, "decomposed") == []

    # Gate 5: Declare (TDD Red evidence)
    builder.step_declare("TASK-001")
    assert check_gate(change_dir, "declaring") == []

    # Gate 6: Implement (TDD Green evidence)
    builder.step_implement("TASK-001")
    assert check_gate(change_dir, "implemented") == []

    # Gate 7: Converged & Verified
    builder.step_verify()
    assert check_gate(change_dir, "converged") == []
    assert validate_change_package(change_dir) == []

    # Archival
    archived_path = archive_change(change_dir, repo_root=tmp_path)
    assert archived_path.is_dir()
    assert not change_dir.exists()


def test_e2e_artifact_writer_workflow_docs_route(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)

    # Scaffold docs route Change package
    res = main(["new", str(tmp_path), "CHG-166", "--route", "docs", "--title", "Docs Update", "--json"])
    assert res == 0
    change_dir = tmp_path / "docs" / "changes" / "CHG-166"

    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert data["route"] == "docs"
    assert check_gate(change_dir, "intake") == []
