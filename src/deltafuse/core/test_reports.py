"""What the test runner itself said, instead of what its log looked like.

Until 3.3.4 a Red record was judged by scanning the log for the substring
``assert``. The same ``TypeError`` was `behavioral-mismatch` when pytest
echoed the source line and `fixture-error` when it did not, so the Worker's
choice of ``--tb=short`` decided whether its evidence was accepted: 52 of the
89 evidence refusals in the runs of 2026-09-23.

Every runner we care about already publishes a machine-readable report, so
the Core reads that. The catch is that the two ecosystems disagree on what
``<error>`` means, and a rule written for one is wrong in the other:

* pytest writes ``<failure>`` for any exception raised inside the test and
  ``<error>`` when collection or a fixture kept the test from running;
* Surefire and Gradle write ``<failure>`` for a failed assertion and
  ``<error>`` for any other exception - so the canonical Java red, a stub
  throwing ``UnsupportedOperationException``, is an ``<error>``.

Both are mapped onto one neutral outcome per test: it ran and did not pass,
it never ran, it was skipped, or it passed. The rule the Core applies is
written in those words and holds in both.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

FAILED = "failed"  # the test ran and did not pass
NOT_RUN = "not-run"  # collection, compilation or a fixture kept it from running
SKIPPED = "skipped"
PASSED = "passed"

PYTEST_RUNNERS = frozenset({"pytest", "py.test"})
JVM_RUNNERS = frozenset({"mvn", "mvnw", "gradle", "gradlew"})
# Where Surefire, Failsafe and Gradle leave their XML without being asked.
JVM_REPORT_GLOBS = (
    "target/surefire-reports/TEST-*.xml",
    "target/failsafe-reports/TEST-*.xml",
    "build/test-results/*/TEST-*.xml",
    "*/target/surefire-reports/TEST-*.xml",
    "*/build/test-results/*/TEST-*.xml",
)


@dataclass
class TestReport:
    """One run of a suite, as the runner reported it."""

    source: str  # "junitxml" (we asked pytest for it) or "surefire" (found on disk)
    outcomes: dict[str, str] = field(default_factory=dict)

    def ids(self, outcome: str) -> list[str]:
        return sorted(name for name, got in self.outcomes.items() if got == outcome)

    @property
    def empty(self) -> bool:
        return not self.outcomes


def _strip_runner_suffix(name: str) -> str:
    for suffix in (".exe", ".cmd", ".bat"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def runner_family(argv: list[str]) -> str:
    """`pytest`, `jvm`, or `` when the Core has no reader for this runner."""
    if not argv:
        return ""
    head = _strip_runner_suffix(Path(str(argv[0]).replace("\\", "/")).name).lower()
    if head in PYTEST_RUNNERS:
        return "pytest"
    if head in JVM_RUNNERS:
        return "jvm"
    if head in {"python", "python3"} and "pytest" in argv[1:3]:
        return "pytest"
    return ""


def wants_junit_flag(argv: list[str]) -> bool:
    """pytest writes a report only when asked, and the Core is the one asking."""
    return runner_family(argv) == "pytest" and not any(
        str(arg).startswith("--junitxml") for arg in argv
    )


def _case_id(case: ET.Element) -> str:
    classname = (case.get("classname") or "").strip()
    name = (case.get("name") or "").strip()
    return f"{classname}::{name}" if classname else name


def read_junit_xml(path: Path, *, error_means: str) -> dict[str, str]:
    """One JUnit XML file as neutral outcomes. `error_means` is the ecosystem's."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return {}
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = _case_id(case)
        if not name:
            continue
        if case.find("skipped") is not None:
            outcomes[name] = SKIPPED
        elif case.find("failure") is not None:
            outcomes[name] = FAILED
        elif case.find("error") is not None:
            outcomes[name] = error_means
        else:
            outcomes[name] = PASSED
    return outcomes


def read_report(
    argv: list[str],
    repo_root: Path,
    *,
    junit_path: Path | None = None,
    newer_than: float | None = None,
) -> TestReport | None:
    """The report this command produced, or None when the runner leaves none.

    `newer_than` keeps a stale report from a previous run out: Surefire and
    Gradle write into a fixed directory and do not clean it themselves.
    """
    family = runner_family(argv)
    if family == "pytest":
        if junit_path is None or not junit_path.is_file():
            return None
        # A test that raises inside its body is a `<failure>` for pytest; an
        # `<error>` is a fixture or collection problem, so the test never ran.
        return TestReport("junitxml", read_junit_xml(junit_path, error_means=NOT_RUN))
    if family == "jvm":
        outcomes: dict[str, str] = {}
        found = False
        for pattern in JVM_REPORT_GLOBS:
            for path in sorted(repo_root.glob(pattern)):
                try:
                    if newer_than is not None and path.stat().st_mtime < newer_than:
                        continue
                except OSError:
                    continue
                found = True
                # Surefire and Gradle call any non-assertion exception an
                # `<error>`, but the test did run: a stub that throws is the
                # normal shape of a Java red.
                outcomes.update(read_junit_xml(path, error_means=FAILED))
        return TestReport("surefire", outcomes) if found else None
    return None


def red_is_authentic(report: TestReport) -> tuple[bool, str | None]:
    """Red: the named tests ran and none of them passed. Returns (ok, why not)."""
    if report.empty:
        return False, (
            "the runner reported no tests at all; a suite that did not run is "
            "not evidence that behaviour is missing"
        )
    not_run = report.ids(NOT_RUN)
    if not_run:
        return False, (
            "tests could not run (collection, compilation or a fixture), so the "
            f"failure is in the test, not in the product: {not_run[:5]}"
        )
    if not report.ids(FAILED):
        return False, "every test that ran passed: there is nothing red here"
    return True, None


def green_covers_red(red_failed: list[str], report: TestReport) -> list[str]:
    """Red tests that Green did not turn green. Empty is what Green must show.

    The point of a Red record is that the test discriminates the change. That
    is only shown when the same test passes afterwards - nothing checked it
    before 3.3.4, so a Red test with a typo in it and a Green run of a
    different test read as a finished task.
    """
    passed = {name for name, got in report.outcomes.items() if got == PASSED}
    return sorted(name for name in red_failed if name not in passed)
