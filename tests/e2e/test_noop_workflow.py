"""E2E deterministic test: No-op / Bug Not-Reproduced / Unchanged Spec path."""

from pathlib import Path
import pytest
from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

def test_noop_not_reproduced_lifecycle(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-101", title="No-op Bug Investigation")

    builder.step_intake(["CR-001"])
    assert check_gate(builder.change_dir, "intake") == []

    builder.step_analyze(slices=["SLICE-01"])
    assert check_gate(builder.change_dir, "analyzed") == []

    # Specify step indicates spec is unchanged
    builder.step_specify()
    assert check_gate(builder.change_dir, "specified") == []

    # Decompose into an investigation task
    builder.step_decompose([{
        "id": "TASK-001",
        "slice": "SLICE-01",
        "depends_on": [],
    }])
    assert check_gate(builder.change_dir, "decomposed") == []

    # Target evidence: not-reproduced
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    ev_not_rep = {
        "schema_version": 2,
        "change": "CHG-101",
        "task": "TASK-001",
        "phase": "red",
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest tests/test_bug.py",
        "exit_code": 0,
        "result": "not-reproduced",
        "summary": "Bug could not be reproduced under specified test conditions",
        "changed_paths": ["tests/test_bug.py"],
        "spec_status": "unchanged",
    }
    import yaml
    (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(ev_not_rep), encoding="utf-8")
    assert check_gate(builder.change_dir, "targeting") == []
