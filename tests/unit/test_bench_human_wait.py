"""A gate that only waits for the human is not the model's retry.

M01 on `qwen/qwen3.8-27b` (2026-09-22): of its three gate refusals, two were
`specified` waiting for `deltafuse decide`. The Worker cannot act on those -
the skills tell it to stop and report - yet they were charged to T3 and to the
process score.
"""

from __future__ import annotations

from deltafuse.bench.journal import summarize_journal, waits_for_human

WAIT = {
    "cmd": "check-gate",
    "gate": "specified",
    "ok": False,
    "errors": [
        "Gate specified: leaving specification-proposed needs spec-delta.md "
        "accepted via deltafuse decide (Human Gate); got 'proposed'"
    ],
    "n_errors": 1,
}
OWN_FAULT = {
    "cmd": "check-gate",
    "gate": "declaring",
    "ok": False,
    "errors": ["Gate declaring: Red evidence in evidence/red/ is required"],
    "n_errors": 1,
}


def test_only_human_verdict_errors_count_as_waiting():
    assert waits_for_human(WAIT) is True
    assert waits_for_human(OWN_FAULT) is False
    assert waits_for_human({**WAIT, "ok": True}) is False
    # One Worker error among the human's: the Worker still has work to do.
    mixed = {**WAIT, "errors": WAIT["errors"] + OWN_FAULT["errors"], "n_errors": 2}
    assert waits_for_human(mixed) is False
    # A clipped error list may hide a Worker error: charge it, do not excuse it.
    assert waits_for_human({**WAIT, "n_errors": 4}) is False


def test_waiting_is_neither_an_attempt_nor_a_retry():
    summary = summarize_journal([WAIT, OWN_FAULT, {"cmd": "check-gate", "gate": "declaring", "ok": True}])
    assert summary["gate_attempts"] == 2
    assert summary["gate_retries"] == 1
    assert summary["human_waits"] == 1
    assert "specified" not in summary["check_gate"]


def test_a_run_that_only_waited_has_no_retries():
    summary = summarize_journal([WAIT, WAIT, {"cmd": "check-gate", "gate": "specified", "ok": True}])
    assert summary["gate_retries"] == 0 and summary["human_waits"] == 2


def test_a_refused_advance_is_a_gate_retry_as_check_gate_was():
    """Bench T3 read gate retries from `check-gate` lines only, and the skills close every gate
    with `advance`: T3 read 0 for every Worker that followed them (codebase audit 2026-10-22)."""
    adv_fail = {**OWN_FAULT, "cmd": "advance", "seq": 1}
    adv_ok = {"cmd": "advance", "gate": "declaring", "ok": True, "seq": 2}
    summary = summarize_journal([adv_fail, adv_ok])
    assert summary["gate_retries"] == 1
    assert summary["by_stage"]["declare"] == {"attempts": 2, "retries": 1}
    (cycle,) = summary["cycles"]
    assert cycle["gate"] == "declaring" and cycle["n"] == 2 and cycle["fail"] == 1 and cycle["ok"]
    # The human's verdict is not the model's retry, whichever command asked the gate.
    waiting = summarize_journal([{**WAIT, "cmd": "advance"}])
    assert waiting["gate_retries"] == 0 and waiting["human_waits"] == 1


def test_the_cli_journals_a_refused_advance_one_error_per_gate_finding(tmp_path, repo_root):
    from deltafuse.bench.journal import load_events
    from deltafuse.cli import main
    from deltafuse.core.installer import install
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / ".deltafuse" / "bench.yaml").write_text("case: J\n", encoding="utf-8")  # a bench product journals
    builder = MockChangeBuilder(tmp_path, change_id="CHG-501", title="Journal").step_intake()
    (builder.change_dir / "request.md").unlink()
    assert main(["advance", str(builder.change_dir), "--gate", "analyzed"]) == 1
    (event,) = [e for e in load_events(tmp_path) if e.get("cmd") == "advance"]
    assert event["ok"] is False and event["gate"] == "analyzed"
    assert event["n_errors"] == len(event["errors"]) > 1
    assert not any(e.startswith("gate 'analyzed' failed") for e in event["errors"])
