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

import re
import shlex
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
    # Failed test -> (message, traceback text) as the runner wrote them; pytest only.
    failures: dict[str, tuple[str, str]] = field(default_factory=dict)

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


def runner_head(program: object) -> str:
    """The runner's bare name: no directory, no `.exe`/`.cmd`/`.bat`, lower case."""
    return _strip_runner_suffix(Path(str(program).replace("\\", "/")).name).lower()


_PYTHON_HEAD = re.compile(r"^(?:python|pypy)\d*(?:\.\d+)*$")
# Interpreter options that take their value as the next argument (`python -X utf8 -m pytest`).
_PYTHON_VALUE_OPTIONS = frozenset({"-X", "-W"})
# Launchers that run a command in the project's environment: `uv run pytest`, `poetry run pytest`.
ENV_WRAPPERS: dict[str, str] = {"uv": "run", "poetry": "run", "pipenv": "run", "pdm": "run", "hatch": "run", "rye": "run"}
_WRAPPER_VALUE_OPTIONS = frozenset({
    "--with", "--with-requirements", "--with-editable", "--python", "-p", "--project", "--directory", "-C",
    "--extra", "--group", "--only-group", "--no-group", "--package", "--env-file", "--env", "-e",
    "--index", "--default-index", "--index-url", "--extra-index-url", "--find-links", "--cache-dir",
})


def is_python(program: object) -> bool:
    """A Python interpreter, however it is called: `python`, `python3`, `python3.12`, `pypy3`, `py`."""
    head = runner_head(program)
    return head == "py" or bool(_PYTHON_HEAD.match(head))


def pytest_args_start(argv: list[str]) -> int | None:
    """The index of pytest's first own argument; None when the command is not pytest.

    Audit 2026-11-17 (FE-3): pytest was recognised as `pytest ...` or `python -m pytest ...` and
    nothing else, so `python -X utf8 -m pytest` and `uv run pytest` - the commands a product
    declares in `workflow.test_commands` - were runners without a reader: no report was asked for
    or read, and Green was no longer tied to the Red it answers. The command is read once, here:
    environment launchers (`uv run`, `poetry run`, ...) and the interpreter's own options are
    skipped, and everything after `pytest` is pytest's.
    """
    args = [str(a) for a in argv]
    i, n = 0, len(args)
    for _ in range(4):  # a launcher, then an interpreter, then pytest
        if i >= n:
            return None
        head = runner_head(args[i])
        if head in PYTEST_RUNNERS:
            return i + 1
        if is_python(head):
            j = i + 1
            while j < n:
                arg = args[j]
                if arg == "-m":
                    return j + 2 if j + 1 < n and args[j + 1] in PYTEST_RUNNERS else None
                if arg in _PYTHON_VALUE_OPTIONS:
                    j += 2
                elif arg.startswith("-") and arg != "-c":
                    j += 1
                else:
                    return None  # a script or `-c`: not pytest
            return None
        if ENV_WRAPPERS.get(head) and i + 1 < n and args[i + 1] == ENV_WRAPPERS[head]:
            j = i + 2
            while j < n and args[j].startswith("-"):
                if args[j] == "--":
                    j += 1
                    break
                j += 2 if args[j] in _WRAPPER_VALUE_OPTIONS else 1
            i = j
            continue
        return None
    return None


def runner_family(argv: list[str]) -> str:
    """`pytest`, `jvm`, or `` when the Core has no reader for this runner."""
    if not argv:
        return ""
    if runner_head(argv[0]) in JVM_RUNNERS:
        return "jvm"
    if pytest_args_start(argv) is not None:
        return "pytest"
    return ""


_READABLE_RUNNER_WORD = re.compile(r"(?<![\w.-])(?:pytest|py\.test|mvn|mvnw|gradle|gradlew)(?![\w-])")


def names_a_readable_runner(argv: list[str]) -> str | None:
    """The runner (`pytest`, `mvn`, ...) a command mentions somewhere in its arguments, if any."""
    for arg in argv:
        found = _READABLE_RUNNER_WORD.search(str(arg).replace("\\", "/"))
        if found:
            return found.group(0)
    return None


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
        elif case.find("failure") is not None or case.find("error") is not None:
            if error_means == FAILED and _class_level(case):
                # Audit 2026-11-16 (df-evidence #8): a throwing `@BeforeAll` (JUnit 4:
                # `initializationError`) is reported against the class, not a method. Read as a
                # failed test `demo.CalcTest::`, it was accepted as Red and no Green could ever
                # pass a test of that name. The class's tests never ran.
                outcomes[name] = NOT_RUN
            else:
                outcomes[name] = FAILED if case.find("failure") is not None else error_means
        else:
            outcomes[name] = PASSED
    return outcomes


def _class_level(case: ET.Element) -> bool:
    """A JVM testcase that stands for its class, not a method: no name, the class's own name,
    or JUnit 4's `initializationError`."""
    name = (case.get("name") or "").strip()
    classname = (case.get("classname") or "").strip()
    return not name or name == classname or name == classname.rsplit(".", 1)[-1] or name == "initializationError"


def read_junit_failures(path: Path) -> dict[str, tuple[str, str]]:
    """Each `<failure>` of one JUnit XML file as (message, traceback text)."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return {}
    found: dict[str, tuple[str, str]] = {}
    for case in root.iter("testcase"):
        failure = case.find("failure")
        name = _case_id(case)
        if name and failure is not None:
            found[name] = ((failure.get("message") or "").strip(), failure.text or "")
    return found


def jvm_module_prefix(rel: str) -> str:
    """`a/` for a report or source under module `a` (`a/target/...`, `a/src/test/...`); `` for
    the root module.

    Audit 2026-11-16 (df-evidence #5): the reports of a multi-module build were merged by
    `class::method`, so a passing test of the same name in another module overwrote the failing
    Red test. A module's test ids carry the module; a single-module product's are unchanged.
    """
    parts = rel.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part in {"target", "build"} or parts[i:i + 2] == ["src", "test"]:
            return "/".join(parts[:i]) + "/" if i else ""
    return ""


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
        try:
            if newer_than is not None and junit_path.stat().st_mtime < newer_than:
                return None  # the Worker's own --junitxml file, left by an earlier run
        except OSError:
            return None
        # A test that raises inside its body is a `<failure>` for pytest; an
        # `<error>` is a fixture or collection problem, so the test never ran.
        return TestReport(
            "junitxml",
            read_junit_xml(junit_path, error_means=NOT_RUN),
            read_junit_failures(junit_path),
        )
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
                prefix = jvm_module_prefix(path.relative_to(repo_root).as_posix())
                outcomes.update(
                    (prefix + name, got) for name, got in read_junit_xml(path, error_means=FAILED).items()
                )
        return TestReport("surefire", outcomes) if found else None
    return None


def worker_junit_path(argv: list[str]) -> str | None:
    """The report path the Worker gave pytest itself, when it did."""
    for i, arg in enumerate(argv):
        for flag in ("--junitxml", "--junit-xml"):
            if arg.startswith(f"{flag}="):
                return arg.split("=", 1)[1] or None
            if arg == flag and i + 1 < len(argv):
                return argv[i + 1]
    return None


# Gradle's word for a task it skipped: its inputs did not change since the last
# run (UP-TO-DATE), or the build cache already had its outputs (FROM-CACHE).
_GRADLE_SKIPPED_TEST = re.compile(r"UP-TO-DATE|FROM-CACHE|\d+ up-to-date|\d+ from cache")


def _command_argv(command: object) -> list[str]:
    if isinstance(command, list):
        return [str(arg) for arg in command]
    try:
        return shlex.split(str(command or ""))
    except ValueError:
        return str(command or "").split()


def no_test_ran(command: object, tests: object, log: str = "") -> str | None:
    """Why a passing run is no evidence: the runner ran no test. None when it did.

    Fuse-Back, Gradle J01 (2026-10-09): right after Green, regression ran the same
    `gradle test`, Gradle reported the test task UP-TO-DATE and ran nothing, and the
    record read `exit_code: 0`, `passed`, authentic. A runner whose report the Core
    reads either leaves a fresh report naming the tests it ran, or ran none. A runner
    without such a report is not judged here - there is nothing to judge it by.
    """
    argv = _command_argv(command)
    family = runner_family(argv)
    if not family:
        return None
    if isinstance(tests, dict) and (tests.get(PASSED) or tests.get(FAILED)):
        return None
    if family == "jvm" and _GRADLE_SKIPPED_TEST.search(log or ""):
        return (
            "the runner ran no test: Gradle reported the test task up to date (or took it from "
            "the build cache) and executed nothing. Add `--rerun` to the test task "
            "(`gradle test --rerun`; before Gradle 7.6, `--rerun-tasks`) and record it again"
        )
    if not isinstance(tests, dict):
        return (
            f"the runner ran no test it reported: `{argv[0]}` left no test report written by "
            "this run, so the record does not show that any test ran. Run the tests so that "
            "they execute, and record it again"
        )
    return (
        "the runner ran no test: its report of this run names none that passed or failed, "
        "and a suite that did not run is not evidence. Run the tests, and record it again"
    )


def no_test_error(label: str, command: object, tests: object, log: str = "") -> list[str]:
    """`<label> is not evidence: <why>` when the run ran no test (`no_test_ran`); else empty."""
    why = no_test_ran(command, tests, log)
    return [f"{label} is not evidence: {why}"] if why else []


def red_is_authentic(report: TestReport) -> tuple[bool, str | None]:
    """Red: the named tests ran and none of them passed. Returns (ok, why not)."""
    if report.empty:
        return False, (
            "the runner reported no tests at all; a suite that did not run is "
            "not evidence that behaviour is missing"
        )
    not_run = report.ids(NOT_RUN)
    if not_run:
        class_level = [name for name in not_run if name.endswith("::")]
        return False, (
            "tests could not run (collection, compilation or a fixture), so the "
            f"failure is in the test, not in the product: {not_run[:5]}"
            + (
                ". A class-level setup failed (`@BeforeAll`, a static initializer), so none of "
                "the class's tests ran: move what it calls into the tests themselves, so each "
                "test runs and fails on its own"
                if class_level else ""
            )
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


# --- the task's own tests -----------------------------------------------------------------------
#
# Audit 2026-11-16 (df-evidence #1, q7 decision): Red was judged on the whole report, so a
# pre-existing broken test elsewhere in the suite made an authentic Red while the task's own test
# already passed, and Green then closed `implemented` with no product change. Red is about the
# tests the task names: the test files Declare wrote (its `changed_paths`), or, for a test that
# is already committed, the tests its command selects.

JVM_TEST_SUFFIXES = (".java", ".kt", ".groovy", ".scala")
_JVM_TEST_ROOT = re.compile(r"(?:^|/)src/test/[^/]+/")


def is_test_file(rel: str) -> bool:
    """A file a runner reads tests from: `test_*.py` / `*_test.py`, or JVM test source."""
    rel = rel.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    if name.endswith(".py"):
        return name.startswith("test_") or name.endswith("_test.py")
    return name.endswith(JVM_TEST_SUFFIXES) and bool(_JVM_TEST_ROOT.search(rel))


def declared_test_files(changed_paths: list[str]) -> list[str]:
    """The test files among a record's changed_paths."""
    return sorted({
        p.replace("\\", "/").lstrip("/") for p in changed_paths if isinstance(p, str) and is_test_file(p)
    })


def _pytest_id_in(test_id: str, rel: str) -> bool:
    """A pytest JUnit id (`dotted.module[.Class]::name`, or a bare module for a collection
    error) names a test of *rel*. The dotted part is relative to pytest's rootdir, so a trailing
    part of the module path must start it (the reading oracle._resolve uses)."""
    if not rel.endswith(".py"):
        return False
    classname, sep, _name = test_id.rpartition("::")
    dotted = (classname if sep else test_id).split("[", 1)[0]
    cparts = [p for p in dotted.split(".") if p]
    mparts = rel[:-3].split("/")
    return any(cparts[:k] == mparts[-k:] for k in range(len(mparts), 0, -1))


def _jvm_class_of(rel: str) -> tuple[str, str]:
    """(module prefix, fully qualified class) of a JVM test source under `src/test/<lang>/`."""
    rel = rel.replace("\\", "/")
    stem = rel.rsplit(".", 1)[0]
    match = _JVM_TEST_ROOT.search(rel)
    start = match.end() if match else len(stem) - len(stem.rsplit("/", 1)[-1])
    return jvm_module_prefix(rel), stem[start:].replace("/", ".")


def _jvm_id_class(test_id: str) -> tuple[str, str]:
    """(module prefix, top-level class) of a JVM test id `[module/]pkg.Class[$Inner]::method`."""
    classname = test_id.split("::", 1)[0]
    prefix, _, classname = classname.rpartition("/")
    return (prefix + "/" if prefix else ""), classname.split("$", 1)[0]


def _jvm_id_in(test_id: str, rel: str) -> bool:
    if not rel.endswith(JVM_TEST_SUFFIXES):
        return False
    return _jvm_class_of(rel) == _jvm_id_class(test_id)


def test_in_files(test_id: str, files: list[str], family: str) -> bool:
    """True when *test_id*, as *family*'s report spells it, is a test of one of *files*."""
    if family == "jvm":
        return any(_jvm_id_in(test_id, rel) for rel in files)
    return any(_pytest_id_in(test_id, rel) for rel in files)


test_in_files.__test__ = False  # a helper, not a test, for pytest collecting a module importing it

# pytest options whose value is the next argument, so that value is not read as a test path.
_PYTEST_VALUE_OPTIONS = frozenset({
    "-k", "-m", "-p", "-c", "-o", "--deselect", "--ignore", "--ignore-glob", "--rootdir", "--junitxml",
    "--junit-xml", "--basetemp", "--import-mode", "--confcutdir", "-W", "--pythonwarnings", "--maxfail",
    "--tb", "--durations", "--config-file", "--override-ini",
})


def pytest_positionals(argv: list[str], repo_root: Path) -> list[str]:
    """The test paths and node ids a pytest command names (existing paths only), POSIX form."""
    start = pytest_args_start(argv)
    if start is None:
        return []
    out: list[str] = []
    rest = iter(argv[start:])
    for arg in rest:
        if arg in _PYTEST_VALUE_OPTIONS:
            next(rest, None)
            continue
        if arg.startswith("-"):
            continue
        posix = arg.replace("\\", "/")
        if (repo_root / posix.split("::", 1)[0]).exists():
            out.append(posix)
    return out


def jvm_test_selection(argv: list[str]) -> list[str]:
    """The class patterns a Maven `-Dtest=` / `-Dit.test=` or Gradle `--tests` names."""
    patterns: list[str] = []
    args = [str(a) for a in argv[1:]]
    for i, arg in enumerate(args):
        value = None
        for flag in ("-Dtest=", "-Dit.test="):
            if arg.startswith(flag):
                value = arg[len(flag):]
        if arg == "--tests" and i + 1 < len(args):
            value = args[i + 1]
        elif arg.startswith("--tests="):
            value = arg.split("=", 1)[1]
        for item in (value or "").split(","):
            item = item.strip().lstrip("!")
            if item:
                patterns.append(item.split("#", 1)[0])
    return patterns


def _jvm_selected(test_id: str, patterns: list[str]) -> bool:
    import fnmatch

    _prefix, cls = _jvm_id_class(test_id)
    simple = cls.rsplit(".", 1)[-1]
    for pattern in patterns:
        if pattern.endswith((".java", ".class", ".kt")):
            pattern = pattern.rsplit(".", 1)[0]
        pattern = pattern.replace("/", ".")
        if fnmatch.fnmatchcase(cls if "." in pattern else simple, pattern):
            return True
    return False


def report_family(report: TestReport) -> str:
    return "jvm" if report.source == "surefire" else "pytest"


def _named_files(argv: list[str], repo_root: Path) -> list[str]:
    return sorted({
        p.split("::", 1)[0] for p in pytest_positionals(argv, repo_root)
        if (repo_root / p.split("::", 1)[0]).is_file()
    })


def task_test_ids(
    report: TestReport, changed_paths: list[str], argv: list[str], repo_root: Path,
    *, taken: dict[str, str] | None = None,
) -> tuple[list[str] | None, str]:
    """The report's tests that are the task's, and how they were named; (None, "") when nothing
    names them - no declared test file and no test file or class selected on the command line.

    *taken* maps a test to the other task whose Red record already names it as failing. Those are
    never this task's (audit 2026-11-17, FE-1): the changed paths the Core computes are the whole
    dirty tree, and during Declare that tree holds every earlier task's still-failing test.
    """
    taken = taken or {}

    def mine(ids: list[str]) -> list[str]:
        return sorted(t for t in ids if t not in taken)

    family = report_family(report)
    declared = declared_test_files(changed_paths)
    if declared:
        return (
            mine([t for t in report.outcomes if test_in_files(t, declared, family)]),
            f"the test files the task declared ({', '.join(declared[:5])})",
        )
    if family == "jvm":
        patterns = jvm_test_selection(argv)
        if not patterns:
            return None, ""
        return (
            mine([t for t in report.outcomes if _jvm_selected(t, patterns)]),
            f"the test classes the command selects ({', '.join(patterns[:5])})",
        )
    files = _named_files(argv, repo_root)
    if not files:
        return None, ""
    return (
        mine([t for t in report.outcomes if test_in_files(t, files, family)]),
        f"the test files the command names ({', '.join(files[:5])})",
    )


def restricted(report: TestReport, ids: list[str]) -> TestReport:
    """*report* with only *ids*."""
    keep = set(ids)
    return TestReport(
        report.source,
        {k: v for k, v in report.outcomes.items() if k in keep},
        {k: v for k, v in report.failures.items() if k in keep},
    )


def task_test_files(
    report: TestReport, changed_paths: list[str], argv: list[str], repo_root: Path
) -> list[str]:
    """The test files that hold the task's tests: those declared, or those the command names.
    A JVM class selected with `-Dtest=` is looked up under `src/test/<lang>/`."""
    declared = declared_test_files(changed_paths)
    if declared:
        return declared
    if report_family(report) != "jvm":
        return _named_files(argv, repo_root)
    named, _ = task_test_ids(report, changed_paths, argv, repo_root)
    found: set[str] = set()
    for test_id in named or []:
        prefix, cls = _jvm_id_class(test_id)
        for path in repo_root.glob(f"{prefix}src/test/*/{cls.replace('.', '/')}.*"):
            if path.suffix in JVM_TEST_SUFFIXES:
                found.add(path.relative_to(repo_root).as_posix())
    return sorted(found)


# --- regression and verification run the whole suite ---------------------------------------------
#
# Audit 2026-11-16 (df-evidence #4, df-gates "narrow verification"): regression and verification
# were judged by the exit code and by the tests the Change's own records name. A conftest that set
# the session's exit status to 0, or Maven's `-fn`, recorded "passed" over failing tests; a
# command narrowed to the task's own test file converged a Change that broke the rest of the suite.

# Audit 2026-11-17 (FE-8): the first form of this check refused the options known to select tests
# (`-k`, `--deselect`, `-Dtest=`, `-pl`, ...), so every option it did not know narrowed the suite
# unseen: Maven `-f b/pom.xml`, `-D test=`, `-Dsurefire.excludes`, `-DskipITs`, `-P`; pytest
# `--pyargs`, `-o testpaths=`, `-c`. It is the other way round now: what may be added to the suite
# command is what is listed here as leaving the suite whole, and anything else is refused. A
# product whose whole suite needs another option declares the command in `workflow.test_commands`.

# pytest: options without a value.
_PYTEST_HARMLESS_FLAGS = frozenset({
    "--exitfirst", "--showlocals", "--no-showlocals", "--no-header", "--no-summary", "--strict-markers",
    "--strict-config", "--strict", "--verbose", "--quiet", "--disable-warnings", "--disable-pytest-warnings",
    "--cache-clear", "--ff", "--failed-first", "--nf", "--new-first", "--full-trace", "--no-cov",
    "--cov-append", "--cov-branch", "--no-cov-on-fail", "--forked",
})
# pytest: options with a value (`--tb short`, `--tb=short`).
_PYTEST_HARMLESS_VALUES = frozenset({
    "--tb", "--durations", "--durations-min", "--maxfail", "--basetemp", "--junitxml", "--junit-xml",
    "--junit-prefix", "--color", "--code-highlight", "--capture", "--show-capture", "--import-mode",
    "--pythonwarnings", "--log-level", "--log-cli-level", "--log-file", "--log-file-level", "--log-format",
    "--log-date-format", "--cov", "--cov-report", "--cov-config", "--cov-fail-under", "--cov-context",
    "--timeout", "--timeout-method", "--dist", "--numprocesses", "--maxprocesses", "--maxschedchunk",
    "--verbosity", "--randomly-seed", "--reruns-delay",
})
_PYTEST_HARMLESS_SHORT_FLAGS = frozenset("qvsxl")
_PYTEST_HARMLESS_SHORT_VALUES = frozenset({"-W", "-n", "-r"})  # `-r` takes its letters attached: -ra
# `-o key=value`: only settings that change how the run is shown or logged.
_PYTEST_HARMLESS_INI = frozenset({
    "log_cli", "log_level", "log_cli_level", "log_format", "log_date_format", "log_file", "log_file_level",
    "console_output_style", "cache_dir", "faulthandler_timeout", "junit_logging", "junit_log_passing_tests",
    "junit_duration_report", "junit_suite_name", "tmp_path_retention_count", "tmp_path_retention_policy",
    "verbosity_assertions", "truncation_limit_lines", "truncation_limit_chars",
})

# Maven: the lifecycle phases; a `plugin:goal` or an execution id runs part of the build.
_MAVEN_PHASES = frozenset({
    "clean", "validate", "initialize", "generate-sources", "process-sources", "generate-resources",
    "process-resources", "compile", "process-classes", "generate-test-sources", "process-test-sources",
    "generate-test-resources", "process-test-resources", "test-compile", "process-test-classes", "test",
    "prepare-package", "package", "pre-integration-test", "integration-test", "post-integration-test",
    "verify", "install",
})
_MAVEN_HARMLESS_FLAGS = frozenset({
    "-o", "--offline", "-B", "--batch-mode", "-q", "--quiet", "-e", "--errors", "-X", "--debug", "--verbose",
    "-U", "--update-snapshots", "-V", "--show-version", "-ntp", "--no-transfer-progress", "-fae",
    "--fail-at-end", "-ff", "--fail-fast", "-fn", "--fail-never", "-C", "--strict-checksums", "-c",
    "--lax-checksums", "-nsu", "--no-snapshot-updates", "-up", "--update-plugins", "--no-plugin-updates",
})
_MAVEN_HARMLESS_VALUES = frozenset({
    "-T", "--threads", "-s", "--settings", "-gs", "--global-settings", "-t", "--toolchains",
    "-gt", "--global-toolchains", "-l", "--log-file", "--color", "-b", "--builder",
})
# `-Dname[=value]`: properties that do not choose which modules or tests run.
_MAVEN_HARMLESS_PROPERTIES = frozenset({
    "maven.repo.local", "style.color", "file.encoding", "project.build.sourceEncoding",
    "project.reporting.outputEncoding", "maven.test.failure.ignore", "testFailureIgnore", "trimStackTrace",
    "surefire.failIfNoSpecifiedTests", "failIfNoSpecifiedTests", "failIfNoTests", "surefire.failIfNoTests",
    "surefire.printSummary", "surefire.useFile", "surefire.reportFormat", "java.io.tmpdir", "user.timezone",
    "user.language", "user.country", "maven.javadoc.skip", "checkstyle.skip", "spotbugs.skip", "pmd.skip",
    "jacoco.skip", "enforcer.skip", "gpg.skip", "maven.source.skip", "license.skip", "spotless.check.skip",
})
_MAVEN_HARMLESS_PROPERTY_PREFIXES = ("maven.wagon.", "aether.", "jansi.", "org.slf4j.simpleLogger.", "http.", "https.")

# Gradle: the tasks that run every project's tests, and what builds them.
_GRADLE_TASKS = frozenset({"test", "check", "build", "clean", "cleanTest", "assemble", "classes", "testClasses"})
_GRADLE_HARMLESS_FLAGS = frozenset({
    "--no-daemon", "--daemon", "--offline", "--info", "-i", "--debug", "-d", "--quiet", "-q", "--warn", "-w",
    "--stacktrace", "-s", "--full-stacktrace", "-S", "--rerun", "--rerun-tasks", "--no-build-cache",
    "--build-cache", "--continue", "--parallel", "--no-parallel", "--no-configuration-cache",
    "--configuration-cache", "--no-watch-fs", "--watch-fs", "--refresh-dependencies", "--no-scan",
})
_GRADLE_HARMLESS_VALUES = frozenset({
    "--console", "--max-workers", "--warning-mode", "--priority", "-g", "--gradle-user-home",
    "--project-cache-dir", "--no-problems-report",
})
_GRADLE_HARMLESS_PROPERTY_PREFIXES = ("org.gradle.", "file.encoding", "user.timezone", "user.language", "user.country")


def _pytest_additions(args: list[str]) -> tuple[list[str], list[str]]:
    """(additions not known to leave the suite whole, test paths) among pytest's arguments."""
    unknown: list[str] = []
    positionals: list[str] = []
    i, n = 0, len(args)
    while i < n:
        arg = args[i]
        nxt = args[i + 1] if i + 1 < n else None
        i += 1
        if arg == "--":
            positionals += args[i:]
            break
        if not arg.startswith("-") or arg == "-":
            positionals.append(arg)
            continue
        if arg.startswith("--"):
            name, eq, value = arg.partition("=")
            if name in {"--override-ini"}:
                value, used = (value, 0) if eq else (nxt or "", 1)
                i += used
                if value.split("=", 1)[0].strip().lower() not in _PYTEST_HARMLESS_INI:
                    unknown.append(f"{name} {value}".strip())
            elif name in _PYTEST_HARMLESS_VALUES and (eq or name not in _PYTEST_HARMLESS_FLAGS):
                if not eq:
                    i += 1
            elif name in _PYTEST_HARMLESS_FLAGS and not eq:
                pass
            else:
                unknown.append(arg)
            continue
        # short options: `-q`, `-qx`, `-vv`, `-ra`, `-n 4`, `-n4`, `-W error`, `-p no:x`, `-o k=v`
        short, attached = arg[:2], arg[2:]
        if short in {"-p", "-o"}:
            value = attached or (nxt or "")
            if not attached:
                i += 1
            ok = value.startswith("no:") if short == "-p" else (
                value.split("=", 1)[0].strip().lower() in _PYTEST_HARMLESS_INI)
            if not ok:
                unknown.append(f"{short} {value}".strip())
        elif short in _PYTEST_HARMLESS_SHORT_VALUES:
            if not attached and short != "-r":
                i += 1
        elif set(arg[1:]) <= _PYTEST_HARMLESS_SHORT_FLAGS:
            pass
        else:
            unknown.append(arg if attached or nxt is None or nxt.startswith("-") else f"{arg} {nxt}")
    return unknown, positionals


def _maven_additions(args: list[str]) -> list[str]:
    unknown: list[str] = []
    i, n = 0, len(args)
    while i < n:
        arg = args[i]
        nxt = args[i + 1] if i + 1 < n else None
        i += 1
        if not arg.startswith("-"):
            if arg not in _MAVEN_PHASES:
                unknown.append(arg)
            continue
        if arg.startswith("-D") or arg == "--define" or arg.startswith("--define="):
            if arg in {"-D", "--define"}:
                prop, i = (nxt or ""), i + 1
            else:
                prop = arg[2:] if arg.startswith("-D") else arg.split("=", 1)[1]
            key = prop.split("=", 1)[0]
            if key not in _MAVEN_HARMLESS_PROPERTIES and not key.startswith(_MAVEN_HARMLESS_PROPERTY_PREFIXES):
                unknown.append(f"-D{prop}")
            continue
        name, eq, _value = arg.partition("=")
        if arg in _MAVEN_HARMLESS_FLAGS:
            continue
        if name in _MAVEN_HARMLESS_VALUES:
            if not eq:
                i += 1
            continue
        if arg.startswith("-T") and arg[2:3].isdigit():
            continue  # -T4, -T1C
        with_value = nxt is not None and not nxt.startswith("-") and nxt not in _MAVEN_PHASES and not eq
        unknown.append(f"{arg} {nxt}" if with_value else arg)
        if with_value:
            i += 1
    return unknown


def _gradle_additions(args: list[str]) -> list[str]:
    unknown: list[str] = []
    i, n = 0, len(args)
    while i < n:
        arg = args[i]
        nxt = args[i + 1] if i + 1 < n else None
        i += 1
        if not arg.startswith("-"):
            if arg not in _GRADLE_TASKS:
                unknown.append(arg)
            continue
        if arg.startswith("-D") and arg[2:].split("=", 1)[0].startswith(_GRADLE_HARMLESS_PROPERTY_PREFIXES):
            continue
        name, eq, _value = arg.partition("=")
        if arg in _GRADLE_HARMLESS_FLAGS:
            continue
        if name in _GRADLE_HARMLESS_VALUES:
            if not eq:
                i += 1
            continue
        with_value = nxt is not None and not nxt.startswith("-") and nxt not in _GRADLE_TASKS and not eq \
            and not arg.startswith(("-D", "-P"))
        unknown.append(f"{arg} {nxt}" if with_value else arg)
        if with_value:
            i += 1
    return unknown


_SUITE_SKIP_DIRS = frozenset({"node_modules", "__pycache__", "site-packages", "venv", "build", "dist", "target"})


def _configured_commands(repo_root: Path) -> list[list[str]]:
    from deltafuse.core.runners import _load_config_prefixes

    return [list(entry) for entry in _load_config_prefixes(repo_root)]


def _normalized(argv: list[str]) -> list[str]:
    """argv with the runner as its bare name (`.venv/Scripts/pytest.exe` -> `pytest`) and any
    spelling of pytest (`python -X utf8 -m pytest`, `uv run pytest`) read as `pytest`, so a
    declared command matches however it is spelled."""
    if not argv:
        return []
    start = pytest_args_start(argv)
    if start is not None:
        return ["pytest", *[str(a) for a in argv[start:]]]
    return [runner_head(argv[0]), *[str(a) for a in argv[1:]]]


def _pytest_testpaths(repo_root: Path) -> list[str] | None:
    """`testpaths` from the product's pytest configuration at its root, when it sets one."""
    import configparser

    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            paths = ((data.get("tool") or {}).get("pytest") or {}).get("ini_options", {}).get("testpaths")
            if paths:
                return [paths] if isinstance(paths, str) else [str(p) for p in paths]
        except (OSError, ValueError, AttributeError):
            pass
    for name, section in (("pytest.ini", "pytest"), (".pytest.ini", "pytest"), ("tox.ini", "pytest"),
                          ("setup.cfg", "tool:pytest")):
        path = repo_root / name
        if not path.is_file():
            continue
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        if parser.has_option(section, "testpaths"):
            return parser.get(section, "testpaths").split()
    return None


def _pytest_test_files(repo_root: Path, scope: list[str]) -> list[str]:
    """The pytest test files (`test_*.py`, `*_test.py`) under *scope*, POSIX, sorted."""
    import os

    found: list[str] = []
    for base in scope:
        top = repo_root / base
        if top.is_file():
            found.append(base)
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SUITE_SKIP_DIRS]
            for name in filenames:
                if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
                    found.append(Path(dirpath, name).relative_to(repo_root).as_posix())
    return sorted(set(found))


