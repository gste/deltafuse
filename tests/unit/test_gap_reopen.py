"""The human sends a Change whose Verify recorded `spec-gap` back to Analyze.

ref-m04-365-2 (2026-10-11) and Fuse-Back J03 (2026-10-09): Verify recorded `spec-gap` honestly -
Specify had left out a catalogue row, in a spec file no slice named - the `converged` gate refused
it, and no command led back: the queue chose Verify seven times and the run was stopped as stalled.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import advance_change, receipt_chain_errors, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _status(path: Path) -> str:
    if path.name == "change.yaml":
        return str(yaml.safe_load(path.read_text(encoding="utf-8")).get("status"))
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return str(meta.get("status"))


def _gap_found(tmp_path: Path, repo_root: Path, outcome: str = "spec-gap") -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-220", title="Gap")
        .step_through_decompose()
        .step_declare()
        .step_implement()
    )
    (builder.change_dir / "verification.md").write_text(
        f"# Verification\n\n- Outcome: {outcome}\n\nThe catalogue row is missing.\n", encoding="utf-8"
    )
    return builder


def test_a_recorded_gap_halts_for_the_human_instead_of_verifying_again(tmp_path: Path, repo_root: Path):
    _gap_found(tmp_path, repo_root)
    queue = build_work_queue(tmp_path)
    assert not queue.ready
    reason = queue.blocked[0].reason
    assert "Verify recorded the gap 'spec-gap'" in reason and "--gap spec-gap --status reopened" in reason


def test_a_gap_with_no_route_still_halts_and_says_so(tmp_path: Path, repo_root: Path):
    builder = _gap_found(tmp_path, repo_root, outcome="test-gap")
    assert "no route back for this gap" in build_work_queue(tmp_path).blocked[0].reason
    with pytest.raises(DecideError, match="no Core route back"):
        apply_decision(builder.change_dir, status="reopened", gap="test-gap")


def test_the_reopened_gap_walks_back_through_analyze_and_specify(tmp_path: Path, repo_root: Path):
    builder = _gap_found(tmp_path, repo_root)
    change = builder.change_dir

    result = apply_decision(change, status="reopened", gap="spec-gap", note="audit.md lacks the row")
    assert result["ok"] and result["change_status"] == "analyzing"
    assert _status(change / "change.yaml") == "analyzing"
    assert _status(change / "slices" / "SLICE-01.md") == "draft"
    assert _status(change / "tasks" / "TASK-001.md") == "declared"
    assert _status(change / "spec-delta.md") == "proposed"
    archive = change / "reopened" / "verify.1"
    assert (archive / "verification.md").is_file() and not (change / "verification.md").exists()
    assert (archive / "evidence" / "green" / "TASK-001.yaml").is_file()
    assert not (change / "evidence" / "green" / "TASK-001.yaml").exists()
    assert (change / "evidence" / "red" / "TASK-001.yaml").is_file()
    assert receipt_chain_errors(tmp_path, change) == []

    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "analyze" and ready[0].analyze_pass == "gap"
    assert "audit.md lacks the row" in ready[0].reason
    assert "docs/changes/*/slices/**" in ready[0].allowed_write
    # The gap pass closes `analyzed` itself, with advance alone - the reason and the skill agree
    # (the skill once closed the gate for `coverage` only, and the reason named check-gate).
    assert "advance --gate analyzed" in ready[0].reason and "check-gate" not in ready[0].reason
    from deltafuse.core.queue import format_item

    assert "--gate analyzed" in format_item(ready[0]) and "check-gate" not in format_item(ready[0])
    skill = (repo_root / "process" / "skills" / "analyze" / "SKILL.md").read_text(encoding="utf-8")
    assert "If `analyze_pass` is `coverage` or `gap`, close with `deltafuse advance" in skill

    advance_change(change, "analyzed")
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "specify" and ready[0].specify_pass == "slice"

    set_artifact_status(change, status="specified", slice_id="SLICE-01")
    set_artifact_status(change, status="specification-proposed", change_status=True)
    accepted = apply_decision(change, status="accepted", spec=True)
    assert accepted["ok"], accepted
    # decomposed and declaring pass on what is on disk; implemented waits for a fresh Green
    assert _status(change / "change.yaml") == "declared"
    assert receipt_chain_errors(tmp_path, change) == []
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "implement" and ready[0].task == "TASK-001"


def test_reopen_needs_the_recorded_gap(tmp_path: Path, repo_root: Path):
    builder = _gap_found(tmp_path, repo_root)
    (builder.change_dir / "verification.md").write_text("# V\n\n- Outcome: converged\n", encoding="utf-8")
    with pytest.raises(DecideError, match="records no gap"):
        apply_decision(builder.change_dir, status="reopened", gap="spec-gap")


def test_tasks_missing_goes_back_to_analyze_to_route_its_claims(tmp_path: Path, repo_root: Path):
    """2026-10-27, an owner's service: three claims routed to a slice that got no task, though the
    other slices' tasks tested them; Verify recorded tasks-missing and nothing led back."""
    builder = _gap_found(tmp_path, repo_root, outcome="tasks-missing")
    change = builder.change_dir
    assert "--gap tasks-missing --status reopened" in build_work_queue(tmp_path).blocked[0].reason

    result = apply_decision(change, status="reopened", gap="tasks-missing", note="CR-008 is tested by TASK-001")
    assert result["ok"] and result["change_status"] == "analyzing"
    assert receipt_chain_errors(tmp_path, change) == []
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "analyze" and ready[0].analyze_pass == "gap"
    assert "Route each claim the gap names" in ready[0].reason
    assert "docs/changes/*/routing.yaml" in ready[0].allowed_write


