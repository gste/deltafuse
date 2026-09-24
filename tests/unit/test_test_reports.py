"""Red is read from the runner's report, and the two ecosystems disagree.

Until 3.3.3 the Core scanned the log for `assert`: the same `TypeError` was
authentic when pytest echoed the source line and refused when it did not, so
`--tb=short` decided whether evidence was accepted (52 of 89 refusals on
2026-09-23). These tests pin the neutral rule and both ecosystems' spelling
of it.
"""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.test_reports import (
    FAILED,
    NOT_RUN,
    PASSED,
    SKIPPED,
    green_covers_red,
    read_junit_xml,
    read_report,
    red_is_authentic,
    runner_family,
    wants_junit_flag,
)

PYTEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.test_limiter" name="test_penalty_blocks">
    <failure message="TypeError">E TypeError: __init__() got an unexpected keyword 'penalty_seconds'</failure>
  </testcase>
  <testcase classname="tests.test_limiter" name="test_setup_broken">
    <error message="fixture 'clock' not found">file or fixture missing</error>
  </testcase>
  <testcase classname="tests.test_limiter" name="test_old_behaviour"/>
  <testcase classname="tests.test_limiter" name="test_later"><skipped/></testcase>
</testsuite></testsuites>
"""

SUREFIRE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.DocumentFlowTest" tests="2">
  <testcase classname="com.example.DocumentFlowTest" name="rejectsUnapproved">
    <error type="java.lang.UnsupportedOperationException">not implemented yet</error>
  </testcase>
  <testcase classname="com.example.DocumentFlowTest" name="approvesTwice">
    <failure type="java.lang.AssertionError">expected true but was false</failure>
  </testcase>
</testsuite>
"""


def test_runner_family_and_the_flag_the_core_adds():
    assert runner_family(["pytest", "tests/"]) == "pytest"
    assert runner_family(["D:/p/.venv/Scripts/pytest.exe"]) == "pytest"
    assert runner_family(["python", "-m", "pytest"]) == "pytest"
    assert runner_family(["mvn", "-B", "test"]) == "jvm"
    assert runner_family(["./gradlew.bat", "test"]) == "jvm"
    assert runner_family(["cargo", "test"]) == ""

    assert wants_junit_flag(["pytest", "tests/"]) is True
    # The Worker asked for its own report: the Core does not add a second one.
    assert wants_junit_flag(["pytest", "--junitxml=mine.xml"]) is False
    assert wants_junit_flag(["mvn", "test"]) is False


def test_pytest_error_means_the_test_never_ran(tmp_path: Path):
    path = tmp_path / "junit.xml"
    path.write_text(PYTEST_XML, encoding="utf-8")
    got = read_junit_xml(path, error_means=NOT_RUN)
    assert got["tests.test_limiter::test_penalty_blocks"] == FAILED
    assert got["tests.test_limiter::test_setup_broken"] == NOT_RUN
    assert got["tests.test_limiter::test_old_behaviour"] == PASSED
    assert got["tests.test_limiter::test_later"] == SKIPPED


def test_surefire_error_means_the_test_ran_and_threw(tmp_path: Path):
    """A Java stub throwing UnsupportedOperationException is the normal red."""
    path = tmp_path / "TEST-com.example.DocumentFlowTest.xml"
    path.write_text(SUREFIRE_XML, encoding="utf-8")
    got = read_junit_xml(path, error_means=FAILED)
    assert got["com.example.DocumentFlowTest::rejectsUnapproved"] == FAILED
    assert got["com.example.DocumentFlowTest::approvesTwice"] == FAILED


def test_a_maven_report_is_found_where_surefire_leaves_it(tmp_path: Path):
    reports = tmp_path / "target" / "surefire-reports"
    reports.mkdir(parents=True)
    (reports / "TEST-com.example.DocumentFlowTest.xml").write_text(
        SUREFIRE_XML, encoding="utf-8"
    )
    report = read_report(["mvn", "-B", "test"], tmp_path, newer_than=None)
    assert report is not None and report.source == "surefire"
    assert len(report.ids(FAILED)) == 2

    # A report left by an earlier run is not this run's evidence.
    import time

    assert read_report(["mvn", "test"], tmp_path, newer_than=time.time() + 60) is None


def test_the_red_rule_in_neutral_words(tmp_path: Path):
    path = tmp_path / "junit.xml"
    path.write_text(PYTEST_XML, encoding="utf-8")
    mixed = read_report(["pytest"], tmp_path, junit_path=path)
    ok, why = red_is_authentic(mixed)
    assert ok is False and "could not run" in why  # one test never ran

    path.write_text(SUREFIRE_XML, encoding="utf-8")
    java_red = read_report(["mvn", "test"], tmp_path, newer_than=None) or read_report(
        ["pytest"], tmp_path, junit_path=path
    )
    # Read through pytest's meaning the Java red would be refused; through
    # Surefire's it is authentic. The adapter is what makes the rule portable.
    assert red_is_authentic(java_red)[0] is False
    from deltafuse.core.test_reports import TestReport

    assert red_is_authentic(TestReport("surefire", {"a::b": FAILED}))[0] is True
    assert red_is_authentic(TestReport("junitxml", {}))[0] is False
    assert red_is_authentic(TestReport("junitxml", {"a::b": PASSED}))[0] is False


def test_green_must_turn_the_red_tests_green():
    from deltafuse.core.test_reports import TestReport

    red_failed = ["tests.test_limiter::test_penalty_blocks"]
    green = TestReport("junitxml", {"tests.test_limiter::test_penalty_blocks": PASSED})
    assert green_covers_red(red_failed, green) == []

    # A Green run of some other test does not close the task.
    other = TestReport("junitxml", {"tests.test_limiter::test_something_else": PASSED})
    assert green_covers_red(red_failed, other) == red_failed
