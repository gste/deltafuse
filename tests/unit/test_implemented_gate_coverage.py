"""The implemented gate re-checks that Green passed the tests Red saw fail.

`green_covers_red` ran only when the Green evidence was recorded, and the
record is written even when that check fails - so a Green recorded over a
different test closed the gate. The isolated run of the frozen oracle hid this
for Reds frozen per test; a Red whose tests lie outside the oracle roots, or
one recorded without a per-test freeze, still went through.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.fsm import green_coverage_errors

RED_FAILED = ["tests.test_limiter::test_cooldown", "tests.test_limiter::test_burst[2]"]


def _errors(tmp_path: Path, red: dict, green: dict) -> list[str]:
    red_file, green_file = tmp_path / "red.yaml", tmp_path / "green.yaml"
    red_file.write_text(yaml.safe_dump(red), encoding="utf-8")
    green_file.write_text(yaml.safe_dump(green), encoding="utf-8")
    return green_coverage_errors(red_file, green_file, "green evidence 'TASK-001.yaml'")


def _red(**tests) -> dict:
    return {"result": "expected-failure", "tests": {"source": "junitxml", "failed": RED_FAILED, **tests}}


def test_a_green_that_passed_the_red_tests_is_accepted(tmp_path: Path):
    green = {"exit_code": 0, "tests": {"source": "junitxml", "passed": [*RED_FAILED, "tests.test_x::test_new"]}}
    assert _errors(tmp_path, _red(), green) == []


def test_a_green_over_other_tests_is_refused_and_names_what_did_not_pass(tmp_path: Path):
    green = {"exit_code": 0, "tests": {"source": "junitxml", "passed": ["tests.test_other::test_other"]}}
    errs = _errors(tmp_path, _red(), green)
    assert len(errs) == 1 and "did not pass the tests Red recorded as failing" in errs[0], errs
    assert "tests.test_limiter::test_cooldown" in errs[0]


def test_a_red_test_that_failed_again_in_green_is_refused(tmp_path: Path):
    green = {"exit_code": 1, "tests": {"source": "junitxml", "passed": RED_FAILED[:1], "failed": RED_FAILED[1:]}}
    errs = _errors(tmp_path, _red(), green)
    assert errs and "test_burst[2]" in errs[0], errs


def test_a_green_without_a_runner_report_cannot_show_the_red_tests_passing(tmp_path: Path):
    errs = _errors(tmp_path, _red(), {"exit_code": 0})
    assert errs and "no runner report" in errs[0], errs


def test_a_red_without_a_report_or_failed_tests_has_nothing_to_cover(tmp_path: Path):
    assert _errors(tmp_path, {"result": "expected-failure"}, {"exit_code": 0}) == []
    assert _errors(tmp_path, _red(failed=[]), {"exit_code": 0}) == []
    # An already-green Red is refused by its own rule, not by this one.
    assert _errors(tmp_path, {**_red(), "result": "already-green"}, {"exit_code": 0}) == []
