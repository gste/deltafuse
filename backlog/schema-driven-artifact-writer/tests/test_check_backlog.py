"""AW-45 checker tests: valid ready/all-blocked fixtures and the six observed
negative patterns (AW-20 unfinished dependency, stale AW-37-style handoff,
false no-work-remaining claim, unknown dependency, duplicate IDs, cycles)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_backlog  # noqa: E402


def _card(cid, status, deps=None, checks=None, **extra):
    card = {"id": cid, "phase": "X", "title": cid, "status": status,
            "depends_on": deps or [], "card_path": f"cards/{cid}.md",
            "result_path": f"results/{cid}.md"}
    card.update(extra)
    if checks is not None:
        card["acceptance_checks"] = checks
    return card


def _doc(cards, entry=None, top_status="in_progress", order=None):
    if entry is None:
        entry = next(
            (c["id"] for c in cards if c["status"] != "completed"),
            cards[0]["id"],
        )
    return {
        "schema_version": 1,
        "status": top_status,
        "entry": entry,
        "order": "first unfinished dependency-ready card",
        "cards": cards,
        "execution_order": order or [c["id"] for c in cards],
    }


# --- valid fixtures --------------------------------------------------------


def test_valid_ready_selection():
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-01"]),
    ]
    violations, report = check_backlog.check(_doc(cards), file_checks=False)
    assert violations == []
    assert report["entry"] == "AW-02"


def test_valid_blocked_by_environment_reports_requirement(capsys):
    blocker = {"requirement": "native POSIX host with SeCreateSymbolicLinkPrivilege"}
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-01"], environment_blocker=blocker),
    ]
    violations, report = check_backlog.check(_doc(cards), file_checks=False)
    assert violations == []
    assert report["entry"] == "AW-02"
    assert report["environment_blocked"] == blocker["requirement"]
    out = capsys.readouterr().out
    assert "ready by dependency but blocked by environment" in out
    assert "independent ready work may proceed" in out


# --- negative fixtures -----------------------------------------------------


def test_unknown_dependency_detected():
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-99"]),
    ]
    violations, _ = check_backlog.check(_doc(cards), file_checks=False)
    assert any("unknown dependency" in v and "AW-99" in v for v in violations)


def test_duplicate_card_ids_detected():
    cards = [_card("AW-01", "completed"), _card("AW-01", "planned")]
    violations, _ = check_backlog.check(_doc(cards), file_checks=False)
    assert any("duplicate card id: AW-01" in v for v in violations)


def test_duplicate_check_ids_detected():
    cards = [_card("AW-01", "planned", checks=[
        {"id": "AW01-R1", "requirement": "x", "status": "open"},
        {"id": "AW01-R1", "requirement": "y", "status": "open"},
    ])]
    violations, _ = check_backlog.check(_doc(cards), file_checks=False)
    assert any("duplicate acceptance-check id" in v for v in violations)


def test_dependency_cycle_detected():
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-03"]),
        _card("AW-03", "planned", deps=["AW-02"]),
    ]
    violations, _ = check_backlog.check(_doc(cards), file_checks=False)
    assert any("dependency cycle" in v for v in violations)


def test_stale_handoff_entry_detected():
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-01"]),
    ]
    doc = _doc(cards, entry="AW-03")
    violations, report = check_backlog.check(doc, file_checks=False)
    assert report["entry"] == "AW-02"
    assert any("stale handoff" in v for v in violations)


def test_false_no_work_remaining_claim_detected():
    cards = [
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-01"]),
    ]
    doc = _doc(cards, entry="AW-02", top_status="completed")
    violations, _ = check_backlog.check(doc, file_checks=False)
    assert any("false no-work-remaining claim" in v for v in violations)


def test_aw20_unfinished_dependency_with_passed_labels_detected():
    cards = [
        _card("AW-42", "in_progress"),
        _card("AW-20", "in_progress", deps=["AW-42"], checks=[
            {"id": "AW20-F1", "requirement": "r1", "status": "passed"},
            {"id": "AW20-F2", "requirement": "r2", "status": "passed"},
        ]),
    ]
    violations, _ = check_backlog.check(_doc(cards), file_checks=False)
    assert any("AW-20" in v and "all acceptance checks passed" in v for v in violations)


# --- main() exit codes and file checks -------------------------------------


def test_main_exit_codes(tmp_path, capsys):
    pos = _doc([
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-01"]),
    ])
    q = tmp_path / "queue.json"
    q.write_text(json.dumps(pos), encoding="utf-8")
    assert check_backlog.main([str(q), "--no-file-checks"]) == 0

    neg = _doc([
        _card("AW-01", "completed"),
        _card("AW-02", "planned", deps=["AW-99"]),
    ])
    q2 = tmp_path / "queue-bad.json"
    q2.write_text(json.dumps(neg), encoding="utf-8")
    assert check_backlog.main([str(q2), "--no-file-checks"]) == 1


def test_file_checks_card_status_mismatch_detected(tmp_path):
    boom = _card("AW-01", "completed")
    doc = _doc([boom])
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (cards_dir / "AW-01.md").write_text("Status: in_progress\n", encoding="utf-8")
    (results_dir / "AW-01.md").write_text("- Status: completed\n", encoding="utf-8")
    queue_file = tmp_path / "queue.json"
    queue_file.write_text(json.dumps(doc), encoding="utf-8")
    violations, _ = check_backlog.check(doc, queue_path=queue_file)
    assert any("card/queue status mismatch" in v for v in violations)


def test_file_checks_missing_card_file_detected(tmp_path):
    doc = _doc([_card("AW-01", "completed")])
    queue_file = tmp_path / "queue.json"
    queue_file.write_text(json.dumps(doc), encoding="utf-8")
    violations, _ = check_backlog.check(doc, queue_path=queue_file)
    assert any("card file missing" in v for v in violations)