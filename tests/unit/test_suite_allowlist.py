"""Regression and verification run the whole suite: what may be added to the suite command is a
list of options known to be harmless, not a list of options known to select.

Audit 2026-11-17 (FE-8): the check refused `-k`, `--deselect`, `-Dtest=`, `-pl` and a dozen others
by name, so every option not on that list narrowed the suite unseen: Maven `-f b/pom.xml`,
`-D test=`, `-Dsurefire.excludes`, `-DskipITs`, `-P`; pytest `--pyargs`, `-o testpaths=`, `-c`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.test_reports import suite_errors, suite_subset
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import (
    CALC_DONE,
    MAVEN_TIMEOUT,
    maven_turn,  # noqa: F401 - a fixture
    maven_module,
    mvn_available,
    pom,
    product,
    write,
)


def _declare(root: Path, command: str | None) -> Path:
    if command:
        write(root / ".deltafuse/config.yaml", f"workflow:\n  test_commands:\n    - {command}\n")
    for rel in ("tests/test_a.py", "tests/unit/test_b.py", "tests/integration/test_c.py"):
        write(root / rel, "def test_x():\n    assert True\n")
    write(root / "tests/unit/pytest.ini", "[pytest]\n")
    return root


PYTEST_NARROWING = [
    ["-k", "cooldown"], ["tests/test_a.py"], ["--deselect", "tests/test_a.py::test_x"],
    ["--pyargs", "tests.test_a"], ["-o", "python_files=test_a.py"], ["-o", "testpaths=tests/unit"],
    ["-c", "tests/unit/pytest.ini"], ["--rootdir", "tests/unit", "--collect-only"], ["--co"],
    ["--ignore-glob=*b*"], ["-o", "python_functions=test_ok*"], ["-o", "norecursedirs=integration"],
    # the same options in their other spellings, and their neighbours
    ["-opython_files=test_a.py"], ["--override-ini=testpaths=tests/unit"], ["-ctests/unit/pytest.ini"],
    ["--config-file=tests/unit/pytest.ini"], ["--rootdir=tests/unit"], ["-p", "tests.unit.plugin"],
    ["--lf"], ["--sw"], ["--setup-only"], ["--collect-only"], ["-m", "fast"], ["--ignore=tests/unit"],
    ["--confcutdir", "tests/unit"], ["--noconftest"], ["--import-mode=importlib", "--pyargs"],
    ["--some-plugin-option"], ["tests/unit"],
]


@pytest.mark.parametrize("declared", ["pytest", None])
@pytest.mark.parametrize("extra", PYTEST_NARROWING, ids=" ".join)
def test_pytest_additions_that_may_narrow_the_suite_are_refused(tmp_path: Path, declared, extra):
    why = suite_subset(["pytest", *extra], _declare(tmp_path, declared))
    assert why is not None


@pytest.mark.parametrize("declared", ["pytest", None])
@pytest.mark.parametrize("extra", [
    [], ["-q"], ["-qq", "-x"], ["-v", "-s"], ["-vv", "-ra"], ["-rfE", "--tb=short"], ["--tb", "line"],
    ["-p", "no:cacheprovider"], ["-pno:randomly"], ["-n", "auto"], ["-n4", "--dist", "loadfile"],
    ["--durations=10"], ["--maxfail", "3"], ["--basetemp", "tmp/x"], ["--junitxml=report.xml"],
    ["-W", "error"], ["--color=yes"], ["--strict-markers", "--strict-config"], ["--cov=src", "--cov-report", "xml"],
    ["--timeout=60"], ["-o", "log_cli=true"], ["--ff"], ["tests"], ["."], ["-q", "tests/"],
], ids=" ".join)
def test_pytest_additions_known_to_leave_the_suite_whole_are_accepted(tmp_path: Path, declared, extra):
    assert suite_subset(["pytest", *extra], _declare(tmp_path, declared)) is None


MAVEN_NARROWING = [
    ["-Dtest=CalcTest"], ["-pl", "b"], ["-f", "b/pom.xml"], ["--file", "b/pom.xml"], ["-D", "test=CalcTest"],
    ["-Dsurefire.excludes=**/CalcTest.java"], ["-DskipITs"], ["-Dtest.skip=true"], ["-Pfast"],
    ["-Dsurefire.failIfNoSpecifiedTests=false", "-Dgroups=fast"], ["-DexcludedGroups=slow"],
    # the same in other spellings, and their neighbours
    ["-P", "fast"], ["--activate-profiles=fast"], ["-N"], ["--non-recursive"], ["-rf", ":b"], ["-am"],
    ["-DskipTests"], ["-Dmaven.test.skip=true"], ["-D", "skipTests"], ["-Dit.test=CalcIT"],
    ["-Dsurefire.includesFile=only.txt"], ["-Dinclude=**/A*.java"], ["-Drevision=2"], ["surefire:test@fast"],
    ["--projects=b"], ["-fb/pom.xml"],
]


@pytest.mark.parametrize("extra", MAVEN_NARROWING, ids=" ".join)
def test_maven_additions_that_may_narrow_the_suite_are_refused(tmp_path: Path, extra):
    assert suite_subset(["mvn", "-B", "test", *extra], _declare(tmp_path, "mvn -B test")) is not None
    assert suite_subset(["mvn", "-B", "test", *extra], _declare(tmp_path / "plain", None)) is not None


@pytest.mark.parametrize("argv", [
    ["mvn", "test"], ["mvn", "-o", "-B", "-q", "test"], ["mvn", "-e", "-X", "-U", "-V", "-ntp", "verify"],
    ["mvn", "-fae", "-T", "4", "clean", "verify"], ["mvn", "-T1C", "test"], ["mvn", "-s", "ci/settings.xml", "test"],
    ["mvn", "-Dmaven.repo.local=/cache/m2", "-Dstyle.color=never", "test"], ["mvn", "-fn", "test"],
    ["mvn", "-D", "file.encoding=UTF-8", "clean", "install"], ["./mvnw", "--batch-mode", "--offline", "verify"],
], ids=" ".join)
def test_maven_commands_that_run_the_whole_build_are_accepted(tmp_path: Path, argv):
    assert suite_subset(argv, tmp_path) is None


@pytest.mark.parametrize("argv", [
    ["gradle", "test", "--tests", "demo.CalcTest"], ["gradle", ":b:test"], ["gradle", "test", "-x", "integrationTest"],
    ["./gradlew", "test", "-PexcludeSlow=true"], ["gradle", "-p", "b", "test"], ["gradle", "--project-dir=b", "test"],
    ["gradle", "test", "-Dtest.single=Calc"], ["gradle", "b:check"], ["gradle", "unitTest"], ["gradle", "test", "-b", "b/build.gradle"],
    ["gradle", "test", "--exclude-task", "check"], ["gradle", "test", "-Pfast"],
], ids=" ".join)
def test_gradle_additions_that_may_narrow_the_suite_are_refused(tmp_path: Path, argv):
    assert suite_subset(argv, tmp_path) is not None


@pytest.mark.parametrize("argv", [
    ["gradle", "test"], ["./gradlew", "clean", "test", "--no-daemon", "--rerun"], ["gradle", "check", "--info", "--stacktrace"],
    ["gradlew.bat", "test", "--offline", "--console=plain", "--continue"], ["gradle", "build", "--rerun-tasks", "-q"],
], ids=" ".join)
def test_gradle_commands_that_run_the_whole_build_are_accepted(tmp_path: Path, argv):
    assert suite_subset(argv, tmp_path) is None


def test_the_declared_command_is_the_suite_as_written_and_the_refusal_says_how_to_declare(tmp_path: Path):
    _declare(tmp_path, "mvn -B test -Pci -Dgroups=unit")
    assert suite_subset(["mvn", "-B", "test", "-Pci", "-Dgroups=unit"], tmp_path) is None
    assert suite_subset(["mvn.cmd", "-B", "test", "-Pci", "-Dgroups=unit", "-q"], tmp_path) is None
    errors = suite_errors("regression", ["mvn", "-B", "test", "-Pci", "-Dgroups=unit", "-f", "b/pom.xml"], None, tmp_path)
    assert len(errors) == 1
    assert "-f b/pom.xml" in errors[0] and "workflow.test_commands" in errors[0], errors


@pytest.mark.skipif(not mvn_available(), reason="needs Maven (offline) on PATH")
def test_a_regression_over_one_module_of_two_is_not_the_suite(tmp_path: Path, repo_root: Path, maven_turn):
    """The reproduction on real Maven: `-f b/pom.xml` appended to the declared command builds
    module b only, while Implement broke module a."""
    write(tmp_path / "pom.xml", pom("root", packaging="pom", modules=("a", "b")))
    maven_module(tmp_path, "a", artifact="a", parent="root", done=True)
    maven_module(tmp_path, "b", artifact="b", parent="root")
    declared = "mvn -o -B -q test"
    builder = product(
        tmp_path, repo_root,
        allowed=["b/src/main/java/demo/Calc.java", "b/src/test/java/demo/CalcTest.java", "a/src/main/java/demo/Calc.java"],
        workflow={"code_roots": ["a/src/**", "b/src/**"], "test_commands": [declared]},
    )
    paths = ["b/src/test/java/demo/CalcTest.java", "b/src/main/java/demo/Calc.java"]
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=[*declared.split(), "-Dtest=CalcTest"],
                       changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert red.authentic, red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    write(tmp_path / "b/src/main/java/demo/Calc.java", CALC_DONE)
    write(tmp_path / "a/src/main/java/demo/Calc.java", CALC_DONE.replace("return a + b;", "return 0;"))
    paths.append("a/src/main/java/demo/Calc.java")
    one_module = [*declared.split(), "-f", "b/pom.xml"]
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=one_module,
                       changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert reg.payload["exit_code"] == 0  # module b alone is green
    assert not reg.authentic
    assert any("-f b/pom.xml" in e for e in reg.errors), reg.errors
    ver = run_evidence(builder.change_dir, phase="verification", argv=one_module, changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert not ver.authentic