def test_tasks_missing_leaves_decompose_its_turn_for_a_slice_with_no_task(tmp_path: Path, repo_root: Path):
    """df-gates #5: after `decide --gap tasks-missing`, accepting the specification walked
    `decomposed` and `declaring` on the old tasks at once, so the task Decompose was to give the
    uncovered slice could never be declared and `next` never offered Decompose (CHANGELOG 3.3.12:
    the gap pass "leaves them for Decompose to give their slice a task")."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-221", title="Gap")
        .step_intake(claims=["CR-001", "CR-002"])
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
        .step_specify()
        .step_decompose()  # TASK-001 on SLICE-01; SLICE-02 gets no task
        .step_declare()
        .step_implement()
    )
    change = builder.change_dir
    (change / "verification.md").write_text(
        "# Verification\n\n- Outcome: tasks-missing\n\nCR-002 (SLICE-02) has no task.\n", encoding="utf-8"
    )
    apply_decision(change, status="reopened", gap="tasks-missing", note="SLICE-02 needs a task")
    advance_change(change, "analyzed")
    for slice_id in ("SLICE-01", "SLICE-02"):
        set_artifact_status(change, status="specified", slice_id=slice_id)
    set_artifact_status(change, status="specification-proposed", change_status=True)
    accepted = apply_decision(change, status="accepted", spec=True)
    assert accepted["ok"], accepted

    assert _status(change / "change.yaml") == "specified"
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "decompose" and "SLICE-02" in ready[0].reason, ready

    task = (change / "tasks" / "TASK-001.md").read_text(encoding="utf-8")
    (change / "tasks" / "TASK-002.md").write_text(
        task.replace("TASK-001", "TASK-002").replace("slice: SLICE-01", "slice: SLICE-02")
        .replace("status: declared", "status: pending"),
        encoding="utf-8",
    )
    assert advance_change(change, "decomposed")["to"] == "decomposed"
    assert receipt_chain_errors(tmp_path, change) == []
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "declare" and ready[0].task == "TASK-002", ready
    # Declare records the task's Red first: since audit 3 (A-13) `declared` needs it.
    builder._write_evidence(change / "evidence" / "red" / "TASK-002.yaml", {
        "schema_version": 3, "change": "CHG-221", "task": "TASK-002", "phase": "red",
        "timestamp": "2026-11-18T12:00:00Z", "command": "pytest tests/test_task-002.py", "exit_code": 1,
        "result": "expected-failure", "failure_category": "behavioral-mismatch", "summary": "failed",
        "changed_paths": ["tests/test_task-002.py"], "spec_status": "unchanged",
    })
    assert set_artifact_status(change, status="declared", task_id="TASK-002")["to"] == "declared"
