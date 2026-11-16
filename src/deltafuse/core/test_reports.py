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


def runner_family(argv: list[str]) -> str:
    """`pytest`, `jvm`, or `` when the Core has no reader for this runner."""
    if not argv:
        return ""
    head = runner_head(argv[0])
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
    if runner_family(argv) != "pytest":
        return []
    start = 1 if runner_head(argv[0]) in PYTEST_RUNNERS else argv.index("pytest") + 1
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
    report: TestReport, changed_paths: list[str], argv: list[str], repo_root: Path
) -> tuple[list[str] | None, str]:
    """The report's tests that are the task's, and how they were named; (None, "") when nothing
    names them - no declared test file and no test file or class selected on the command line."""
    family = report_family(report)
    declared = declared_test_files(changed_paths)
    if declared:
        return (
            sorted(t for t in report.outcomes if test_in_files(t, declared, family)),
            f"the test files the task declared ({', '.join(declared[:5])})",
        )
    if family == "jvm":
        patterns = jvm_test_selection(argv)
        if not patterns:
            return None, ""
        return (
            sorted(t for t in report.outcomes if _jvm_selected(t, patterns)),
            f"the test classes the command selects ({', '.join(patterns[:5])})",
        )
    files = _named_files(argv, repo_root)
    if not files:
        return None, ""
    return (
        sorted(t for t in report.outcomes if test_in_files(t, files, family)),
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

# Options that run part of the suite: pytest's selection and Maven/Gradle's test and module filters.
_PYTEST_SELECTING = ("-k", "-m", "--deselect", "--ignore", "--ignore-glob", "--lf", "--last-failed",
                     "--sw", "--stepwise", "--sw-skip", "--stepwise-skip")
_JVM_SELECTING = ("-Dtest=", "-Dit.test=", "-Dgroups=", "-DexcludedGroups=", "-Dsurefire.includesFile=",
                  "-Dsurefire.excludesFile=", "-Dtest.single=", "--tests", "-pl", "--projects", "-rf",
                  "--resume-from", "-x", "--exclude-task")
_SUITE_SKIP_DIRS = frozenset({"node_modules", "__pycache__", "site-packages", "venv", "build", "dist", "target"})


def _configured_commands(repo_root: Path) -> list[list[str]]:
    from deltafuse.core.runners import _load_config_prefixes

    return [list(entry) for entry in _load_config_prefixes(repo_root)]


def _normalized(argv: list[str]) -> list[str]:
    """argv with the runner as its bare name (`.venv/Scripts/pytest.exe` -> `pytest`) and a
    `python -m pytest` read as `pytest`, so a declared command matches however it is spelled."""
    if not argv:
        return []
    head = runner_head(argv[0])
    if head in {"python", "python3"} and argv[1:3] == ["-m", "pytest"]:
        return ["pytest", *[str(a) for a in argv[3:]]]
    return [head, *[str(a) for a in argv[1:]]]


def _selecting_options(argv: list[str]) -> list[str]:
    family = runner_family(argv)
    out: list[str] = []
    for arg in argv[1:]:
        arg = str(arg)
        if family == "pytest":
            if any(arg == opt or arg.startswith(opt + "=") or (len(opt) == 2 and arg.startswith(opt) and len(arg) > 2)
                   for opt in _PYTEST_SELECTING):
                out.append(arg)
        elif family == "jvm":
            if any(arg == opt or arg.startswith(opt if opt.endswith("=") else opt + "=") for opt in _JVM_SELECTING):
                out.append(arg)
    return out


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
    """Why *command* runs only part of the product's suite; None when it runs the whole of it.

    A command the product declares in `workflow.test_commands` is the whole suite as written;
    anything added to it that selects tests narrows it. Without a declaration, a test-selecting
    option narrows the suite, and so does a pytest path that leaves test files out (a file or
    node id, or a directory with test files outside it).
    """
    argv = _command_argv(command)
    family = runner_family(argv)
    if not family:
        return None
    norm = _normalized(argv)
    declared = [_normalized(entry) for entry in _configured_commands(repo_root)]
    if norm in declared:
        return None
    base = next((d for d in declared if norm[: len(d)] == d), None)
    extra = norm[len(base):] if base is not None else norm[1:]
    selecting = _selecting_options([norm[0], *extra])
    if selecting:
        return f"it selects part of the suite ({' '.join(selecting[:3])})"
    if family != "pytest":
        return None
    positionals = pytest_positionals(["pytest", *extra], repo_root)
    if not positionals:
        return None
    named = [p for p in positionals if "::" in p or (repo_root / p).is_file()]
    if named:
        return f"it names single test files or tests ({', '.join(named[:3])}), not the suite"
    dirs = [p.rstrip("/").removeprefix("./") for p in positionals]
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
