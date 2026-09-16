"""DF3-008: fail-closed v3 contract validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change
from tests.fixtures.change_builder import MockChangeBuilder


def test_new_changes_are_created_with_schema_version_3(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-801", route="docs")
    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert data["schema_version"] == 3


def test_unknown_or_partial_version_stops_with_exact_diagnostic(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-802", title="Future")
    builder.step_intake()
    path = builder.change_dir / "change.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["schema_version"] = 4  # a Core from the future wrote this
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    errors = validate_change_package(builder.change_dir)
    assert errors
    assert "schema_version 4" in errors[0]
    assert "no automatic conversion" in errors[0]
    # The artifact is left exactly as it was (fail-closed, never migrated).
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["schema_version"] == 4


def test_legacy_vocabulary_is_rejected_without_auto_conversion(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-803", title="Legacy")
    builder.step_intake()
    path = builder.change_dir / "change.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "schema_version: 3", "schema_version: 2"
    )
    path.write_text(text, encoding="utf-8")

    errors = validate_change_package(builder.change_dir)
    assert errors and "schema_version 2" in errors[0]


def test_check_gate_reports_version_errors_before_gate_logic(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-804", title="Gate order")
    builder.step_intake()
    path = builder.change_dir / "change.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["schema_version"] = "3.x"  # partial/unknown marker
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    errors = check_gate(builder.change_dir, "intake")
    assert any("schema_version" in e for e in errors)
