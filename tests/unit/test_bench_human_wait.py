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
