"""df-gates #6: a Change closes without converging only by the human's recorded verdict.

No command wrote `rejected`, `duplicate`, `superseded` or `not-reproduced`: they were set by hand
in change.yaml, `archive` moved such a package with no check, and the `init --force` guard counted
it as closed. docs/state-machine.md asks a rationale, the other Change, or the proof of
not-reproduced; `deltafuse decide <change-dir> --close --status <status> --note "<why>"` records
them, and `archive`, the upgrade guard and `next` take nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core import gate_password
from deltafuse.core.archiver import ArchivalError, archive_change
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.installer import _active_change_ids, install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import receipt_chain_errors
from tests.fixtures.change_builder import MockChangeBuilder


def _status(change: Path) -> str:
    return str(yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"])


def _set_status(change: Path, status: str) -> None:
    cfile = change / "change.yaml"
    data = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    data["status"] = status
    cfile.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _analyzing(tmp_path: Path, repo_root: Path, change_id: str = "CHG-401") -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id=change_id).step_intake().step_analyze().change_dir


def test_a_hand_set_terminal_status_neither_archives_nor_lifts_the_upgrade_guard(tmp_path: Path, repo_root: Path):
    change = _analyzing(tmp_path, repo_root)
    _set_status(change, "not-reproduced")

    assert any("hand-set terminal status" in e for e in receipt_chain_errors(tmp_path, change))
    with pytest.raises(ArchivalError, match="not-reproduced"):
        archive_change(change, repo_root=tmp_path)
    assert change.is_dir()
    assert _active_change_ids(tmp_path) == ["CHG-401"]
    blocked = build_work_queue(tmp_path).blocked
    assert blocked and "decide <change-dir> --close" in blocked[0].reason


def test_the_human_closes_a_change_and_it_archives(tmp_path: Path, repo_root: Path):
    change = _analyzing(tmp_path, repo_root)

    result = apply_decision(change, status="rejected", close=True, note="Out of scope for the deposit service")
    assert result["ok"] and result["change_status"] == "rejected" and result["human_check"] == "none"
    assert _status(change) == "rejected"
    assert receipt_chain_errors(tmp_path, change) == []
    assert _active_change_ids(tmp_path) == []
    assert not build_work_queue(tmp_path).blocked

    # change.yaml edited after the verdict: no longer the human's.
    _set_status(change, "duplicate")
    assert receipt_chain_errors(tmp_path, change)
    _set_status(change, "rejected")
    assert receipt_chain_errors(tmp_path, change) == []

    dest = archive_change(change, repo_root=tmp_path)
    assert dest.is_dir() and not change.exists()


def test_closing_needs_what_the_state_machine_asks(tmp_path: Path, repo_root: Path):
    change = _analyzing(tmp_path, repo_root)
    with pytest.raises(DecideError, match="rationale"):
        apply_decision(change, status="rejected", close=True)
    with pytest.raises(DecideError, match="other Change"):
        apply_decision(change, status="duplicate", close=True, note="same as the other one")
    with pytest.raises(DecideError, match="other Change"):
        apply_decision(change, status="superseded", close=True, note="CHG-401 itself")
    with pytest.raises(DecideError, match="--close takes"):
        apply_decision(change, status="accepted", close=True, note="x")
    assert _status(change) == "analyzing"

    assert apply_decision(change, status="duplicate", close=True, note="Duplicate of CHG-007")["ok"]
    assert receipt_chain_errors(tmp_path, change) == []


def test_the_human_closes_an_analyzed_change(tmp_path: Path, repo_root: Path):
    """Owner, 2026-11-16: a Change whose specification the human rejected is back at `analyzed`
    and must be closable; the table allowed rejected/duplicate/superseded only before it."""
    for status, note in (
        ("rejected", "Spec rejected: out of scope"),
        ("duplicate", "Duplicate of CHG-007"),
        ("superseded", "Superseded by CHG-009"),
    ):
        root = tmp_path / status
        root.mkdir()
        builder = MockChangeBuilder(root, change_id="CHG-404")
        install(target_dir=root, framework_root=repo_root)
        change = builder.step_intake().step_analyze().change_dir
        builder._core_advance("analyzed")
        assert _status(change) == "analyzed"
        assert apply_decision(change, status=status, close=True, note=note)["ok"]
        assert _status(change) == status
        assert receipt_chain_errors(root, change) == []
    with pytest.raises(DecideError, match="cannot become 'not-reproduced'"):
        root = tmp_path / "nr"
        root.mkdir()
        install(target_dir=root, framework_root=repo_root)
        builder = MockChangeBuilder(root, change_id="CHG-405")
        change = builder.step_intake().step_analyze().change_dir
        builder._core_advance("analyzed")
        apply_decision(change, status="not-reproduced", close=True, note="no defect")


def test_not_reproduced_from_declare_needs_a_red_that_did_not_fail(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-402").step_through_decompose()
    change = builder.change_dir
    with pytest.raises(DecideError, match="no Red record"):
        apply_decision(change, status="not-reproduced", close=True, note="the defect does not show")
    builder.step_declare()
    red = change / "evidence" / "red" / "TASK-001.yaml"
    data = yaml.safe_load(red.read_text(encoding="utf-8"))
    data["result"] = "already-green"
    red.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert apply_decision(change, status="not-reproduced", close=True, note="Red passes on unchanged code")["ok"]
    assert _status(change) == "not-reproduced"


def test_a_verify_verdict_not_reproduced_halts_for_the_human(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-403").step_through_decompose().step_declare().step_implement()
    change = builder.change_dir
    with pytest.raises(DecideError, match="Outcome: not-reproduced"):
        apply_decision(change, status="not-reproduced", close=True, note="no-op")
    (change / "verification.md").write_text("# V\n\n- Outcome: not-reproduced\n", encoding="utf-8")
    queue = build_work_queue(tmp_path)
    assert not queue.ready and "--close --status not-reproduced" in queue.blocked[0].reason
    assert apply_decision(change, status="not-reproduced", close=True, note="no-op")["ok"]


def test_close_is_behind_the_gate_password_and_on_the_cli(tmp_path: Path, repo_root: Path, monkeypatch, capsys):
    monkeypatch.setattr(gate_password, "ITERATIONS", 1_000)
    change = _analyzing(tmp_path, repo_root)
    gate_password.set_password(tmp_path, "correct horse")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    code = main(["decide", str(change), "--close", "--status", "rejected", "--note", "out of scope"])
    assert code == 1 and "interactive terminal" in capsys.readouterr().err
    assert _status(change) == "analyzing"

    gate_password.clear_password(tmp_path, "correct horse")
    code = main(["decide", str(change), "--close", "--status", "rejected", "--note", "out of scope"])
    assert code == 0, capsys.readouterr().err
    assert _status(change) == "rejected"
