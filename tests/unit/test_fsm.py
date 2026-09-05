import pytest
from pathlib import Path
import yaml
from deltafuse.core.fsm import (
    validate_change_package,
    check_gate,
    can_transition,
    VALID_CHANGE_STATUSES,
)
from deltafuse.core.archiver import is_change_id_archived
from deltafuse.core.installer import install


def test_validate_empty_directory(tmp_path: Path):
    errors = validate_change_package(tmp_path)
    assert any("Missing required change.yaml" in e for e in errors)


def test_check_gate_lifecycle(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / "docs" / "changes" / "CHG-001-test"
    change_dir.mkdir(parents=True)

    # 1. Intake state
    assert len(check_gate(change_dir, "intake")) > 0

    (change_dir / "request.md").write_text("# Request\nCR-001: Implement feature", encoding="utf-8")
    change_yaml_content = (
        "schema_version: 2\n"
        "id: CHG-001\n"
        "title: Test change\n"
        "status: normalized\n"
        "framework:\n"
        "  version: 2.0.0\n"
        "  content_hash: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        "intent: feature\n"
        "risk: low\n"
        "source:\n"
        "  request: request.md\n"
        "  intake_refs: []\n"
        "deltas: []\n"
        "slices: []\n"
        "decisions: []\n"
        "tasks: []\n"
        "verification: null\n"
    )
    (change_dir / "change.yaml").write_text(change_yaml_content, encoding="utf-8")

    assert check_gate(change_dir, "intake") == []
    assert len(check_gate(change_dir, "analyzed")) > 0


def test_fsm_canonical_statuses_and_transitions():
    assert len(VALID_CHANGE_STATUSES) == 18
    assert "specification-proposed" in VALID_CHANGE_STATUSES
    assert "blocked-on-decision" in VALID_CHANGE_STATUSES

    # Canonical transitions
    assert can_transition("normalized", "analyzing")
    assert can_transition("analyzing", "blocked-on-decision")
    assert can_transition("blocked-on-decision", "analyzing")
    assert can_transition("analyzing", "analyzed")
    assert can_transition("analyzed", "specification-proposed")
    assert can_transition("analyzed", "targeting")  # Bug path
    assert can_transition("specification-proposed", "specified")
    assert can_transition("specified", "decomposed")
    assert can_transition("decomposed", "targeting")
    assert can_transition("targeting", "target-confirmed")
    assert can_transition("target-confirmed", "implementing")
    assert can_transition("implementing", "implemented")
    assert can_transition("implemented", "verifying")
    assert can_transition("verifying", "converged")
    assert can_transition("converged", "archived")

    # Terminal transitions
    assert can_transition("normalized", "rejected")
    assert can_transition("normalized", "duplicate")
    assert can_transition("targeting", "not-reproduced")

    # Forbidden transitions
    assert not can_transition("normalized", "converged")
    assert not can_transition("decomposed", "converged")
    assert not can_transition("archived", "analyzing")
    assert not can_transition("rejected", "normalized")


def test_decision_blocking_gate(tmp_path: Path, repo_root: Path):
    """Verifies that an unresolved proposed decision blocks the analyzed/specified gate."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / "docs" / "changes" / "CHG-001-test"
    change_dir.mkdir(parents=True)
    (change_dir / "request.md").write_text("# Request\nCR-001: Implement feature", encoding="utf-8")
    (change_dir / "routing.yaml").write_text(yaml.safe_dump({"change": "CHG-001", "claims": {"CR-001": {"summary": "S", "primary_capability": "system.core", "confidence": "high"}}}), encoding="utf-8")
    (change_dir / "coverage.yaml").write_text(yaml.safe_dump({"change": "CHG-001", "claims": {"CR-001": {"slice": "SLICE-01", "status": "pending"}}}), encoding="utf-8")
    slices_dir = change_dir / "slices"
    slices_dir.mkdir(parents=True)
    (slices_dir / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-001\ntitle: S\nstatus: draft\nprimary_capability: c\nclaims: [CR-001]\n---\n# S\n",
        encoding="utf-8"
    )
    change_yaml = {
        "schema_version": 2,
        "id": "CHG-001",
        "title": "Test change",
        "status": "analyzed",
        "framework": {"version": "2.0.0", "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
        "source": {"request": "request.md"},
        "analysis": {"routing": "routing.yaml", "summary": "analysis.md"},
        "deltas": [], "slices": [{"id": "SLICE-01", "status": "draft", "file": "slices/SLICE-01.md"}],
        "decisions": [], "tasks": []
    }
    (change_dir / "change.yaml").write_text(yaml.safe_dump(change_yaml), encoding="utf-8")

    # Create a proposed decision in docs/decisions
    dec_file = tmp_path / "docs" / "decisions" / "DEC-0001-db-choice.md"
    dec_file.write_text(
        "---\n"
        "id: DEC-0001\n"
        "title: DB Choice\n"
        "kind: architecture\n"
        "status: proposed\n"
        "owner: ghost\n"
        "change: CHG-001\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision details\n",
        encoding="utf-8"
    )

    errs = check_gate(change_dir, "analyzed")
    assert any("blocked-on-decision" in e and "DEC-0001" in e for e in errs)

    # Transition decision to accepted -> gate unblocked
    dec_file.write_text(
        "---\n"
        "id: DEC-0001\n"
        "title: DB Choice\n"
        "kind: architecture\n"
        "status: accepted\n"
        "owner: human\n"
        "change: CHG-001\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision details\n",
        encoding="utf-8"
    )
    assert not any("blocked-on-decision" in e for e in check_gate(change_dir, "analyzed"))


def test_is_change_id_archived(tmp_path: Path):
    arch_dir = tmp_path / "docs" / "archive" / "changes" / "2026-09-05-CHG-999"
    arch_dir.mkdir(parents=True)
    assert is_change_id_archived("CHG-999", tmp_path)
    assert not is_change_id_archived("CHG-888", tmp_path)


def test_task_design_ref_validation(tmp_path: Path):
    from tests.fixtures.change_builder import MockChangeBuilder
    from deltafuse.core.frontmatter import parse_frontmatter

    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-005", title="Design Ref Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["design_ref"] = "docs/decisions/DEC-0005-missing.md"
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

    # 1. Nonexistent DEC file
    errs = validate_change_package(builder.change_dir)
    assert any("Referenced decision record does not exist" in e for e in errs)

    # 2. DEC file in proposed status
    dec_file = tmp_path / "docs" / "decisions" / "DEC-0005-missing.md"
    dec_file.parent.mkdir(parents=True, exist_ok=True)
    dec_file.write_text(
        "---\nid: DEC-0005\ntitle: D\nkind: architecture\nstatus: proposed\nowner: ghost\nchange: CHG-005\naffects: {capabilities: [c], spec_refs: []}\n---\n# D\n",
        encoding="utf-8"
    )
    errs = validate_change_package(builder.change_dir)
    assert any("must be 'accepted'" in e for e in errs)

    # 3. DEC file in accepted status
    dec_file.write_text(
        "---\nid: DEC-0005\ntitle: D\nkind: architecture\nstatus: accepted\nowner: ghost\nchange: CHG-005\naffects: {capabilities: [c], spec_refs: []}\n---\n# D\n",
        encoding="utf-8"
    )
    errs = validate_change_package(builder.change_dir)
    assert not any("Referenced decision" in e for e in errs)
