"""Audit 2026-11, FL-5: a Decision bound to a Change stops every gate, not only Analyze's.

A Decision written during Verify - `proposed`, or `accepted` by the Worker's own hand - did not
stop `converged` or `archive`: the decision checks ran at `analyzed` and `specified` only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.archiver import ArchivalError, archive_change
from deltafuse.core.decide import apply_decision
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from tests.fixtures.change_builder import MockChangeBuilder

DEC = """---
id: DEC-0001
title: Delete user data on start
kind: product
status: {status}
owner: human-owner
date: 2026-11-16
change: {change}
affects:
  capabilities: []
  spec_refs: []
supersedes: null
superseded_by: null
---

# Delete user data on start
"""


def _verified(tmp_path: Path, repo_root: Path, cid: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Dec").step_through_decompose()
    return builder.step_declare().step_implement().step_verify()


def _decision(tmp_path: Path, status: str, cid: str) -> Path:
    path = tmp_path / "docs" / "decisions" / "DEC-0001-delete.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEC.format(status=status, change=cid), encoding="utf-8")
    return path


@pytest.mark.parametrize("gate", ["decomposed", "declaring", "implemented", "converged"])
def test_a_proposed_decision_stops_the_gates_after_specify(tmp_path: Path, repo_root: Path, gate: str):
    builder = _verified(tmp_path, repo_root, "CHG-740")
    assert check_gate(builder.change_dir, gate) == []
    _decision(tmp_path, "proposed", "CHG-740")
    errors = check_gate(builder.change_dir, gate)
    assert any("blocked-on-decision" in e and "DEC-0001-delete.md" in e for e in errors), errors


def test_a_decision_accepted_by_hand_stops_converged_archive_and_the_queue(tmp_path: Path, repo_root: Path):
    """The nearest bypass of "a proposed Decision blocks": write it already accepted."""
    builder = _verified(tmp_path, repo_root, "CHG-741")
    _decision(tmp_path, "accepted", "CHG-741")
    errors = check_gate(builder.change_dir, "converged")
    assert any("accepted without deltafuse decide" in e for e in errors), errors
    with pytest.raises(ArchivalError, match="without deltafuse decide"):
        archive_change(builder.change_dir, repo_root=tmp_path)


def test_the_queue_halts_on_a_hand_accepted_decision_and_names_the_way_out(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-742", title="Dec").step_through_decompose()
    builder.step_declare().step_implement()
    assert build_work_queue(tmp_path).ready
    decision = _decision(tmp_path, "accepted", "CHG-742")

    queue = build_work_queue(tmp_path)
    assert not queue.ready
    reason = queue.blocked[0].reason
    assert "accepted without deltafuse decide" in reason and "--decision DEC-0001" in reason

    # The way out it names: the record goes back to `proposed`, and the human answers it.
    decision.write_text(DEC.format(status="proposed", change="CHG-742"), encoding="utf-8")
    assert build_work_queue(tmp_path).blocked[0].halt_kind == "decision"
    apply_decision(tmp_path, status="accepted", decision="DEC-0001")
    assert build_work_queue(tmp_path).ready
    assert check_gate(builder.change_dir, "implemented") == []
