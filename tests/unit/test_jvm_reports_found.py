"""The reports of a JVM build are read wherever its modules are.

Audit 2026-11-17 (FE-9): the Core looked for Surefire reports in `target/` and `*/target/`, and
for Failsafe reports in the root `target/` only. An integration test of a module was never read,
and a module two directories deep (`services/calc`) had no report at all: its honest Red was
"the runner reported no tests", with no documented way out.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from deltafuse.core import test_reports as reports
from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import (
    CALC_DONE,
    MAVEN_TIMEOUT,
    maven_module,
    maven_turn,  # noqa: F401 - a fixture
    mvn,
    mvn_available,
    pom,
    product,
    write,
)

needs_maven = pytest.mark.skipif(not mvn_available(), reason="needs Maven (offline) on PATH")
CASE = '<testsuite name="{cls}"><testcase name="adds" classname="{cls}"/></testsuite>'


def _xml(root: Path, rel: str, cls: str = "demo.CalcTest") -> Path:
    write(root / rel, CASE.format(cls=cls))
    return root / rel


@pytest.mark.parametrize("rel,test_id", [
    ("target/surefire-reports/TEST-demo.CalcTest.xml", "demo.CalcTest::adds"),
    ("target/failsafe-reports/TEST-demo.CalcTest.xml", "demo.CalcTest::adds"),
    ("b/target/surefire-reports/TEST-demo.CalcTest.xml", "b/demo.CalcTest::adds"),
    ("b/target/failsafe-reports/TEST-demo.CalcTest.xml", "b/demo.CalcTest::adds"),
    ("services/calc/target/surefire-reports/TEST-demo.CalcTest.xml", "services/calc/demo.CalcTest::adds"),
    ("services/calc/target/failsafe-reports/TEST-demo.CalcTest.xml", "services/calc/demo.CalcTest::adds"),
    ("build/test-results/test/TEST-demo.CalcTest.xml", "demo.CalcTest::adds"),
    ("apps/api/core/build/test-results/integrationTest/TEST-demo.CalcTest.xml", "apps/api/core/demo.CalcTest::adds"),
])
def test_a_report_is_read_from_any_module_of_the_build(tmp_path: Path, rel: str, test_id: str):
    _xml(tmp_path, rel)
    report = reports.read_report(["mvn", "verify"], tmp_path)
    assert report is not None and report.outcomes == {test_id: reports.PASSED}


def test_only_reports_of_this_run_and_of_the_product_are_read(tmp_path: Path):
    old = _xml(tmp_path, "a/target/surefire-reports/TEST-demo.OldTest.xml", "demo.OldTest")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    _xml(tmp_path, "node_modules/lib/target/surefire-reports/TEST-demo.LibTest.xml", "demo.LibTest")
    _xml(tmp_path, ".git/target/surefire-reports/TEST-demo.GitTest.xml", "demo.GitTest")
    _xml(tmp_path, "b/target/classes/target/surefire-reports/TEST-demo.CopyTest.xml", "demo.CopyTest")
    _xml(tmp_path, "services/calc/target/failsafe-reports/TEST-demo.CalcIT.xml", "demo.CalcIT")
    report = reports.read_report(["mvn", "verify"], tmp_path, newer_than=time.time() - 60)
    assert sorted(report.outcomes) == ["services/calc/demo.CalcIT::adds"]


def _cycle(builder, root: Path, module: str, test_class: str, goal: str):
    pre = f"{module}/" if module else ""
    test_rel, code_rel = f"{pre}src/test/java/demo/{test_class}.java", f"{pre}src/main/java/demo/Calc.java"
    paths = [test_rel, code_rel]
    select = [] if goal == "verify" else [f"-Dtest={test_class}"]
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=mvn(goal, *select),
                       changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert red.authentic, red.errors
    assert red.payload["tests"]["failed"] == [f"{pre}demo.{test_class}::adds"]
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    assert check_gate(builder.change_dir, "declaring") == []
    builder._core_advance("declaring")
    write(root / code_rel, CALC_DONE)
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=mvn(goal, *select),
                         changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert green.authentic, green.errors
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=mvn(goal),
                       changed_paths=paths, timeout=MAVEN_TIMEOUT)
    assert reg.authentic, reg.errors
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert check_gate(builder.change_dir, "implemented") == []
    return red, green, reg


@needs_maven
def test_the_honest_cycle_of_a_module_two_directories_deep(tmp_path: Path, repo_root: Path, maven_turn):
    write(tmp_path / "pom.xml", pom("root", packaging="pom", modules=("services/calc",)))
    maven_module(tmp_path, "services/calc", artifact="calc", parent="root", parent_rel="../../pom.xml")
    builder = product(tmp_path, repo_root, workflow={"code_roots": ["services/calc/src/**"]},
                      allowed=["services/calc/src/main/java/demo/Calc.java", "services/calc/src/test/java/demo/CalcTest.java"])
    _cycle(builder, tmp_path, "services/calc", "CalcTest", "test")


@needs_maven
def test_the_honest_cycle_of_a_failsafe_test_in_a_module(tmp_path: Path, repo_root: Path, maven_turn):
    write(tmp_path / "pom.xml", pom("root", packaging="pom", modules=("a", "b")))
    maven_module(tmp_path, "a", artifact="a", parent="root", done=True)
    maven_module(tmp_path, "b", artifact="b", parent="root", test_class="CalcIT", failsafe=True)
    builder = product(tmp_path, repo_root, workflow={"code_roots": ["a/src/**", "b/src/**"]},
                      allowed=["b/src/main/java/demo/Calc.java", "b/src/test/java/demo/CalcIT.java"])
    _red, _green, reg = _cycle(builder, tmp_path, "b", "CalcIT", "verify")
    assert sorted(reg.payload["tests"]["passed"]) == ["a/demo.CalcTest::adds", "b/demo.CalcIT::adds"]
