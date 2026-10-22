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
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt


def _decomposed(tmp_path: Path, repo_root: Path, *, delta: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-140", title="Constraint already met")
        .step_through_decompose()
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
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    queue = build_work_queue(tmp_path)
    assert not queue.ready
    assert queue.blocked and "waits for the human" in queue.blocked[0].reason


def test_red_is_not_taken_again_after_declare(tmp_path: Path, repo_root: Path):
    """cls-g31s5-m02 (2026-10-05): with its Green refused in Implement, the Worker recorded
    Red for the task again three times, each accepted - re-freezing the declared oracle."""
    from deltafuse.core.evidence import EvidenceRunError

    builder = _decomposed(tmp_path, repo_root, delta="added")
    red = builder.change_dir / "evidence" / "red" / "TASK-001.yaml"
    red.parent.mkdir(parents=True, exist_ok=True)
    red.write_text("frozen: true\n", encoding="utf-8")
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: pending", "status: implemented"), encoding="utf-8")

    with pytest.raises(EvidenceRunError, match="Red is not taken again"):
        run_evidence(
            builder.change_dir, phase="red", task="TASK-001",
            argv=[sys.executable, "-c", "raise SystemExit(1)"],
        )
    assert red.read_text(encoding="utf-8") == "frozen: true\n"


def test_red_may_be_retaken_while_the_change_is_in_declare(tmp_path: Path, repo_root: Path):
    """ref-m02-340 (2026-10-05): the guard above also covered Declare, where retaking Red is
    legitimate - nothing has consumed the oracle yet - and left the reference no way out."""
    from deltafuse.core.evidence import _refuse_red_after_declare

    builder = _decomposed(tmp_path, repo_root, delta="added")
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: pending", "status: declared"), encoding="utf-8")
    change = builder.change_dir / "change.yaml"
    text = change.read_text(encoding="utf-8")
    import re as _re

    change.write_text(_re.sub(r"(?m)^status: .*$", "status: declaring", text), encoding="utf-8")
    _refuse_red_after_declare(builder.change_dir, "TASK-001")  # allowed: no raise

    change.write_text(_re.sub(r"(?m)^status: .*$", "status: implementing", text), encoding="utf-8")
    from deltafuse.core.evidence import EvidenceRunError

    with pytest.raises(EvidenceRunError, match="Red is not taken again"):
        _refuse_red_after_declare(builder.change_dir, "TASK-001")


def test_a_sibling_stub_in_a_red_record_is_inside_the_contract(tmp_path: Path, repo_root: Path):
    """ref-m02-340: TASK-002's Declare stub src/ratelimit/policy.py sat in TASK-001's and
    TASK-003's Core-computed Red changed_paths (nothing commits between tasks) and the
    declaring gate refused them; no retaken Red could drop it."""
    import yaml as _yaml
    from deltafuse.core.fsm import _validate_evidence_changed_paths_contract

    change = tmp_path / "CHG-001"
    (change / "tasks").mkdir(parents=True)
    (change / "tasks" / "TASK-001.md").write_text(
        "---\nid: TASK-001\nstatus: declared\nallowed_paths: [tests/test_a.py]\n---\n", encoding="utf-8")
    (change / "tasks" / "TASK-002.md").write_text(
        "---\nid: TASK-002\nstatus: declared\nallowed_paths: [src/shop/policy.py]\n---\n", encoding="utf-8")
    red = change / "evidence" / "red"
    red.mkdir(parents=True)
    (red / "TASK-001.yaml").write_text(
        _yaml.safe_dump({"task": "TASK-001", "changed_paths": ["tests/test_a.py", "src/shop/policy.py"]}),
        encoding="utf-8")
    assert _validate_evidence_changed_paths_contract(change, "red", "declare", gate="declaring") == []

    (red / "TASK-001.yaml").write_text(
        _yaml.safe_dump({"task": "TASK-001", "changed_paths": ["src/shop/core.py"]}), encoding="utf-8")
    errors = _validate_evidence_changed_paths_contract(change, "red", "declare", gate="declaring")
    assert errors and "TASK-001.yaml" in errors[0] and "src/shop/core.py" in errors[0]


def test_a_superseded_task_has_no_green_and_its_green_does_not_block_the_gate(tmp_path: Path, repo_root: Path):
    """ref-m03-346 (2026-10-07): a Green recorded for a task superseded on an already-green Red
    was accepted, then the implemented gate refused it with every task done."""
    from deltafuse.core.evidence import EvidenceRunError
    from deltafuse.core.fsm import check_gate

    builder = _decomposed(tmp_path, repo_root, delta="none")
    _already_green_red(tmp_path, builder)
    set_artifact_status(builder.change_dir, status="superseded", task_id="TASK-001")

    with pytest.raises(EvidenceRunError, match="has no Green"):
        run_evidence(builder.change_dir, phase="green", task="TASK-001",
                     argv=[sys.executable, "tests/test_task-001.py"])

    stray = builder.change_dir / "evidence" / "green" / "TASK-001.yaml"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("result: passed\nexit_code: 0\n", encoding="utf-8")
    errors = check_gate(builder.change_dir, "implemented")
    assert not any("already-green Red" in e for e in errors)


def test_coverage_carries_the_cores_evidence_summary_per_task(tmp_path: Path, repo_root: Path):
    """ref-m03-347 (2026-10-07): Verify opened every Red/Green/regression record to check what
    the Core had already checked - 25 files in one call. coverage.yaml now says it per task."""
    import yaml as _yaml
    from deltafuse.core.analyze import write_coverage

    builder = _decomposed(tmp_path, repo_root, delta="none")
    _already_green_red(tmp_path, builder)
    set_artifact_status(builder.change_dir, status="superseded", task_id="TASK-001")
    write_coverage(builder.change_dir)
    doc = _yaml.safe_load((builder.change_dir / "coverage.yaml").read_text(encoding="utf-8"))
    row = doc["task_evidence"]["TASK-001"]
    assert row["status"] == "superseded" and row["red"].startswith("already-green")
    assert row["green"] == "not owed (superseded)" and row["problems"] == []


def test_the_advice_finds_a_task_file_named_with_a_slug(tmp_path: Path, repo_root: Path):
    """Codebase audit 2026-10-21: the advice read `tasks/<id>.md` only, so for
    `TASK-001-<slug>.md` it lost requirement_delta and sent a supersedable task to the human."""
    from deltafuse.core.transitions import already_green_advice

    builder = _decomposed(tmp_path, repo_root, delta="none")
    _already_green_red(tmp_path, builder)
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.rename(task.with_name("TASK-001-penalty-window.md"))
    assert "--status superseded`" in already_green_advice(builder.change_dir, "TASK-001")


def test_the_coverage_summary_names_what_the_implemented_gate_refuses(tmp_path: Path, repo_root: Path):
    """Codebase audit 2026-10-21: task_evidence_summary promised the implemented gate's checks but
    left out a Green with no Red and a Green over an already-green Red."""
    from deltafuse.core.fsm import task_evidence_summary
    from tests.fixtures.change_builder import record_green_attempt

    builder = _decomposed(tmp_path, repo_root, delta="added")
    _already_green_red(tmp_path, builder)
    record_green_attempt(builder.change_dir, "TASK-001")
    problems = task_evidence_summary(builder.change_dir, tmp_path)["TASK-001"]["problems"]
    assert any("answers an already-green Red" in p for p in problems), problems

    (builder.change_dir / "evidence" / "red" / "TASK-001.yaml").unlink()
    problems = task_evidence_summary(builder.change_dir, tmp_path)["TASK-001"]["problems"]
    assert any("has no matching Red evidence" in p for p in problems), problems
