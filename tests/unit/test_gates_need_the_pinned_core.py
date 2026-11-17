"""Audit 2026-11, FL-11 and FW-10: gates and `next` run only on the Core the product pins.

FL-11: docs/state-machine.md promised that a product whose config does not match its lock
cannot proceed through gates; `advance` exited 0 - only `validate-layout` compared them.
FW-10: a Core whose identity differs from the lock's pin was refused by `artifact write` alone;
`evidence`, `state`, `advance` and `next` went on recording under another Core's rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from deltafuse.cli import main
from deltafuse.core.decide import apply_decision
from deltafuse.core.fsm import check_gate, product_pin_errors
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, advance_change, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _config_ahead_of_lock(product: Path) -> None:
    config = product / ".deltafuse" / "config.yaml"
    text = config.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(\s*version:\s*)\S+", r"\g<1>9.9.9", text, count=1)
    text = re.sub(r"deltafuse://v[0-9.]+", "deltafuse://v9.9.9", text, count=1)
    config.write_text(text, encoding="utf-8")


def _lock_pins_another_hash(product: Path) -> None:
    lock = product / ".deltafuse" / "lock.yaml"
    lock.write_text(
        re.sub(r"sha256:[0-9a-f]{64}", "sha256:" + "ab" * 32, lock.read_text(encoding="utf-8"), count=1),
        encoding="utf-8",
    )


def _lock_pins_another_version(product: Path) -> None:
    for name in ("lock.yaml", "config.yaml"):
        path = product / ".deltafuse" / name
        text = re.sub(r"(?m)^(\s*version:\s*)\S+", r"\g<1>9.9.9", path.read_text(encoding="utf-8"), count=1)
        path.write_text(re.sub(r"deltafuse://v[0-9.]+", "deltafuse://v9.9.9", text, count=1), encoding="utf-8")


@pytest.mark.parametrize("drift", [_config_ahead_of_lock, _lock_pins_another_hash, _lock_pins_another_version])
def test_a_drifted_pin_stops_gates_state_next_and_evidence(tmp_path: Path, repo_root: Path, drift, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-770", title="Pin").step_through_decompose().step_declare()
    change = builder.change_dir
    assert product_pin_errors(tmp_path) == []
    assert check_gate(change, "declaring") == []

    drift(tmp_path)
    assert product_pin_errors(tmp_path)
    assert any("lock" in e for e in check_gate(change, "declaring"))
    with pytest.raises(TransitionError, match="lock"):
        advance_change(change, "declaring")
    with pytest.raises(TransitionError, match="lock"):
        set_artifact_status(change, status="implementing", task_id="TASK-001")

    for queue in (build_work_queue(tmp_path), build_work_queue(tmp_path, only_change=change)):
        assert not queue.ready
        assert queue.blocked and "lock" in queue.blocked[0].reason
    capsys.readouterr()
    assert main(["next", str(tmp_path)]) == 1
    assert main(["evidence", str(change), "--phase", "green", "--task", "TASK-001", "--", "python", "-c", "pass"]) == 2
    assert "lock" in capsys.readouterr().err
    assert not (change / "evidence" / "green" / "TASK-001.yaml").exists()


def test_the_human_can_still_close_a_change_before_upgrading(tmp_path: Path, repo_root: Path):
    """The way out of the upgrade guard stays open: the guard asks for the active Changes to be
    closed, so closing one cannot itself wait for the upgrade."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-771", title="Pin").step_intake().step_analyze()
    _lock_pins_another_hash(tmp_path)
    closed = apply_decision(builder.change_dir, status="rejected", close=True, note="closed before the upgrade")
    assert closed["change_status"] == "rejected"


def test_there_is_one_pin_check(tmp_path: Path, repo_root: Path, monkeypatch):
    """The gates' name for the check answers with the leash's: `lock.product_pin_errors`."""
    from deltafuse.core import fsm, lock

    install(target_dir=tmp_path, framework_root=repo_root)
    _lock_pins_another_hash(tmp_path)
    assert fsm.product_pin_errors(tmp_path) == lock.product_pin_errors(tmp_path) != []
    monkeypatch.setattr(lock, "product_pin_errors", lambda root: ["the one check"])
    assert fsm.product_pin_errors(tmp_path) == ["the one check"]
