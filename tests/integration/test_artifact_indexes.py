"""Integration tests for Change scaffolding, derived coverage, and child indexing (AW-14).

Validates schema-compliant scaffolding, Core-derived coverage serialization,
and explicit atomic child-index updates.
"""

from pathlib import Path
import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.analyze import build_coverage_document, write_coverage, CoverageError
from deltafuse.core.artifact_registry import ArtifactRegistry
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change, update_change_child_index, ScaffoldError
from tests.fixtures.change_builder import MockChangeBuilder


def _init_repo(tmp_path: Path, repo_root: Path) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    return tmp_path


def test_scaffold_change_schema_valid_without_bogus_fields(tmp_path: Path, repo_root: Path):
    root = _init_repo(tmp_path, repo_root)
    change_dir = scaffold_change(root, "CHG-140", route="code", title="Valid Scaffold")

    change_yaml = change_dir / "change.yaml"
    assert change_yaml.is_file()

    data = yaml.safe_load(change_yaml.read_text(encoding="utf-8"))

    # Bogus non-schema fields must NOT exist
    assert "created" not in data
    assert data["route"] == "code"

    # Storage schema validation must pass cleanly
    registry = ArtifactRegistry()
    val_res = registry.validate_storage_schema("change", data)
    assert val_res.valid, f"Scaffolded change.yaml failed schema validation: {val_res.diagnostics}"


def test_update_change_child_index_requires_real_child_on_disk(tmp_path: Path, repo_root: Path):
    root = _init_repo(tmp_path, repo_root)
    change_dir = scaffold_change(root, "CHG-141", route="code", title="Index Update")

    # Attempting to index a nonexistent task on disk must fail
    with pytest.raises(ScaffoldError) as exc_info:
        update_change_child_index(change_dir, child_kind="task", child_id="TASK-999")
    assert "does not exist" in str(exc_info.value).lower()


def test_update_change_child_index_success(tmp_path: Path, repo_root: Path):
    root = _init_repo(tmp_path, repo_root)
    change_dir = scaffold_change(root, "CHG-142", route="code", title="Real Index Update")

    # Create real task file on disk
    task_file = change_dir / "tasks" / "TASK-001.md"
    task_content = (
        "---\n"
        "id: TASK-001\n"
        "change: CHG-142\n"
        "slice: SLICE-01\n"
        "kind: feature\n"
        "status: pending\n"
        "---\n"
        "# TASK-001: Sample Task\n"
    )
    task_file.write_text(task_content, encoding="utf-8")

    # Update child index explicitly
    update_change_child_index(change_dir, child_kind="task", child_id="TASK-001")

    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert len(data["tasks"]) == 1
    assert data["tasks"][0] == "TASK-001"

    # Create real slice file on disk and index it
    slice_file = change_dir / "slices" / "SLICE-01.md"
    slice_content = (
        "---\n"
        "id: SLICE-01\n"
        "change: CHG-142\n"
        "title: Core Slice\n"
        "status: draft\n"
        "primary_capability: auth\n"
        "---\n"
        "# SLICE-01\n"
    )
    slice_file.write_text(slice_content, encoding="utf-8")
    update_change_child_index(change_dir, child_kind="slice", child_id="SLICE-01")

    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert len(data["slices"]) == 1
    assert data["slices"][0]["id"] == "SLICE-01"
    assert data["slices"][0]["status"] == "draft"


def test_coverage_derived_serialization_validation(tmp_path: Path, repo_root: Path):
    b = MockChangeBuilder(tmp_path, change_id="CHG-143", title="Coverage Test").step_intake().step_analyze()

    dest = write_coverage(b.change_dir)
    assert dest.is_file()

    doc = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert doc["change"] == "CHG-143"
    assert "claims" in doc

    registry = ArtifactRegistry()
    val_res = registry.validate_storage_schema("coverage", doc)
    assert val_res.valid, f"Generated coverage.yaml failed schema validation: {val_res.diagnostics}"
