"""E2E deterministic test: Edge cases, gate rejections, and DAG cycles."""

from pathlib import Path
import pytest
from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

def test_cyclic_tasks_fail_validation(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-102", title="Cyclic Tasks")
    builder.step_intake().step_analyze().step_specify()

    # Create cyclic tasks: TASK-001 depends on TASK-002, TASK-002 depends on TASK-001
    builder.step_decompose([
        {"id": "TASK-001", "depends_on": ["TASK-002"]},
        {"id": "TASK-002", "depends_on": ["TASK-001"]},
    ])

    errors = validate_change_package(builder.change_dir)
    assert any("Task DAG cycle error" in e for e in errors)
    assert len(check_gate(builder.change_dir, "decomposed")) > 0

def test_orphan_claim_in_coverage_fails_gate(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-103", title="Orphan Claim")
    builder.step_intake(claims=["CR-001"])
    builder.step_analyze()

    # Mutate coverage.yaml to introduce orphan claim CR-999 not in request.md
    import yaml
    cov_path = builder.change_dir / "coverage.yaml"
    cov_data = yaml.safe_load(cov_path.read_text(encoding="utf-8"))
    cov_data["claims"]["CR-999"] = {"slice": "SLICE-01", "tasks": ["TASK-001"]}
    cov_path.write_text(yaml.safe_dump(cov_data), encoding="utf-8")

    errors = validate_change_package(builder.change_dir)
    assert any("CR-999" in e and "orphan" in e for e in errors)
