"""Two guards from the runs of 2026-10-06/07.

* ref-m03-345: Decompose split "write the tests" (tests only, src/** forbidden) from the task
  that changes the product, and the tests task ran first: its Red could never turn Green.
  The `decomposed` gate now refuses a delta task that may change no product file and depends
  on no task that may. Over 107 Changes of the bench runs to date it flags 5, each such a split.
* cls-g31-m03: the Worker rewrote a frozen test, Green was refused, and it marked the task
  blocked as an "oracle mismatch". Blocked is now refused while the declared oracle is changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from deltafuse.core.leash import unreachable_green_errors
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt


def _task(change: Path, tid: str, delta: str, paths: list[str], deps: list[str] | None = None) -> None:
    (change / "tasks").mkdir(parents=True, exist_ok=True)
    (change / "tasks" / f"{tid}.md").write_text(
        f"---\nid: {tid}\nstatus: pending\nrequirement_delta: {delta}\n"
        f"allowed_paths: {paths}\ndepends_on: {deps or []}\n---\n",
        encoding="utf-8",
    )


def test_a_tests_only_delta_task_first_in_line_is_refused(tmp_path: Path):
    change = tmp_path / "CHG-001"
    _task(change, "TASK-001", "added", ["tests/test_stats.py"])
    _task(change, "TASK-002", "added", ["src/stats.py"], deps=["TASK-001"])
    errors = unreachable_green_errors(change)
    assert len(errors) == 1 and errors[0].startswith("Task TASK-001 promises requirement_delta 'added'")


def test_a_tests_only_task_after_the_product_task_or_without_a_delta_is_fine(tmp_path: Path):
    change = tmp_path / "CHG-001"
    _task(change, "TASK-001", "added", ["src/stats.py"])
    _task(change, "TASK-002", "added", ["tests/test_stats.py"], deps=["TASK-001"])
    _task(change, "TASK-003", "none", ["tests/test_regression.py"])
    assert unreachable_green_errors(change) == []


def test_blocked_is_refused_while_the_frozen_oracle_is_changed(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-170", title="Tampered oracle")
        .step_intake().step_analyze().step_specify().step_decompose()
    )
    test_file = tmp_path / "tests" / "test_task-001.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_feature():\n    assert 1 == 2\n", encoding="utf-8")
    red = run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_task-001.py"],
        changed_paths=["tests/test_task-001.py"],
    )
    assert red.payload["result"] == "expected-failure"

    test_file.write_text("def test_feature():\n    assert 1 == 1\n", encoding="utf-8")
    with pytest.raises(TransitionError, match="restore the tests as Red froze them"):
        record_green_attempt(builder.change_dir, "TASK-001")
        set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")

    test_file.write_text("def test_feature():\n    assert 1 == 2\n", encoding="utf-8")
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
