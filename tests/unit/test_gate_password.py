"""Optional Human Gate password (roadmap item 4, 2026-09-22)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deltafuse.cli import main
from deltafuse.core import gate_password, gate_receipts
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.installer import install
from deltafuse.core.leash import check_paths

PASSWORD = "correct horse"


@pytest.fixture(autouse=True)
def _fast_kdf(monkeypatch):
    monkeypatch.setattr(gate_password, "ITERATIONS", 1_000)


def _product(tmp_path: Path, repo_root: Path) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "DEC-0009.md").write_text(
        "---\n"
        "id: DEC-0009\n"
        "title: Storage\n"
        "kind: architecture\n"
        "status: proposed\n"
        "owner: human\n"
        "change: null\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision\n",
        encoding="utf-8",
    )
    return tmp_path


def _decision(root: Path) -> Path:
    return root / "docs" / "decisions" / "DEC-0009.md"


def test_file_holds_a_salted_hash_not_the_password(tmp_path: Path, repo_root: Path):
    root = _product(tmp_path, repo_root)
    assert not gate_password.is_enabled(root)

    gate_password.set_password(root, PASSWORD)

    stored = gate_password.password_path(root).read_text(encoding="utf-8")
    assert PASSWORD not in stored and "salt" in stored
    assert gate_password.verify_password(root, PASSWORD)
    assert not gate_password.verify_password(root, "wrong password")
    assert not gate_password.verify_password(root, None)


def test_change_and_clear_need_the_current_password(tmp_path: Path, repo_root: Path):
    root = _product(tmp_path, repo_root)
    gate_password.set_password(root, PASSWORD)

    with pytest.raises(gate_password.GatePasswordError, match="current"):
        gate_password.set_password(root, "another password")
    with pytest.raises(gate_password.GatePasswordError, match="current"):
        gate_password.clear_password(root, "wrong password")
    with pytest.raises(gate_password.GatePasswordError, match="at least"):
        gate_password.set_password(root, "short", current=PASSWORD)

    gate_password.clear_password(root, PASSWORD)
    assert not gate_password.is_enabled(root)


def test_decide_without_password_records_none(tmp_path: Path, repo_root: Path):
    root = _product(tmp_path, repo_root)

    result = apply_decision(root, status="accepted", decision="DEC-0009")

    assert result["human_check"] == "none"
    assert gate_receipts.load_receipts(root)[-1]["human_check"] == "none"


@pytest.mark.parametrize("prompt", [None, lambda: "wrong password"])
def test_decide_refused_before_any_write(tmp_path: Path, repo_root: Path, prompt):
    root = _product(tmp_path, repo_root)
    gate_password.set_password(root, PASSWORD)
    before = _decision(root).read_bytes()

    with pytest.raises(DecideError, match="password"):
        apply_decision(root, status="accepted", decision="DEC-0009", password_prompt=prompt)

    assert _decision(root).read_bytes() == before
    assert gate_receipts.load_receipts(root) == []


def test_decide_with_password_records_the_check(tmp_path: Path, repo_root: Path):
    root = _product(tmp_path, repo_root)
    gate_password.set_password(root, PASSWORD)

    result = apply_decision(
        root, status="accepted", decision="DEC-0009", password_prompt=lambda: PASSWORD
    )

    assert result["ok"] and result["human_check"] == "password"
    receipt = gate_receipts.load_receipts(root)[-1]
    assert receipt["human_check"] == "password"
    assert gate_receipts.journal_errors(root) == []


def test_failed_receipt_undoes_the_verdict(tmp_path: Path, repo_root: Path, monkeypatch):
    root = _product(tmp_path, repo_root)
    before = _decision(root).read_bytes()

    def broken(*_args, **_kwargs):
        raise gate_receipts.ReceiptError("disk full")

    monkeypatch.setattr(gate_receipts, "record_receipt", broken)
    with pytest.raises(DecideError, match="verdict undone"):
        apply_decision(root, status="accepted", decision="DEC-0009")

    assert _decision(root).read_bytes() == before


def test_cli_refuses_without_a_terminal(tmp_path: Path, repo_root: Path, monkeypatch, capsys):
    root = _product(tmp_path, repo_root)
    gate_password.set_password(root, PASSWORD)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    code = main(["decide", str(root), "--decision", "DEC-0009", "--status", "accepted"])

    assert code == 1
    assert "interactive terminal" in capsys.readouterr().err
    assert "status: proposed" in _decision(root).read_text(encoding="utf-8")


def test_cli_status_reports_enabled(tmp_path: Path, repo_root: Path, capsys):
    root = _product(tmp_path, repo_root)
    assert main(["gate-password", "status", str(root)]) == 0
    assert "disabled" in capsys.readouterr().out
    gate_password.set_password(root, PASSWORD)
    assert main(["gate-password", "status", str(root)]) == 0
    assert "enabled" in capsys.readouterr().out


def test_leash_refuses_the_password_file_in_a_worker_diff():
    errors = check_paths([gate_password.PASSWORD_REL], [], baseline="draft")
    assert errors and "Core-owned" in errors[0]


def test_journal_json_carries_no_secret(tmp_path: Path, repo_root: Path):
    root = _product(tmp_path, repo_root)
    gate_password.set_password(root, PASSWORD)
    apply_decision(root, status="accepted", decision="DEC-0009", password_prompt=lambda: PASSWORD)
    journal = (root / gate_receipts.JOURNAL_REL).read_text(encoding="utf-8")
    assert PASSWORD not in journal
    assert all(json.loads(line) for line in journal.splitlines())
