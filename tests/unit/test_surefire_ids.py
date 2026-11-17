"""A JVM test is named by its class and method, whatever it is displayed as.

Audit 2026-11-17 (FE-5): with a JUnit 5 `@DisplayName` on the class, Surefire writes the display
name into `classname`, so the honest Red of `demo.CalcTest` was reported as `Calculator::adds`,
matched no declared file and no `-Dtest=` pattern, and was refused `not-the-tasks-tests` with no
way out; a class with a display-named `@Nested` lost those failures. The class is the report's
`<testsuite name>` (Surefire writes one file per top-level class).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core import test_reports as reports
from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import (
    CALC_DONE,
    MAVEN_TIMEOUT,
    maven_turn,  # noqa: F401 - a fixture
    maven_module,
    mvn,
    mvn_available,
    product,
    write,
)

needs_maven = pytest.mark.skipif(not mvn_available(), reason="needs Maven (offline) on PATH")

# What Surefire 3.5.4 wrote for a class with @DisplayName("Calculator works"), a plain @Nested
# class and two display-named @Nested classes (real run, 2026-11-17).
SUREFIRE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="demo.CalcTest" tests="7" errors="0" skipped="0" failures="4">
  <testcase name="params(int)[1]" classname="Calculator works" time="0.047"><failure message="m" type="t">x</failure></testcase>
  <testcase name="params(int)[2]" classname="Calculator works" time="0.002"/>
  <testcase name="adds" classname="Calculator works" time="0.005"><error message="todo" type="java.lang.UnsupportedOperationException">x</error></testcase>
  <testcase name="named" classname="Calculator works" time="0.001"/>
  <testcase name="nested2" classname="named inner" time="0.005"/>
  <testcase name="nested" classname="demo.CalcTest$Inner" time="0.003"><failure message="m" type="t">x</failure></testcase>
  <testcase name="deep" classname="deep one" time="0.001"><failure message="m" type="t">x</failure></testcase>
</testsuite>
"""
TEST_REL = "src/test/java/demo/CalcTest.java"


def _report(root: Path, xml: str = SUREFIRE_XML, name: str = "demo.CalcTest", where: str = "target/surefire-reports"):
    write(root / where / f"TEST-{name}.xml", xml)
    return reports.read_report(["mvn", "test"], root)


def test_a_display_named_class_is_read_by_its_class_and_method(tmp_path: Path):
    report = _report(tmp_path)
    assert report.ids(reports.FAILED) == [
        "demo.CalcTest$Inner::nested", "demo.CalcTest::adds", "demo.CalcTest::deep", "demo.CalcTest::params(int)[1]",
    ]
    assert report.ids(reports.PASSED) == ["demo.CalcTest::named", "demo.CalcTest::nested2", "demo.CalcTest::params(int)[2]"]


def test_every_test_of_a_display_named_class_is_the_declared_files_and_the_selected_classes(tmp_path: Path):
    write(tmp_path / TEST_REL, "package demo;\nclass CalcTest {}\n")
    report = _report(tmp_path)
    declared, _ = reports.task_test_ids(report, [TEST_REL], ["mvn", "test"], tmp_path)
    assert declared == sorted(report.outcomes)
    selected, _ = reports.task_test_ids(report, [], ["mvn", "test", "-Dtest=CalcTest"], tmp_path)
    assert selected == sorted(report.outcomes)
    assert reports.task_test_files(report, [], ["mvn", "test", "-Dtest=CalcTest"], tmp_path) == [TEST_REL]


def test_two_display_named_classes_with_one_method_name_do_not_hide_a_failure(tmp_path: Path):
    """Both map to `demo.CalcTest::same`: the failure wins, in either order."""
    case = '<testcase name="same" classname="{c}">{body}</testcase>'
    failed = '<failure message="m" type="t">x</failure>'
    for first, second in ((failed, ""), ("", failed)):
        xml = ('<testsuite name="demo.CalcTest">' + case.format(c="first inner", body=first)
               + case.format(c="second inner", body=second) + "</testsuite>")
        assert _report(tmp_path, xml).outcomes == {"demo.CalcTest::same": reports.FAILED}


