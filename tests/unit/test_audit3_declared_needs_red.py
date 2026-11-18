"""`state --task --status declared` needs the task's authentic Red (A-13, O5).

Audit 3: a task was set `declared` with no Red record, or right after `deltafuse evidence` had
refused its Red. From `declared` Red is not taken again once the Change has left Declare (a
reopened task), so only the human's cancel got the task out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.evidence import write_stamped_evidence
from deltafuse.core.installer import install
from deltafuse.core.transitions import TransitionError, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _decomposed(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id="CHG-321", title="Declared").step_intake().step_through_decompose()


def _red(builder: MockChangeBuilder, **overrides) -> Path:
    record = {
        "schema_version": 3,
        "change": builder.change_id,
        "task": "TASK-001",
        "phase": "red",
        "timestamp": "2026-11-18T12:00:00Z",
        "command": "pytest tests/test_task-001.py",
        "exit_code": 1,
        "result": "expected-failure",
        "failure_category": "behavioral-mismatch",
        "summary": "failed as expected",
        "changed_paths": ["tests/test_task-001.py"],
        "spec_status": "unchanged",
        **overrides,
    }
    dest = builder.change_dir / "evidence" / "red" / "TASK-001.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_stamped_evidence(dest, record, builder.root_dir)
    return dest


def _declare(builder: MockChangeBuilder) -> dict:
    return set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")


def test_no_red_record_no_declared(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    with pytest.raises(TransitionError, match="no Red record") as raised:
        _declare(builder)
    assert "--phase red --task TASK-001" in str(raised.value)
    assert builder.task_status("TASK-001") == "pending"


def test_a_refused_red_is_not_a_declared_task(tmp_path: Path, repo_root: Path):
    """The record `deltafuse evidence` writes and refuses: a fixture error, not a behavioural failure."""
    builder = _decomposed(tmp_path, repo_root)
    _red(builder, failure_category="fixture-error")
    with pytest.raises(TransitionError, match="not authentic"):
        _declare(builder)
    _red(builder, result="blocked", exit_code=1)
    with pytest.raises(TransitionError, match="not authentic"):
        _declare(builder)
    assert builder.task_status("TASK-001") == "pending"


def test_a_hand_mended_red_is_not_authentic(tmp_path: Path, repo_root: Path):
    """The nearest bypass: edit the refused record until it reads authentic. The stamp tells."""
    builder = _decomposed(tmp_path, repo_root)
    dest = _red(builder, failure_category="fixture-error")
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    data["failure_category"] = "behavioral-mismatch"
    dest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(TransitionError, match="not authentic"):
        _declare(builder)


def test_an_authentic_red_declares(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    _red(builder)
    assert _declare(builder)["to"] == "declared"


def test_an_already_green_red_the_core_recorded_declares(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root)
    _red(builder, exit_code=0, result="already-green", failure_category=None)
    assert _declare(builder)["to"] == "declared"
