"""Cancelling a task is the human's decision, not the Worker's.

ref-m02-338 observation (2026-10-04): `deltafuse state --status cancelled` let the Worker
drop a pending task with no condition; only the bench's hidden suite would have noticed a
hard task quietly cancelled. The Worker marks a task it cannot do `blocked`; the human
cancels with `deltafuse decide <change-dir> --task <id> --status cancelled`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core import gate_password, gate_receipts
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt


def _decomposed(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id="CHG-160", title="Hard task")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def _status(builder: MockChangeBuilder) -> str:
    meta, _ = parse_frontmatter((builder.change_dir / "tasks" / "TASK-001.md").read_text(encoding="utf-8"))
    return str(meta.get("status"))


def test_the_worker_cannot_cancel_a_task(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    with pytest.raises(TransitionError, match="the human's decision") as exc_info:
        set_artifact_status(builder.change_dir, status="cancelled", task_id="TASK-001")
    assert "--task TASK-001 --status cancelled" in str(exc_info.value)
    assert "--status blocked" in str(exc_info.value)
    assert _status(builder) == "pending"


def test_the_human_cancels_a_blocked_task_and_the_receipt_says_so(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    assert build_work_queue(tmp_path).blocked

    result = apply_decision(builder.change_dir, status="cancelled", task="TASK-001")
    assert result["ok"] and result["gate"] == "task" and result["from"] == "blocked"
    assert _status(builder) == "cancelled"
    assert gate_receipts.has_click(tmp_path, kind="task", status="cancelled", artifact_id="TASK-001")
    assert not any(item.task == "TASK-001" for item in build_work_queue(tmp_path).blocked)


def test_decide_task_takes_only_cancelled_and_honours_the_password(tmp_path: Path, repo_root: Path, monkeypatch):
    builder = _decomposed(tmp_path, repo_root)
    with pytest.raises(DecideError, match="only --status cancelled"):
        apply_decision(builder.change_dir, status="accepted", task="TASK-001")

    monkeypatch.setattr(gate_password, "is_enabled", lambda root: True)
    with pytest.raises(DecideError, match="password"):
        apply_decision(builder.change_dir, status="cancelled", task="TASK-001")
    assert _status(builder) == "pending"
