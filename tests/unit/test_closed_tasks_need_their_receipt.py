"""Audit 2026-11, FL-3: a task is closed by the human's verdict or the Core's write, not by an edit.

A task whose status was set to `cancelled` or `superseded` by hand was skipped by every gate -
no Red, no Green, no regression asked of it - and the Change converged and archived without the
hard task. Only the leash under `enforce` noticed. No gate compared the status with the
`decide --task` receipt (cancelled) or the `deltafuse state` receipt and its condition, an
already-green Red on a task that changes no requirement (superseded).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.decide import apply_decision
from deltafuse.core.evidence import write_stamped_evidence
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, advance_change, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

TWO = [
    {"id": "TASK-001", "slice": "SLICE-01", "depends_on": []},
    {"id": "TASK-002", "slice": "SLICE-01", "depends_on": []},
]


def _hand_set(task_file: Path, **fields) -> None:
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta.update(fields)
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")


def _decomposed(tmp_path: Path, repo_root: Path, cid: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Two").step_intake().step_analyze().step_specify()
    return builder.step_decompose(tasks=TWO)


def _already_green_red(builder: MockChangeBuilder, task_id: str) -> None:
    write_stamped_evidence(
        builder.change_dir / "evidence" / "red" / f"{task_id}.yaml",
        {
            "schema_version": 3, "change": builder.change_id, "task": task_id, "phase": "red",
            "timestamp": "2026-11-17T10:00:00Z", "command": f"pytest tests/test_{task_id.lower()}.py",
            "exit_code": 0, "result": "already-green", "summary": "passes on unchanged code",
            "changed_paths": [f"tests/test_{task_id.lower()}.py"], "spec_status": "unchanged",
        },
        builder.root_dir,
    )


@pytest.mark.parametrize("closed", ["cancelled", "superseded"])
def test_a_task_closed_by_hand_stops_the_gates_and_the_queue(tmp_path: Path, repo_root: Path, closed: str):
    builder = _decomposed(tmp_path, repo_root, "CHG-750")
    change = builder.change_dir
    _hand_set(change / "tasks" / "TASK-002.md", status=closed)

    blocked = build_work_queue(tmp_path).blocked
    assert blocked and "TASK-002" in blocked[0].reason and closed in blocked[0].reason

    builder.step_declare("TASK-001")
    errors = check_gate(change, "declaring")
    assert any("TASK-002" in e and f"'{closed}'" in e for e in errors), errors
    with pytest.raises(TransitionError, match="TASK-002"):
        advance_change(change, "declaring")

    builder.step_implement("TASK-001")  # receipts forged past the gates: the later ones still see it
    builder.step_verify()
    _hand_set(change / "tasks" / "TASK-002.md", status=closed)
    for gate in ("implemented", "converged"):
        assert any("TASK-002" in e and f"'{closed}'" in e for e in check_gate(change, gate)), gate


def test_superseded_by_hand_over_a_real_already_green_red_is_still_not_the_cores_write(tmp_path: Path, repo_root: Path):
    """The nearest bypass: make the condition true and skip the command."""
    builder = _decomposed(tmp_path, repo_root, "CHG-751")
    change = builder.change_dir
    _hand_set(change / "tasks" / "TASK-002.md", requirement_delta="none", status="superseded")
    _already_green_red(builder, "TASK-002")
    builder.step_declare("TASK-001")
    assert any("TASK-002" in e and "deltafuse state" in e for e in check_gate(change, "declaring"))


def test_a_superseded_task_whose_red_is_no_longer_already_green_is_refused(tmp_path: Path, repo_root: Path):
    """... and the other half: the receipt is there, the condition it was given for is not."""
    builder = _decomposed(tmp_path, repo_root, "CHG-752")
    change = builder.change_dir
    _hand_set(change / "tasks" / "TASK-002.md", requirement_delta="none")
    _already_green_red(builder, "TASK-002")
    set_artifact_status(change, status="superseded", task_id="TASK-002")
    builder.step_declare("TASK-001")
    assert check_gate(change, "declaring") == []

    (change / "evidence" / "red" / "TASK-002.yaml").unlink()
    assert any("TASK-002" in e and "already-green" in e for e in check_gate(change, "declaring"))


def test_the_humans_cancel_and_the_cores_supersede_close_a_task(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-753")
    change = builder.change_dir
    apply_decision(change, status="cancelled", task="TASK-002")
    builder.step_declare("TASK-001")
    assert check_gate(change, "declaring") == []
    assert build_work_queue(tmp_path).ready


def test_a_cancel_in_another_change_does_not_vouch_for_this_one(tmp_path: Path, repo_root: Path):
    first = _decomposed(tmp_path, repo_root, "CHG-754")
    apply_decision(first.change_dir, status="cancelled", task="TASK-002")
    second = MockChangeBuilder(tmp_path, change_id="CHG-755", title="Other").step_intake().step_analyze().step_specify()
    second.step_decompose(tasks=TWO)
    _hand_set(second.change_dir / "tasks" / "TASK-002.md", status="cancelled")
    second.step_declare("TASK-001")
    assert any("TASK-002" in e for e in check_gate(second.change_dir, "declaring"))


def test_the_writer_does_not_create_a_task_already_closed(tmp_path: Path, repo_root: Path, capsys):
    """The same trick through the Artifact Writer: `status` is the Core's field."""
    builder = _decomposed(tmp_path, repo_root, "CHG-756")
    source = tmp_path / "task.json"
    source.write_text(json.dumps({"identity": "TASK-003", "fields": {
        "slice": "SLICE-01", "title": "hard", "kind": "feature", "depends_on": [], "status": "cancelled",
        "requirement_delta": "added", "spec_refs": ["docs/spec/core.md#REQ-01"], "design_ref": None,
        "allowed_paths": ["src/core.py"], "forbidden_paths": []}, "body": "hard"}), encoding="utf-8")
    assert main(["artifact", "write", "--kind", "task", "--change", str(builder.change_dir), "--input", str(source)]) != 0
    assert not (builder.change_dir / "tasks" / "TASK-003.md").exists()
