"""Audit 2026-11, FL-10 and FL-4 (owner decision R8): a Change that will not converge can be closed.

FL-10: past Specify no status closed a Change (`decide --close` refused every one), yet the
Change blocked `deltafuse init --force`, and docs/using.md said "explicitly close the Change".
FL-4: on the no-op path - every task superseded on an already-green Red - `next` answered
"done", `advance --gate declaring` moved the Change to `declared`, and nothing led out of it:
no Green would ever be recorded, and close was refused from `declared`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.archiver import archive_change
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.installer import _active_change_ids, install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import advance_change, receipt_chain_errors, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _status(change: Path) -> str:
    return str(yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"])


def _at(tmp_path: Path, repo_root: Path, status: str, cid: str = "CHG-780") -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Close").step_intake().step_analyze()
    if status == "analyzing":
        return builder
    builder.step_specify()
    if status == "specified":
        return builder
    builder.step_decompose()
    if status == "decomposed":
        return builder
    builder.step_declare()
    if status == "declared":
        advance_change(builder.change_dir, "declaring")
        return builder
    builder.step_implement()
    if status == "implemented":
        return builder
    raise AssertionError(status)


@pytest.mark.parametrize("at", ["analyzing", "specified", "decomposed", "declared", "implemented"])
@pytest.mark.parametrize("verdict", ["rejected", "superseded"])
def test_the_human_closes_a_change_from_any_status_before_converged(tmp_path: Path, repo_root: Path, at: str, verdict: str):
    builder = _at(tmp_path, repo_root, at)
    change = builder.change_dir
    assert _status(change) == at
    assert _active_change_ids(tmp_path) == ["CHG-780"]  # what blocks `init --force`

    note = "replaced by CHG-999" if verdict == "superseded" else "abandoned"
    result = apply_decision(change, status=verdict, close=True, note=note)
    assert result["ok"] and result["change_status"] == verdict and result["from"] == at
    assert receipt_chain_errors(tmp_path, change) == []
    assert _active_change_ids(tmp_path) == []
    queue = build_work_queue(tmp_path)
    assert not queue.blocked
    assert archive_change(change, repo_root=tmp_path).is_dir()


def test_the_other_verdicts_keep_their_conditions(tmp_path: Path, repo_root: Path):
    """What R8 did not open: `superseded` still names the other Change, `duplicate` is still
    Analyze's verdict, `not-reproduced` still needs its proof, and a converged Change is not
    closed as anything."""
    builder = _at(tmp_path, repo_root, "declared")
    change = builder.change_dir
    with pytest.raises(DecideError, match="other Change"):
        apply_decision(change, status="superseded", close=True, note="no longer needed")
    with pytest.raises(DecideError, match="cannot become 'duplicate'"):
        apply_decision(change, status="duplicate", close=True, note="same as CHG-999")
    with pytest.raises(DecideError, match="no Red record shows"):
        apply_decision(change, status="not-reproduced", close=True, note="it works")
    assert _status(change) == "declared"

    done =MockChangeBuilder(tmp_path, change_id="CHG-781", title="Done").step_through_decompose()
    done.step_declare().step_implement().step_verify()
    with pytest.raises(DecideError, match="cannot become 'rejected'"):
        apply_decision(done.change_dir, status="rejected", close=True, note="too late")


@pytest.mark.parametrize("close_gate_first", [False, True])
def test_the_no_op_path_halts_with_a_command_that_closes_it(tmp_path: Path, repo_root: Path, close_gate_first: bool):
    builder = _at(tmp_path, repo_root, "decomposed", cid="CHG-782")
    change = builder.change_dir
    builder.close_task("TASK-001", "superseded")  # the Core's supersede over an already-green Red

    if close_gate_first:
        # What the audit did next: the declaring gate closes, and the Change sat in `declared`.
        assert advance_change(change, "declaring")["to"] == "declared"
    queue = build_work_queue(tmp_path)
    assert not queue.ready, [item.reason for item in queue.ready]
    reason = queue.blocked[0].reason
    assert "every task is closed" in reason and "--close --status not-reproduced" in reason

    closed = apply_decision(change, status="not-reproduced", close=True, note="the behaviour already exists")
    assert closed["change_status"] == "not-reproduced"
    assert receipt_chain_errors(tmp_path, change) == []
    assert not build_work_queue(tmp_path).blocked
    assert archive_change(change, repo_root=tmp_path).is_dir()


def test_superseding_the_last_task_through_the_core_reaches_the_same_halt(tmp_path: Path, repo_root: Path):
    """The path a Worker walks: `deltafuse state --status superseded`, then `next`."""
    from deltafuse.core.evidence import write_stamped_evidence
    from deltafuse.core.frontmatter import parse_frontmatter

    builder = _at(tmp_path, repo_root, "decomposed", cid="CHG-783")
    change = builder.change_dir
    task = change / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task.read_text(encoding="utf-8"))
    meta["requirement_delta"] = "none"
    task.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    write_stamped_evidence(
        change / "evidence" / "red" / "TASK-001.yaml",
        {
            "schema_version": 3, "change": "CHG-783", "task": "TASK-001", "phase": "red",
            "timestamp": "2026-11-17T10:00:00Z", "command": "pytest tests/test_task-001.py", "exit_code": 0,
            "result": "already-green", "summary": "passes", "changed_paths": ["tests/test_task-001.py"],
            "spec_status": "unchanged",
        },
        tmp_path,
    )
    set_artifact_status(change, status="superseded", task_id="TASK-001")
    queue = build_work_queue(tmp_path)
    assert not queue.ready and "every task is closed" in queue.blocked[0].reason
