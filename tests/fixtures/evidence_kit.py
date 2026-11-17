"""A product with a decomposed Change, for tests that record real evidence (audit 2026-11-17).

`product()` installs the framework into a directory and walks a Change to `decomposed`;
`pytest_argv()` is the runner the Core reads reports of. The Maven half (`mvn_available`,
`maven_module`) writes a JUnit 5 module built with the plugins of the offline local repository.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

MAVEN_TIMEOUT = 300


def pytest_argv(*targets: str) -> list[str]:
    return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *targets]


def product(
    root: Path,
    repo_root: Path,
    *,
    change_id: str = "CHG-900",
    tasks: tuple | list = ("TASK-001",),
    allowed: list[str] | None = None,
    workflow: dict | None = None,
) -> MockChangeBuilder:
    install(target_dir=root, framework_root=repo_root)
    if workflow:
        cfg_path = root / ".deltafuse" / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        cfg.setdefault("workflow", {}).update(workflow)
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    spec: list[dict] = []
    for task in tasks:
        row = dict(task) if isinstance(task, dict) else {"id": task}
        row.setdefault("slice", "SLICE-01")
        row.setdefault("depends_on", [])
        if allowed and "allowed_paths" not in row:
            row["allowed_paths"] = allowed
        spec.append(row)
    return (
        MockChangeBuilder(root, change_id=change_id, title="Evidence kit")
        .step_intake().step_analyze().step_specify().step_decompose(spec)
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def only(errors: list[str], *needles: str) -> list[str]:
    return [e for e in errors if any(n in e for n in needles)]


def git_init(root: Path, *, autocrlf: str = "false") -> None:
    for args in (
        ("init", "-q"),
        ("config", "user.email", "kit@example.invalid"),
        ("config", "user.name", "kit"),
        ("config", "core.autocrlf", autocrlf),
        ("add", "-A"),
        ("commit", "-q", "-m", "base", "--no-verify"),
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


# --- Maven -------------------------------------------------------------------------------------

def mvn_available() -> bool:
    return shutil.which("mvn") is not None


def mvn(*args: str) -> list[str]:
    return ["mvn", "-o", "-B", "-q", *args]


_POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  {parent}
  <groupId>demo</groupId><artifactId>{artifact}</artifactId><version>1.0</version>
  <packaging>{packaging}</packaging>
  <properties>
    <maven.compiler.source>17</maven.compiler.source><maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  {modules}
  <dependencies>
    <dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.12.2</version><scope>test</scope></dependency>
  </dependencies>
  <build><plugins>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.5.4</version></plugin>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.14.1</version></plugin>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-resources-plugin</artifactId><version>3.3.1</version></plugin>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-jar-plugin</artifactId><version>3.4.1</version></plugin>
    {failsafe}
  </plugins></build>
</project>
"""
_FAILSAFE = (
    "<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-failsafe-plugin</artifactId>"
    "<version>3.5.4</version><executions><execution><goals><goal>integration-test</goal><goal>verify</goal>"
    "</goals></execution></executions></plugin>"
)
CALC_STUB = 'package demo;\npublic class Calc { public int add(int a, int b) { throw new UnsupportedOperationException("todo"); } }\n'
CALC_DONE = "package demo;\npublic class Calc { public int add(int a, int b) { return a + b; } }\n"
CALC_TEST = (
    "package demo;\nimport org.junit.jupiter.api.Test;\n"
    "import static org.junit.jupiter.api.Assertions.assertEquals;\n"
    "class {name} {{ @Test void adds() {{ assertEquals(5, new Calc().add(2, 3)); }} }}\n"
)


def pom(artifact: str = "demo", *, packaging: str = "jar", modules: tuple = (),
        parent: str | None = None, parent_rel: str = "../pom.xml", failsafe: bool = False) -> str:
    mods = "<modules>" + "".join(f"<module>{m}</module>" for m in modules) + "</modules>" if modules else ""
    par = (f"<parent><groupId>demo</groupId><artifactId>{parent}</artifactId><version>1.0</version>"
           f"<relativePath>{parent_rel}</relativePath></parent>") if parent else ""
    return _POM.format(artifact=artifact, packaging=packaging, modules=mods, parent=par,
                       failsafe=_FAILSAFE if failsafe else "")


def maven_module(root: Path, rel: str = "", *, artifact: str = "demo", parent: str | None = None,
                 parent_rel: str = "../pom.xml", done: bool = False, test_class: str = "CalcTest",
                 failsafe: bool = False) -> None:
    """A module with `demo.Calc` (a stub that throws unless *done*) and one JUnit 5 test of it."""
    base = root / rel if rel else root
    write(base / "pom.xml", pom(artifact, parent=parent, parent_rel=parent_rel, failsafe=failsafe))
    write(base / "src/main/java/demo/Calc.java", CALC_DONE if done else CALC_STUB)
    write(base / f"src/test/java/demo/{test_class}.java", CALC_TEST.format(name=test_class))


@pytest.fixture
def maven_turn():
    """One Maven build at a time, also across pytest-xdist workers: the builds share the local
    repository and the machine. A lock directory in the temp folder; a lock older than 20 minutes
    is a crashed run's and is taken over."""
    lock = Path(tempfile.gettempdir()) / "deltafuse-tests-maven.lock"
    deadline = time.time() + 1800
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 1200:
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise
            time.sleep(0.5)
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass
