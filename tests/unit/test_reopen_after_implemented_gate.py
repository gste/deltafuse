"""Audit 2026-11, FL-8: a task blocked after the `implemented` gate and reopened can be declared.

With the Change at `implemented`, the human reopened a blocked task. `next` said "declare", and
`deltafuse state --task --status declared` refused: a task is declared again only while its
Change is `declared` or `implementing`. Only cancelling the task led out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.decide import apply_decision
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import (
    TransitionError,
    advance_change,
    load_receipts,
    receipt_chain_errors,
    set_artifact_status,
)
from tests.fixtures.change_builder import MockChangeBuilder, record_red


def _status(path: Path) -> str:
    if path.name == "change.yaml":
        return str(yaml.safe_load(path.read_text(encoding="utf-8")).get("status"))
    return str(parse_frontmatter(path.read_text(encoding="utf-8"))[0].get("status"))


def _blocked_after_the_gate(tmp_path: Path, repo_root: Path, cid: str) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Late").step_through_decompose()
    builder.step_declare().step_implement()
    change = builder.change_dir
    assert _status(change / "change.yaml") == "implemented"
    set_artifact_status(change, status="blocked", task_id="TASK-001", human=True)
    return change


def test_reopening_after_the_implemented_gate_returns_the_change_to_declared(tmp_path: Path, repo_root: Path):
    change = _blocked_after_the_gate(tmp_path, repo_root, "CHG-800")

    result = apply_decision(change, status="reopened", task="TASK-001", note="the oracle was wrong")
    assert result["ok"] and result["change_status"] == "declared"
    assert _status(change / "change.yaml") == "declared"
    assert _status(change / "tasks" / "TASK-001.md") == "pending"
    assert receipt_chain_errors(tmp_path, change) == []

    selected = select_next(build_work_queue(tmp_path))
    assert (selected.step, selected.task) == ("declare", "TASK-001")
    # The step `next` names can be carried out: Red again, declared again, then implemented again.
    record_red(change)
    set_artifact_status(change, status="declared", task_id="TASK-001")
    assert select_next(build_work_queue(tmp_path)).step == "implement"
    set_artifact_status(change, status="implemented", task_id="TASK-001")
    assert receipt_chain_errors(tmp_path, change) == []


def test_the_gate_already_passed_is_not_resumed_but_asked_again(tmp_path: Path, repo_root: Path):
    """The nearest bypass: the rewound status is the `from` of the journal's last transition, so
    `advance` must not read it as its own interrupted write and put `implemented` back."""
    change = _blocked_after_the_gate(tmp_path, repo_root, "CHG-801")
    apply_decision(change, status="reopened", task="TASK-001")
    transitions = [r for r in load_receipts(tmp_path, "CHG-801") if r.get("kind") == "transition"]
    assert (transitions[-1]["from"], transitions[-1]["to"]) == ("declared", "implemented")

    with pytest.raises(TransitionError, match="gate 'implemented' failed"):
        advance_change(change, "implemented")
    assert _status(change / "change.yaml") == "declared"
    with pytest.raises(TransitionError):
        advance_change(change, "converged")
    assert _status(change / "change.yaml") == "declared"


def test_reopening_before_the_gate_leaves_the_change_where_it_is(tmp_path: Path, repo_root: Path):
    """The twin path that worked: the Change is still in Implement."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-802", title="Early").step_through_decompose().step_declare()
    change = builder.change_dir
    advance_change(change, "declaring")
    set_artifact_status(change, status="blocked", task_id="TASK-001", human=True)
    result = apply_decision(change, status="reopened", task="TASK-001")
    assert result["change_status"] is None and _status(change / "change.yaml") == "declared"
    assert receipt_chain_errors(tmp_path, change) == []