def suite_subset(command: object, repo_root: Path) -> str | None:
    """Why *command* may run only part of the product's suite; None when it runs the whole of it.

    A command the product declares in `workflow.test_commands` is the whole suite as written.
    What is added to it - or, without a declaration, everything after the runner - must be known
    to leave the suite whole (the lists above): an output or logging option, a lifecycle phase,
    a pytest directory that leaves no test file out. Anything else is refused, known or not.
    """
    argv = _command_argv(command)
    family = runner_family(argv)
    if not family:
        return None
    norm = _normalized(argv)
    declared = [_normalized(entry) for entry in _configured_commands(repo_root)]
    if norm in declared:
        return None
    base = max((d for d in declared if norm[: len(d)] == d), key=len, default=None)
    extra = norm[len(base):] if base is not None else norm[1:]
    how = (
        "declare the command with it in workflow.test_commands if that is the product's whole suite"
    )
    positionals: list[str] = []
    if family == "pytest":
        unknown, positionals = _pytest_additions(extra)
    elif runner_head(norm[0]) in {"gradle", "gradlew"}:
        unknown = _gradle_additions(extra)
    else:
        unknown = _maven_additions(extra)
    if unknown:
        shown = ", ".join(f"`{u}`" for u in unknown[:3])
        return (
            f"it adds {shown} to the suite command, and that is not known to leave the suite whole "
            f"(it selects part of the suite, or the Core cannot tell that it does not); {how}"
        )
    if not positionals:
        return None
    posix = [p.replace("\\", "/") for p in positionals]
    named = [p for p in posix if "::" in p or (repo_root / p).is_file()]
    if named:
        return f"it names single test files or tests ({', '.join(named[:3])}), not the suite"
    # A path that is not there selects nothing pytest would run (it exits 4 on one), and a
    # record whose tree lost a directory since is stale on its own account.
    dirs = [p.rstrip("/").removeprefix("./") for p in posix if (repo_root / p).exists()]
    if not dirs:
        return None
    if any(d in {".", ""} for d in dirs):
        return None
    scope = _pytest_testpaths(repo_root) or ["."]
    outside = [
        f for f in _pytest_test_files(repo_root, scope)
        if not any(f.startswith(d + "/") for d in dirs)
    ]
    if outside:
        return f"it leaves out test files of the suite ({', '.join(outside[:3])})"
    return None


def suite_errors(label: str, command: object, tests: object, repo_root: Path) -> list[str]:
    """What keeps a regression or verification run from showing the suite passes."""
    errors: list[str] = []
    if isinstance(tests, dict):
        failing = [str(t) for t in (tests.get(FAILED) or []) + (tests.get("not_run") or [])]
        if failing:
            errors.append(
                f"{label} is not evidence: {len(failing)} test(s) failed or did not run "
                f"({', '.join(failing[:5])}), whatever the exit code says - every test of the suite "
                "must pass. Fix what broke them and record it again"
            )
    narrowed = suite_subset(command, repo_root)
    if narrowed:
        errors.append(
            f"{label} is not evidence: {narrowed}. Regression and verification run the product's "
            "whole test suite"
            + (" as `workflow.test_commands` declares it" if _configured_commands(repo_root) else "")
            + "; record it again with the full command"
        )
    return errors