def test_a_real_class_reported_inside_another_suite_keeps_its_name(tmp_path: Path):
    """A JUnit 4 suite class reports the tests of the classes it runs under their own names."""
    write(tmp_path / "src/test/java/demo/OtherTest.java", "package demo;\npublic class OtherTest {}\n")
    xml = ('<testsuite name="demo.AllTests"><testcase name="adds" classname="demo.OtherTest"/>'
           '<testcase name="x" classname="Other"/></testsuite>')
    assert sorted(_report(tmp_path, xml, name="demo.AllTests").outcomes) == ["demo.AllTests::x", "demo.OtherTest::adds"]


def test_a_class_level_failure_under_a_display_name_is_still_a_class_that_never_ran(tmp_path: Path):
    xml = ('<testsuite name="demo.CalcTest"><testcase name="" classname="Calculator works">'
           '<error message="boom" type="java.lang.IllegalStateException">x</error></testcase></testsuite>')
    assert _report(tmp_path, xml).outcomes == {"demo.CalcTest::": reports.NOT_RUN}


def test_the_class_of_a_test_file_is_what_the_file_says_not_where_it_is(tmp_path: Path):
    """The neighbouring hard-coded path: the package was derived from `src/test/<lang>/`."""
    rel = "app/java/tests/CalcTest.java"  # a test source directory of the product's own choosing
    write(tmp_path / rel, "// header\npackage demo.calc;\n\nimport org.junit.jupiter.api.Test;\nclass CalcTest {}\n")
    report = reports.TestReport("surefire", {"demo.calc.CalcTest::adds": reports.FAILED, "demo.OtherTest::x": reports.FAILED})
    ids, _ = reports.task_test_ids(report, [rel], ["mvn", "test"], tmp_path)
    assert ids == ["demo.calc.CalcTest::adds"]
    kt = "src/test/kotlin/demo/CalcTests.kt"
    write(tmp_path / kt, "package demo\n\nclass CalcTest {\n}\n\nclass OtherTest\n")  # Kotlin: file name != class
    ids, _ = reports.task_test_ids(report, [kt], ["gradle", "test"], tmp_path)
    assert ids == ["demo.OtherTest::x"]


# --- real Maven ---------------------------------------------------------------------------------

DISPLAY_NAMED = '''package demo;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.assertEquals;
@DisplayName("Калькулятор")
class CalcTest {
    @Test void adds() { assertEquals(5, new Calc().add(2, 3)); }
    @Test @DisplayName("складывает два числа") void named() { assertEquals(5, new Calc().add(2, 3)); }
    @ParameterizedTest @ValueSource(ints = {1, 2}) void params(int x) { assertEquals(x + 1, new Calc().add(x, 1)); }
    @Nested class Inner { @Test void nested() { assertEquals(2, new Calc().add(1, 1)); } }
    @Nested @DisplayName("вложенный с именем") class Named { @Test void deep() { assertEquals(4, new Calc().add(2, 2)); } }
}
'''
CODE_REL = "src/main/java/demo/Calc.java"


def _display_named_product(tmp_path: Path, repo_root: Path):
    maven_module(tmp_path)
    write(tmp_path / TEST_REL, DISPLAY_NAMED)
    return product(tmp_path, repo_root, allowed=[CODE_REL, TEST_REL])


@needs_maven
@pytest.mark.parametrize("changed", [[TEST_REL, CODE_REL], [CODE_REL]], ids=["declared-file", "selected-class"])
def test_the_honest_cycle_of_a_display_named_junit5_class(tmp_path: Path, repo_root: Path, changed, maven_turn):
    builder = _display_named_product(tmp_path, repo_root)
    argv = mvn("test", "-Dtest=CalcTest*")
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=argv, changed_paths=changed,
                       timeout=MAVEN_TIMEOUT)
    assert red.authentic, red.errors
    failed = red.payload["tests"]["failed"]
    assert "demo.CalcTest::adds" in failed and "demo.CalcTest$Inner::nested" in failed and "demo.CalcTest::deep" in failed
    assert len(failed) == 6, failed
    assert [f["path"] for f in red.payload["red_oracle_tests"]["files"]] == [TEST_REL]
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    assert check_gate(builder.change_dir, "declaring") == []
    builder._core_advance("declaring")
    write(tmp_path / CODE_REL, CALC_DONE)
    paths = [TEST_REL, CODE_REL]
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=argv, changed_paths=paths,
                         timeout=MAVEN_TIMEOUT)
    assert green.authentic, green.errors
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=mvn("test"), changed_paths=paths,
                       timeout=MAVEN_TIMEOUT)
    assert reg.authentic, reg.errors
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert check_gate(builder.change_dir, "implemented") == []
