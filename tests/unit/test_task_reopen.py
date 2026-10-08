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
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

WRONG_ORACLE = "def test_penalty():\n    assert 10 > 100  # still blocked at t=100\n"
FIXED_ORACLE = "def test_penalty():\n    assert 10 < 100 and False  # fails until implemented\n"


def _decomposed(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id="CHG-180", title="Wrong oracle")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def _status(builder: MockChangeBuilder) -> str:
    meta, _ = parse_frontmatter((builder.change_dir / "tasks" / "TASK-001.md").read_text(encoding="utf-8"))
    return str(meta.get("status"))


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
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    return builder


def test_the_worker_cannot_leave_blocked(tmp_path: Path, repo_root: Path):
    builder = _blocked_in_implement(tmp_path, repo_root)
    with pytest.raises(TransitionError, match="only the human answers that halt") as exc_info:
        set_artifact_status(builder.change_dir, status="pending", task_id="TASK-001")
    assert "--task TASK-001 --status reopened" in str(exc_info.value)
    assert _status(builder) == "blocked"
    reason = build_work_queue(tmp_path).blocked[0].reason
    assert "--status cancelled" in reason and "--status reopened" in reason


def test_the_human_reopens_and_the_task_is_declared_again(tmp_path: Path, repo_root: Path):
    builder = _blocked_in_implement(tmp_path, repo_root)
    change = builder.change_dir

    result = apply_decision(change, status="reopened", task="TASK-001", note="t=100 contradicts a 10 s penalty")
    assert result["ok"] and result["status"] == "reopened" and result["from"] == "blocked"
    assert _status(builder) == "pending"
    assert not (change / "evidence" / "red" / "TASK-001.yaml").exists()
    archive = change / "reopened" / "TASK-001.1"
    assert (archive / "red.yaml").is_file()
    info = yaml.safe_load((archive / "reopen.yaml").read_text(encoding="utf-8"))
    assert info["archived"] == ["red.yaml"] and info["note"] == "t=100 contradicts a 10 s penalty"
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
    assert _status(builder) == "pending"
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
