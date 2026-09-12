"""DF3-004: Core-owned lifecycle transitions and receipts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import (
    TransitionError,
    advance_change,
    last_receipt,
    receipt_mismatch,
)
from tests.fixtures.change_builder import MockChangeBuilder

GATE = "analyzed"


def _builder(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id=change_id, title="Transitions")


def _analyze_ready(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    """Change with all Analyze artifacts, status still Worker-held 'analyzing'."""
    builder = _builder(tmp_path, repo_root, change_id)
    builder.step_intake().step_analyze()
    builder._update_change_yaml({"status": "analyzing"})
    return builder


def _read_status(change_dir: Path) -> str:
    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    return data["status"]


def _write_status(change_dir: Path, status: str) -> None:
    path = change_dir / "change.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["status"] = status
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_status_jump_normalized_to_converged_is_rejected(
    tmp_path: Path, repo_root: Path
):
    """Even with hand-crafted converged artifacts, the transition table
    rejects the jump."""
    builder = _builder(tmp_path, repo_root, "CHG-410")
    (
        builder.step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_declare()
        .step_implement()
        .step_verify()
    )
    _write_status(builder.change_dir, "normalized")

    # Either the package validation or the transition table rejects the jump.
    with pytest.raises(TransitionError, match="cannot apply|Status mismatch"):
        advance_change(builder.change_dir, "converged")


def test_advance_records_receipt_that_matches_change_status(
    tmp_path: Path, repo_root: Path
):
    builder = _analyze_ready(tmp_path, repo_root, "CHG-411")

    result = advance_change(builder.change_dir, GATE)

    assert result["ok"] is True
    assert result["from"] == "analyzing"
    assert result["to"] == "analyzed"
    assert _read_status(builder.change_dir) == "analyzed"
    last = last_receipt(tmp_path, "CHG-411")
    assert last is not None and last["receipt"] == result["receipt"]
    assert receipt_mismatch(tmp_path, builder.change_dir) is None


def test_hand_edited_status_without_receipt_halts_the_queue(
    tmp_path: Path, repo_root: Path
):
    builder = _analyze_ready(tmp_path, repo_root, "CHG-412")
    result = advance_change(builder.change_dir, GATE)
    assert result["to"] == "analyzed"

    # The Worker hand-edits its own progress: no receipt backs this status.
    _write_status(builder.change_dir, "specified")
    assert receipt_mismatch(tmp_path, builder.change_dir) is not None

    queue = build_work_queue(tmp_path)
    assert queue.blocked, "hand-edited status must halt the Change"
    blocked = queue.blocked[0]
    assert "chain" in blocked.reason or "receipt" in blocked.reason


def test_crash_between_receipt_and_status_write_is_resumable(
    tmp_path: Path, repo_root: Path
):
    """The receipt is the source of truth: a lost change.yaml write is
    completed by the next advance instead of leaving a half transition."""
    builder = _analyze_ready(tmp_path, repo_root, "CHG-413")
    first = advance_change(builder.change_dir, GATE)

    # Simulate the crash: the journal entry survived, the status write did not.
    _write_status(builder.change_dir, first["from"])

    resumed = advance_change(builder.change_dir, GATE)
    assert resumed["ok"] is True and resumed["to"] == "analyzed"
    # The same transition completes; the original receipt stays valid.
    assert resumed["receipt"] == first["receipt"]
    assert _read_status(builder.change_dir) == "analyzed"


def test_full_analyze_cycle_advances_and_hands_off_to_specify(
    tmp_path: Path, repo_root: Path
):
    builder = _analyze_ready(tmp_path, repo_root, "CHG-414")

    assert main(["advance", str(builder.change_dir), "--gate", GATE]) == 0
    assert main(["check-gate", str(builder.change_dir), "--gate", GATE]) == 0

    assert _read_status(builder.change_dir) == "analyzed"
    item = select_next(build_work_queue(tmp_path))
    assert item is not None and item.skill == "specify"

def test_hand_set_advanced_status_is_rejected_in_every_state(
    tmp_path: Path, repo_root: Path
):
    """V3-FIX-009: a hand-edited status without receipts halts `next`,
    `check-gate`, `advance` and `archive` for every advanced state."""
    hand_statuses = [
        "analyzing",
        "analyzed",
        "specification-proposed",
        "specified",
        "decomposed",
        "declaring",
        "declared",
        "implementing",
        "implemented",
        "verifying",
        "converged",
    ]
    for status in hand_statuses:
        builder = _analyze_ready(tmp_path, repo_root, f"CHG-{900 + hand_statuses.index(status)}")
        # start from a pristine normalized package
        _write_status(builder.change_dir, "normalized")
        (builder.change_dir.parent.parent.parent / ".deltafuse" / "transitions.jsonl").unlink(missing_ok=True)
        _write_status(builder.change_dir, status)

        assert receipt_mismatch(tmp_path, builder.change_dir) is not None, status
        queue = build_work_queue(tmp_path)
        assert queue.blocked, status
        with pytest.raises(TransitionError, match="chain invalid"):
            advance_change(builder.change_dir, "intake")
        assert check_gate(builder.change_dir, "intake"), status


def test_partial_receipt_chain_does_not_satisfy_advanced_status(
    tmp_path: Path, repo_root: Path
):
    """V3-FIX-009: receipts must cover the whole chain, not just the last gate."""
    builder = _analyze_ready(tmp_path, repo_root, "CHG-950")
    advance_change(builder.change_dir, GATE)  # analyzed
    _write_status(builder.change_dir, "converged")

    assert receipt_mismatch(tmp_path, builder.change_dir) is not None
    with pytest.raises(TransitionError, match="chain invalid"):
        advance_change(builder.change_dir, "converged")
    from deltafuse.core.archiver import ArchivalError, archive_change

    with pytest.raises(ArchivalError, match="transition chain invalid"):
        archive_change(builder.change_dir, repo_root=tmp_path)

def test_state_command_writes_core_owned_task_status(
    tmp_path: Path, repo_root: Path
):
    """V3-FIX-010: `deltafuse state` journals the task status write and
    rejects disallowed transitions."""
    builder = _analyze_ready(tmp_path, repo_root, "CHG-960")
    result = advance_change(builder.change_dir, GATE)
    assert result["to"] == "analyzed"
    builder.step_decompose()  # creates TASK-001, Core-advanced to decomposed

    # declare step: pending -> declared via the Core
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    text = task_file.read_text(encoding="utf-8")
    assert "status: pending" in text
    assert main(["state", str(builder.change_dir), "--task", "TASK-001", "--status", "declared"]) == 0
    assert "status: declared" in task_file.read_text(encoding="utf-8")

    # disallowed jump is rejected
    assert main(["state", str(builder.change_dir), "--task", "TASK-001", "--status", "verified"]) == 1

    # slice writes
    assert main(["state", str(builder.change_dir), "--slice", "SLICE-01", "--status", "specified"]) == 0

    # Change-level in-flight status through the Core, from analyzed
    builder2 = _analyze_ready(tmp_path, repo_root, "CHG-961")
    advance_change(builder2.change_dir, GATE)
    assert main(["state", str(builder2.change_dir), "--change", "--status", "specification-proposed"]) == 0
    assert _read_status(builder2.change_dir) == "specification-proposed"

    # receipt-backed statuses stay Core-gated
    assert main(["state", str(builder2.change_dir), "--change", "--status", "implemented"]) == 1
