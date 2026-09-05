"""E2E deterministic test: Full Golden Workflow through all lifecycle gates."""

from pathlib import Path
import pytest
from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

def test_golden_lifecycle_flow(tmp_path: Path, repo_root: Path):
    # 0. Product installation
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-100", title="E2E Feature Flow")

    # Gate 1: Intake
    builder.step_intake(["CR-001"])
    assert check_gate(builder.change_dir, "intake") == []
    assert len(check_gate(builder.change_dir, "analyzed")) > 0

    # Gate 2: Analyzed
    builder.step_analyze(slices=["SLICE-01"])
    assert check_gate(builder.change_dir, "analyzed") == []
    assert len(check_gate(builder.change_dir, "specified")) > 0

    # Gate 3: Specified
    builder.step_specify()
    assert check_gate(builder.change_dir, "specified") == []
    assert len(check_gate(builder.change_dir, "decomposed")) > 0

    # Gate 4: Decomposed
    builder.step_decompose([{
        "id": "TASK-001",
        "slice": "SLICE-01",
        "depends_on": [],
    }])
    assert check_gate(builder.change_dir, "decomposed") == []
    assert len(check_gate(builder.change_dir, "targeting")) > 0

    # Gate 5: Targeting (TDD Red)
    builder.step_target("TASK-001")
    assert check_gate(builder.change_dir, "targeting") == []
    assert len(check_gate(builder.change_dir, "implemented")) > 0

    # Gate 6: Implemented (TDD Green + Regression)
    builder.step_implement("TASK-001")
    assert check_gate(builder.change_dir, "implemented") == []
    assert len(check_gate(builder.change_dir, "converged")) > 0

    # Gate 7: Converged & Verified
    builder.step_verify()
    assert check_gate(builder.change_dir, "converged") == []
    assert validate_change_package(builder.change_dir) == []
