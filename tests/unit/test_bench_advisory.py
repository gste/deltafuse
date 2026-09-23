"""An advisory finding lowers the score without failing correctness or a stage.

Owner decision 2026-09-23, after the M01 run on `qwen/qwen3.8-27b`: the Worker
proposed a well-founded Decision ("which clock measures the penalty") on a case
whose oracle expects none. Nothing wrong was written - the request was read less
sharply than it deserved. That cost a correctness check and failed the analyze
stage, which also failed the gating T1/T2. It now costs score only.
"""

from __future__ import annotations

from deltafuse.bench.score import ADVISORY_PENALTY, _apply_points, _check, _stage_result


def _stage(*checks) -> dict:
    return _stage_result(list(checks), {})


def test_an_advisory_failure_does_not_fail_the_stage():
    row = _stage(
        _check("present", True, "Change present"),
        _check("routing.capability", True),
        _check("no.unexpected.decision", False, advisory=True),
    )
    assert row["pass"] is True and row["status"] == "pass"

    strict = _stage(
        _check("present", True, "Change present"),
        _check("routing.capability", False),
    )
    assert strict["pass"] is False


def test_an_advisory_failure_is_outside_correctness():
    stages = {
        "analyze": _stage(
            _check("present", True, "Change present"),
            _check("routing.capability", True),
            _check("no.unexpected.decision", False, advisory=True),
        )
    }
    earned, maximum = _apply_points(stages, {})
    assert earned == maximum == 1.0  # only routing.capability is ranked


def test_the_penalty_is_a_fixed_slice_of_the_score():
    assert ADVISORY_PENALTY == 3.0
