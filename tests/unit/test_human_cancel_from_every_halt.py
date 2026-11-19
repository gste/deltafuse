"""Audit 2026-11, FL-16: the command a halt names has to work from the state that halts.

The already-green halt tells the human to cancel the task with `deltafuse decide <change>
--task <id> --status cancelled`. For a task in `declaring` - where a Worker that marked the
step started leaves it - the command exited 1: the task table had no `declaring -> cancelled`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.decide import apply_decision
from deltafuse.core.evidence import write_stamped_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TASK_STATUS_TRANSITIONS, TransitionError, advance_change, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _already_green(builder: MockChangeBuilder, task_id: str = "TASK-001") -> None:
    write_stamped_evidence(
        builder.change_dir / "evidence" / "red" / f"{task_id}.yaml",
        {
            "schema_version": 3, "change": builder.change_id, "task": task_id, "phase": "red",
            "timestamp": "2026-11-17T10:00:00Z", "command": "pytest tests/test_task-001.py", "exit_code": 0,
            "result": "already-green", "summary": "passes", "changed_paths": ["tests/test_task-001.py"],
            "spec_status": "unchanged",
        },
        builder.root_dir,
    )


@pytest.mark.parametrize("task_status", ["pending", "declaring", "declared"])
def test_the_already_green_halt_names_a_cancel_that_works(tmp_path: Path, repo_root: Path, task_status: str):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-790", title="Green").step_through_decompose()
    change = builder.change_dir
    # The already-green Red first: since audit 3 (A-13) `declared` needs the task's Red.
    _already_green(builder)
    if task_status != "pending":
        set_artifact_status(change, status=task_status, task_id="TASK-001")

    blocked = build_work_queue(tmp_path).blocked
    assert blocked and "--task TASK-001 --status cancelled" in blocked[0].reason

    result = apply_decision(change, status="cancelled", task="TASK-001")
    assert result["ok"] and result["from"] == task_status
    assert not any("TASK-001 is 'cancelled'" in e for e in check_gate(change, "declaring"))


def test_the_human_cancels_a_task_in_any_state_the_worker_can_leave_it_in(tmp_path: Path, repo_root: Path):
    """The twin: `implementing`, where the cancel hint of `deltafuse state` sends the human too.
    Every status that is not final offers the human a cancel, directly or through `blocked`."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-791", title="Impl").step_through_decompose().step_declare()
    change = builder.change_dir
    advance_change(change, "declaring")
    set_artifact_status(change, status="implementing", task_id="TASK-001")
    assert apply_decision(change, status="cancelled", task="TASK-001")["from"] == "implementing"

    for status, targets in TASK_STATUS_TRANSITIONS.items():
        assert "cancelled" in targets or "blocked" in targets, status


def test_the_worker_still_cannot_cancel(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-792", title="No").step_through_decompose()
    set_artifact_status(builder.change_dir, status="declaring", task_id="TASK-001")
    with pytest.raises(TransitionError, match="human's decision"):
        set_artifact_status(builder.change_dir, status="cancelled", task_id="TASK-001")
    meta = (builder.change_dir / "tasks" / "TASK-001.md").read_text(encoding="utf-8")
    assert yaml.safe_load(meta.split("---")[1])["status"] == "declaring"
