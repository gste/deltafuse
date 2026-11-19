"""Audit 2026-11, FL-12 and FL-17: a Change status nobody recorded is not a state of the Change.

FL-12: with change.yaml set by hand to `converged` or `archived`, `deltafuse next` reported the
product done and nothing blocked; `blocked-on-decision` set by hand was ignored and work went on.
FL-17: with the status rewound by hand to the `from` of the journal's last transition,
`advance --gate converged` exited 0 - it had "resumed" the `declaring` transition, whatever gate
was asked for.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.archiver import ArchivalError, archive_change
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, advance_change, receipt_chain_errors
from tests.fixtures.change_builder import MockChangeBuilder


def _declared(tmp_path: Path, repo_root: Path, cid: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Hand").step_through_decompose().step_declare()
    advance_change(builder.change_dir, "declaring")
    return builder


def _status(change: Path) -> str:
    return str(yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"])


@pytest.mark.parametrize("status", ["converged", "archived", "blocked-on-decision"])
def test_a_hand_set_status_halts_the_queue(tmp_path: Path, repo_root: Path, status: str):
    builder = _declared(tmp_path, repo_root, "CHG-760")
    assert build_work_queue(tmp_path).ready
    builder._update_change_yaml({"status": status})

    assert receipt_chain_errors(tmp_path, builder.change_dir)
    for queue in (build_work_queue(tmp_path), build_work_queue(tmp_path, only_change=builder.change_dir)):
        assert not queue.ready
        assert queue.blocked and status in queue.blocked[0].reason, queue.blocked
    # `next` does not read as "done", and no Core command builds on the status.
    assert main(["next", str(tmp_path)]) == 1
    with pytest.raises(ArchivalError):
        archive_change(builder.change_dir, repo_root=tmp_path)
    with pytest.raises(TransitionError):
        advance_change(builder.change_dir, "implemented")


def test_a_change_the_core_converged_is_still_done(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-761", title="Done").step_through_decompose()
    builder.step_declare().step_implement().step_verify()
    queue = build_work_queue(tmp_path)
    assert not queue.ready and not queue.blocked
    assert receipt_chain_errors(tmp_path, builder.change_dir) == []


@pytest.mark.parametrize("gate", ["converged", "implemented", "decomposed"])
def test_a_rewound_status_is_not_resumed_under_another_gates_name(tmp_path: Path, repo_root: Path, gate: str, capsys):
    builder = _declared(tmp_path, repo_root, "CHG-762")
    builder._update_change_yaml({"status": "decomposed"})  # the `from` of the last transition

    with pytest.raises(TransitionError, match="gate 'declaring'"):
        advance_change(builder.change_dir, gate)
    assert _status(builder.change_dir) == "decomposed"
    assert main(["advance", str(builder.change_dir), "--gate", gate]) == 1
    assert "was not applied" in capsys.readouterr().err
    assert _status(builder.change_dir) == "decomposed"


def test_an_interrupted_advance_is_still_finished_by_its_own_gate(tmp_path: Path, repo_root: Path):
    """The crash window the resume exists for: receipt written, change.yaml not."""
    builder = _declared(tmp_path, repo_root, "CHG-763")
    builder._update_change_yaml({"status": "decomposed"})
    result = advance_change(builder.change_dir, "declaring")
    assert result["resumed"] and result["to"] == "declared"
    assert _status(builder.change_dir) == "declared"
    assert receipt_chain_errors(tmp_path, builder.change_dir) == []
