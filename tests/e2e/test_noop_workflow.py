"""E2E deterministic test: No-op / Bug Not-Reproduced / Unchanged Spec path."""

from pathlib import Path
import pytest
import yaml
from deltafuse.core.fsm import check_gate, validate_change_package, can_transition
from deltafuse.core.evidence import write_stamped_evidence
from deltafuse.core.installer import install
from deltafuse.core.archiver import archive_change
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

    # Transition change.yaml status to targeting
    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["status"] = "targeting"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    # Declare evidence: not-reproduced
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
    write_stamped_evidence(red_dir / "TASK-001.yaml", ev_not_rep, tmp_path)
    assert check_gate(builder.change_dir, "targeting") == []

    # Transition change to terminal not-reproduced status
    assert can_transition("targeting", "not-reproduced")
    cdata["status"] = "not-reproduced"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    # Package is valid in terminal not-reproduced state
    assert validate_change_package(builder.change_dir) == []

    # Archive the terminal package
    dest = archive_change(builder.change_dir, repo_root=tmp_path)
    assert dest.is_dir()
    assert not builder.change_dir.exists()


def test_not_reproduced_transitions_from_analyzing_and_verifying(tmp_path: Path, repo_root: Path):
    """Verify that not-reproduced is reachable directly from analyzing and verifying."""
    assert can_transition("analyzing", "not-reproduced")
    assert can_transition("targeting", "not-reproduced")
    assert can_transition("verifying", "not-reproduced")

    # Cannot transition from normalized or implemented directly without targeting/verifying
    assert not can_transition("normalized", "not-reproduced")
