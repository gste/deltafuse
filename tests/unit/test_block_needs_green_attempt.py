"""The Worker blocks a task only after a Green attempt against the oracle Red froze.

ref-v338-a-M01 (2026-10-20): the reference, reading the history of a reopened task, ran
`deltafuse state --status blocked` "as a probe" before writing any code. The Core accepted it and
the run halted for the human over an oracle nobody had tried.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

PYTEST = [sys.executable, "-m", "pytest", "tests/test_task-001.py"]


def _declared(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-190", title="Block after Green")
        .step_through_decompose()
    )
    test_file = tmp_path / "tests" / "test_task-001.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_feature():\n    assert 1 == 2\n", encoding="utf-8")
    red = run_evidence(
        builder.change_dir, phase="red", task="TASK-001", argv=PYTEST, changed_paths=["tests/test_task-001.py"]
    )
    assert red.payload["result"] == "expected-failure"
    return builder


def test_blocking_before_any_green_is_refused_and_names_the_green_step(tmp_path: Path, repo_root: Path):
    builder = _declared(tmp_path, repo_root)
    with pytest.raises(TransitionError, match="before a Green attempt") as refused:
        set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    assert "--phase green --task TASK-001" in str(refused.value)
    assert builder.task_status() != "blocked"


def test_a_failed_green_the_core_recorded_lets_the_worker_block(tmp_path: Path, repo_root: Path):
    builder = _declared(tmp_path, repo_root)
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=PYTEST)
    assert green.payload["result"] == "failed" and not green.authentic
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    assert builder.task_status() == "blocked"


def test_a_hand_written_or_older_green_does_not_count(tmp_path: Path, repo_root: Path):
    builder = _declared(tmp_path, repo_root)
    green_file = builder.change_dir / "evidence" / "green" / "TASK-001.yaml"
    green_file.parent.mkdir(parents=True, exist_ok=True)
    green_file.write_text(
        yaml.safe_dump({"phase": "green", "task": "TASK-001", "exit_code": 1, "result": "failed"}), encoding="utf-8"
    )
    with pytest.raises(TransitionError, match="before a Green attempt"):
        set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")

    # A Green the Core stamped, but older than the Red it would answer.
    run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=PYTEST)
    red_file = builder.change_dir / "evidence" / "red" / "TASK-001.yaml"
    red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    green = yaml.safe_load(green_file.read_text(encoding="utf-8"))
    from deltafuse.core.evidence import stamp_evidence

    red["timestamp"] = "2099-01-01T00:00:00Z"
    red = stamp_evidence({k: v for k, v in red.items() if k not in {"recorded_by", "recorded_sha256"}}, tmp_path)
    red_file.write_text(yaml.safe_dump(red, sort_keys=False), encoding="utf-8")
    assert green["timestamp"] < red["timestamp"]
    with pytest.raises(TransitionError, match="before a Green attempt"):
        set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")


def test_a_task_with_no_red_cannot_be_blocked_by_the_worker(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-191", title="No Red").step_through_decompose()
    with pytest.raises(TransitionError, match="no Red record"):
        set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
