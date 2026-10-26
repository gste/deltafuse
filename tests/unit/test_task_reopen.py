"""The human reopens a blocked task: its declared oracle was wrong, and Declare runs again.

ref-m01-352 (2026-10-08): the reference declared a Red test no code could pass (blocked until
t=10, still asserted blocked at t=100), found the contradiction in Implement and marked the task
blocked, as the skill says. The human's only answer was to cancel it, which dropped the task's
whole promise. `deltafuse decide <change> --task <id> --status reopened` archives the task's
evidence, returns it to `pending`, and lets that task alone be declared again while its Change
is past Declare. Leaving `blocked` stays the human's: the Worker can do neither.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core import gate_receipts
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.evidence import EvidenceRunError, run_evidence
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt

WRONG_ORACLE = "def test_penalty():\n    assert 10 > 100  # still blocked at t=100\n"
FIXED_ORACLE = "def test_penalty():\n    assert 10 < 100 and False  # fails until implemented\n"


def _decomposed(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id="CHG-180", title="Wrong oracle").step_through_decompose()


def _red(tmp_path: Path, builder: MockChangeBuilder, oracle: str):
    test_file = tmp_path / "tests" / "test_task-001.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(oracle, encoding="utf-8")
    return run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_task-001.py"],
        changed_paths=["tests/test_task-001.py"],
    )


def _blocked_in_implement(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    builder = _decomposed(tmp_path, repo_root)
    assert _red(tmp_path, builder, WRONG_ORACLE).payload["result"] == "expected-failure"
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    return builder


def test_the_worker_cannot_leave_blocked(tmp_path: Path, repo_root: Path):
    builder = _blocked_in_implement(tmp_path, repo_root)
    with pytest.raises(TransitionError, match="only the human answers that halt") as exc_info:
        set_artifact_status(builder.change_dir, status="pending", task_id="TASK-001")
    assert "--task TASK-001 --status reopened" in str(exc_info.value)
    assert builder.task_status() == "blocked"
    reason = build_work_queue(tmp_path).blocked[0].reason
    assert "--status cancelled" in reason and "--status reopened" in reason


def test_the_human_reopens_and_the_task_is_declared_again(tmp_path: Path, repo_root: Path):
    builder = _blocked_in_implement(tmp_path, repo_root)
    change = builder.change_dir

    result = apply_decision(change, status="reopened", task="TASK-001", note="t=100 contradicts a 10 s penalty")
    assert result["ok"] and result["status"] == "reopened" and result["from"] == "blocked"
    assert builder.task_status() == "pending"
    assert not (change / "evidence" / "red" / "TASK-001.yaml").exists()
    archive = change / "reopened" / "TASK-001.1"
    assert (archive / "red.yaml").is_file()
    info = yaml.safe_load((archive / "reopen.yaml").read_text(encoding="utf-8"))
    # The failed Green the block rests on goes with the Red it answered.
    assert info["archived"] == ["red.yaml", "green.yaml"] and info["note"] == "t=100 contradicts a 10 s penalty"
    assert gate_receipts.task_reopened(tmp_path, change="CHG-180", task="TASK-001")

    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "declare" and ready[0].task == "TASK-001"
    assert "human reopened it" in ready[0].reason and "reopened/TASK-001.1/" in ready[0].reason
    assert "t=100 contradicts a 10 s penalty" in ready[0].reason

    # Declare again with the Change past Declare: a new Red freezes the fixed oracle.
    assert _red(tmp_path, builder, FIXED_ORACLE).payload["result"] == "expected-failure"
    set_artifact_status(change, status="declared", task_id="TASK-001")
    ready = build_work_queue(tmp_path).ready
    assert ready and ready[0].step == "implement"
    with pytest.raises(EvidenceRunError, match="Red is not taken again"):
        _red(tmp_path, builder, FIXED_ORACLE)
    # The archive sits outside evidence/: no gate reads it as a live record.
    from deltafuse.core.fsm import check_gate

    gate_errors = check_gate(change, "implemented")
    assert gate_errors and not any("reopened" in e for e in gate_errors), gate_errors

    # A second block and reopen archives under the next number.
    record_green_attempt(change, "TASK-001")
    set_artifact_status(change, status="blocked", task_id="TASK-001")
    apply_decision(change, status="reopened", task="TASK-001")
    assert (change / "reopened" / "TASK-001.2" / "red.yaml").is_file()


def test_only_a_reopened_task_is_declared_after_declare(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    builder._core_advance("declaring")
    with pytest.raises(TransitionError, match="may not run ahead of its Change"):
        set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")


def test_reopen_needs_a_blocked_task_and_a_note_needs_reopen(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    with pytest.raises(DecideError, match="only a blocked task is reopened"):
        apply_decision(builder.change_dir, status="reopened", task="TASK-001")
    with pytest.raises(DecideError, match="--note goes only with --status reopened"):
        apply_decision(builder.change_dir, status="cancelled", task="TASK-001", note="why")
    assert builder.task_status() == "pending"
    change_yaml = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^status: decomposed$", change_yaml)


def test_the_leash_takes_the_archive_as_the_humans_write(tmp_path: Path, repo_root: Path):
    from deltafuse.core.leash import reopen_archive_path

    builder = _blocked_in_implement(tmp_path, repo_root)
    archive = "docs/changes/CHG-180/reopened/TASK-001.1/reopen.yaml"
    assert not reopen_archive_path(tmp_path, archive)  # no reopened receipt yet
    apply_decision(builder.change_dir, status="reopened", task="TASK-001")
    assert reopen_archive_path(tmp_path, archive)
    assert not reopen_archive_path(tmp_path, "docs/changes/CHG-180/reopened/TASK-001.1/notes.md")
    assert not reopen_archive_path(tmp_path, "docs/changes/CHG-180/reopened/TASK-002.1/red.yaml")
    from deltafuse.core.leash import reopened_red_path

    assert reopened_red_path(tmp_path, "docs/changes/CHG-180/evidence/red/TASK-001.yaml")
    assert not reopened_red_path(tmp_path, "docs/changes/CHG-180/evidence/red/TASK-002.yaml")
    assert not reopened_red_path(tmp_path, "docs/changes/CHG-180/evidence/green/TASK-001.yaml")


def test_reopening_restores_the_tasks_product_files_as_declaring_found_them(tmp_path: Path, repo_root: Path):
    """ref-m04-363-2 (2026-10-11): the code written in the blocked Implement stayed, the corrected
    oracle passed on it - Red already-green for a task promising a delta - and the run ended."""
    from deltafuse.core.task_snapshot import declaring_snapshot
    from deltafuse.core.transitions import advance_change

    builder = _decomposed(tmp_path, repo_root)
    product = tmp_path / "src" / "core.py"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("VALUE = 0\n", encoding="utf-8")
    assert _red(tmp_path, builder, WRONG_ORACLE).payload["result"] == "expected-failure"
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    advance_change(builder.change_dir, "declaring")
    assert declaring_snapshot(tmp_path, "CHG-180") == {
        "src/core.py": __import__("hashlib").sha256(product.read_bytes()).hexdigest()
    }

    product.write_text("VALUE = 42  # Implement's attempt\n", encoding="utf-8")
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    result = apply_decision(builder.change_dir, status="reopened", task="TASK-001")
    assert product.read_text(encoding="utf-8") == "VALUE = 0\n"
    assert "src/core.py" in result["written"]
    info = yaml.safe_load((builder.change_dir / "reopened" / "TASK-001.1" / "reopen.yaml").read_text(encoding="utf-8"))
    assert info["restored"] == ["src/core.py"]
    assert "back as the declaring gate found them (src/core.py)" in build_work_queue(tmp_path).ready[0].reason


def test_an_altered_copy_refuses_the_reopen(tmp_path: Path, repo_root: Path):
    import hashlib

    from deltafuse.core.task_snapshot import snapshot_copy
    from deltafuse.core.transitions import advance_change

    builder = _decomposed(tmp_path, repo_root)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "core.py").write_text("VALUE = 0\n", encoding="utf-8")
    _red(tmp_path, builder, WRONG_ORACLE)
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    advance_change(builder.change_dir, "declaring")
    copy = snapshot_copy(tmp_path, hashlib.sha256((tmp_path / "src" / "core.py").read_bytes()).hexdigest())
    assert copy.is_file()
    copy.write_text("VALUE = 99\n", encoding="utf-8")
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    with pytest.raises(DecideError, match="missing or altered"):
        apply_decision(builder.change_dir, status="reopened", task="TASK-001")
    assert builder.task_status() == "blocked"


def test_red_may_not_change_a_test_another_tasks_red_froze(tmp_path: Path, repo_root: Path):
    """ref-m02-366-1 (2026-10-11): TASK-003, declared again after a reopen, rewrote a test TASK-002's
    Red had frozen; two Reds froze two bodies of one test and the run went round Implement."""
    from deltafuse.core.evidence import EvidenceRunError

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-181", title="Shared test file")
        .step_intake().step_analyze().step_specify()
        .step_decompose(tasks=[{"id": "TASK-001", "slice": "SLICE-01", "depends_on": []},
                               {"id": "TASK-002", "slice": "SLICE-01", "depends_on": []}])
    )
    shared = tmp_path / "tests" / "test_shared.py"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text("def test_first():\n    assert 1 == 2\n", encoding="utf-8")
    run_evidence(builder.change_dir, phase="red", task="TASK-001",
                 argv=[sys.executable, "-m", "pytest", "tests/test_shared.py"],
                 changed_paths=["tests/test_shared.py"])

    shared.write_text(
        "def test_first():\n    assert 1 == 3  # rewritten\n\n\ndef test_second():\n    assert 2 == 3\n",
        encoding="utf-8",
    )
    with pytest.raises(EvidenceRunError, match="TASK-001's Red froze its oracle") as exc_info:
        run_evidence(builder.change_dir, phase="red", task="TASK-002",
                     argv=[sys.executable, "-m", "pytest", "tests/test_shared.py"],
                 changed_paths=["tests/test_shared.py"])
    assert "test_first changed" in str(exc_info.value)
    assert not (builder.change_dir / "evidence" / "red" / "TASK-002.yaml").exists()

    # a new test beside the frozen one is fine
    shared.write_text("def test_first():\n    assert 1 == 2\n\n\ndef test_second():\n    assert 2 == 3\n", encoding="utf-8")
    assert run_evidence(builder.change_dir, phase="red", task="TASK-002",
                        argv=[sys.executable, "-m", "pytest", "tests/test_shared.py::test_second"],
                        changed_paths=["tests/test_shared.py"]).payload["result"] == "expected-failure"


def test_a_snapshot_copy_is_named_by_content_so_a_deep_path_stays_short(tmp_path: Path, repo_root: Path):
    """Fuse-Back, Gradle J01 (2026-10-21): the copy mirrored the tree under
    `.deltafuse/snapshots/<change>/`, ~45 characters on top of a 104-character test path, and
    `git add` on Windows failed with "Filename too long". The copy is now named by its sha256."""
    from deltafuse.core.task_snapshot import record_declaring_snapshot, snapshot_copy

    deep = "src/main/java/fuseback/characterization/traffic_management/rate_limiting/TokenBucketLimiter.java"
    (tmp_path / deep).parent.mkdir(parents=True)
    (tmp_path / deep).write_text("class TokenBucketLimiter {}\n", encoding="utf-8")
    change = tmp_path / "docs" / "changes" / "CHG-001-negative-amount"
    (change / "tasks").mkdir(parents=True)
    (change / "tasks" / "TASK-001.md").write_text(
        f"---\nid: TASK-001\nstatus: declared\nallowed_paths: [{deep}]\n---\n", encoding="utf-8"
    )
    snapshot = record_declaring_snapshot(tmp_path, change, "CHG-001-negative-amount")
    copy = snapshot_copy(tmp_path, snapshot[deep])
    assert copy.read_bytes() == (tmp_path / deep).read_bytes()
    assert len(copy.relative_to(tmp_path).as_posix()) == len(".deltafuse/snapshots/") + 64
    assert not (tmp_path / ".deltafuse" / "snapshots" / "CHG-001-negative-amount").exists()


def test_a_copy_taken_by_3_3_8_in_the_mirrored_layout_is_still_restored(tmp_path: Path, repo_root: Path):
    from deltafuse.core.task_snapshot import restore_plan, snapshot_copy, snapshot_dir
    from deltafuse.core.transitions import advance_change

    builder = _decomposed(tmp_path, repo_root)
    product = tmp_path / "src" / "core.py"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("VALUE = 0\n", encoding="utf-8")
    _red(tmp_path, builder, WRONG_ORACLE)
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    advance_change(builder.change_dir, "declaring")
    data = product.read_bytes()
    copy = snapshot_copy(tmp_path, __import__("hashlib").sha256(data).hexdigest())
    legacy = snapshot_dir(tmp_path, "CHG-180") / "src" / "core.py"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(data)
    copy.unlink()
    plan, problems = restore_plan(tmp_path, "CHG-180", {"allowed_paths": ["src/core.py"]})
    assert problems == [] and plan == [("src/core.py", data)]


def test_a_reopen_counts_only_for_the_task_of_its_own_change(tmp_path: Path, repo_root: Path):
    """Codebase audit 2026-10-21: the leash looked the reopen up by task id alone, so reopening
    TASK-001 of one Change let a Red record or an archive of TASK-001 in another Change through."""
    from deltafuse.core.leash import reopen_archive_path, reopened_red_path

    builder = _blocked_in_implement(tmp_path, repo_root)
    apply_decision(builder.change_dir, status="reopened", task="TASK-001", note="wrong oracle")
    other = tmp_path / "docs" / "changes" / "CHG-181"
    other.mkdir(parents=True)
    (other / "change.yaml").write_text("id: CHG-181\nstatus: implementing\n", encoding="utf-8")

    assert reopened_red_path(tmp_path, "docs/changes/CHG-180/evidence/red/TASK-001.yaml")
    assert reopen_archive_path(tmp_path, "docs/changes/CHG-180/reopened/TASK-001.1/red.yaml")
    assert not reopened_red_path(tmp_path, "docs/changes/CHG-181/evidence/red/TASK-001.yaml")
    assert not reopen_archive_path(tmp_path, "docs/changes/CHG-181/reopened/TASK-001.1/red.yaml")
