"""A task whose Red is already-green is closed, not declared forever.

Gemma 31B shakedown cls-g31g-m02b (2026-10-04): TASK-007, "verify the architectural
constraints", wrote a test the earlier tasks had already made pass. `deltafuse evidence`
recorded `already-green` and said to "return this outcome upstream", which named no command;
`deltafuse state --status already-green` was refused; the queue selected declare TASK-007
again, and a new step's conversation no longer had the advice. Seven declare steps in a row,
then the Worker hand-edited other tasks' Red records. Owner decision 2026-10-04: a task that
changes no requirement is `superseded` (its test stays as regression); one that promises a
requirement delta halts for the human.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _decomposed(tmp_path: Path, repo_root: Path, *, delta: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-140", title="Constraint already met")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(
        task.read_text(encoding="utf-8").replace("requirement_delta: added", f"requirement_delta: {delta}"),
        encoding="utf-8",
    )
    return builder


def _already_green_red(tmp_path: Path, builder: MockChangeBuilder) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "def test_no_network_store():\n    assert 'redis' not in 'in-process'\n", encoding="utf-8"
    )
    red = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=[sys.executable, "tests/test_task-001.py"],
        changed_paths=["tests/test_task-001.py"],
    )
    assert red.payload["result"] == "already-green"


def test_a_task_already_met_is_named_by_the_queue_and_superseded(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, delta="none")
    _already_green_red(tmp_path, builder)

    item = select_next(build_work_queue(tmp_path))
    assert item is not None and item.step == "declare" and item.task == "TASK-001"
    assert "--task TASK-001 --status superseded" in item.reason  # a new step learns the way out

    set_artifact_status(builder.change_dir, status="superseded", task_id="TASK-001")
    after = select_next(build_work_queue(tmp_path))
    assert not (after is not None and after.task == "TASK-001" and after.step == "declare")


def test_superseded_needs_an_already_green_red(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, delta="none")
    with pytest.raises(TransitionError, match="only when its Red record is already-green"):
        set_artifact_status(builder.change_dir, status="superseded", task_id="TASK-001")


def test_a_task_that_promised_a_delta_halts_for_the_human(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, delta="added")
    _already_green_red(tmp_path, builder)

    with pytest.raises(TransitionError, match="the human's to settle"):
        set_artifact_status(builder.change_dir, status="superseded", task_id="TASK-001")
    queue = build_work_queue(tmp_path)
    assert not any(i.step == "declare" and i.task == "TASK-001" for i in queue.ready)
    halt = [i for i in queue.blocked if i.task == "TASK-001"]
    assert halt and "The human decides" in halt[0].reason and "--status cancelled" in halt[0].reason


def test_the_evidence_command_names_the_way_out(tmp_path: Path, repo_root: Path):
    from deltafuse.core.transitions import already_green_advice

    builder = _decomposed(tmp_path, repo_root, delta="none")
    _already_green_red(tmp_path, builder)
    advice = already_green_advice(builder.change_dir, "TASK-001")
    assert f"`deltafuse state {builder.change_dir} --task TASK-001 --status superseded`" in advice
    assert advice.startswith("Red is already-green") and "Do not proceed to Implement" in advice
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("requirement_delta: none", "requirement_delta: added"),
                    encoding="utf-8")
    assert "for the human to settle" in already_green_advice(builder.change_dir, "TASK-001")


def test_a_blocked_task_halts_the_queue_and_says_why(tmp_path: Path, repo_root: Path):
    """ref-m02-338 (2026-10-04): the reference proved its own declared oracle for TASK-004
    unsatisfiable, and with no way back to declare the queue selected implement five times.
    Owner decision: the Worker marks such a task blocked and the human settles it."""
    builder = _decomposed(tmp_path, repo_root, delta="added")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    queue = build_work_queue(tmp_path)
    assert not queue.ready
    assert queue.blocked and "waits for the human" in queue.blocked[0].reason
