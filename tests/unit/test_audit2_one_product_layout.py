"""Audit 2026-11-17, S2 at the merge: the leash reads the product's layout where the Red freeze,
stale evidence and the context budget read it - `core/product_layout.py`.

The evidence branch made `ProductLayout`; the leash branch tightened the leash's own lists (owner's
decision R5). Merged, there were two definitions again: the leash's exemptions, its guarded globs,
and an envelope that told the test side by the literal prefix `tests`. Here: one definition, R5
not weakened, a bare file name as a code root (`pom.xml`), and an honest Change on a Maven
product walked through Red, Green and the gates under `leash: enforce`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core import leash as leash_mod
from deltafuse.core import product_layout as layout_mod
from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.leash_run import run_leash
from deltafuse.core.product_layout import ProductLayout, product_layout
from deltafuse.core.queue import WorkItem
from deltafuse.core.transitions import advance_change, set_artifact_status
from tests.fixtures.evidence_kit import (
    CALC_DONE,
    MAVEN_TIMEOUT,
    maven_module,
    maven_turn,  # noqa: F401 - a fixture
    mvn,
    mvn_available,
    product,
    write,
)

needs_maven = pytest.mark.skipif(not mvn_available(), reason="needs Maven (offline) on PATH")

# Owner's decision R5: the whole list of what the leash does not judge.
R5_EXEMPT = [
    ".deltafuse/tmp/task.json", ".deltafuse/lock.yaml", "docs/intake/source.md", "docs/archive/intake/source.md",
    "docs/archive/changes/CHG-001/change.yaml", "AGENTS.md", ".git/config",
    "src/__pycache__/app.cpython-314.pyc", "tests/.pytest_cache/v/cache/lastfailed", ".pytest_cache/README.md",
]
R5_JUDGED = [
    "pom.xml", "conftest.py", "README.md", "README.ru.md", "CHANGELOG.md", ".gitignore", "agents.md",
    ".github/workflows/deltafuse-leash.yml", "docs/guide.md", "docs/spec/core.md", "docs/changes/CHG-001/change.yaml",
    # FW-17: not a cache, although it lies where caches do.
    "src/__pycache__/payload.py", "src/stray.pyc", "src/.pytest_cache/evil.py", "src/app.class",
    # What the layout leaves out of the hashed tree is still judged: the leash is not the hash.
    "target/classes/demo/Calc.class", "node_modules/lib/index.js", ".venv/bin/python", "src/pkg.egg-info/PKG-INFO",
    "docs/intake/../../src/app.py",
]


# --- one definition -------------------------------------------------------------------------

@pytest.mark.parametrize("rel", R5_EXEMPT)
def test_the_exempt_list_is_the_layouts(rel: str):
    assert ProductLayout(root=None).is_exempt(rel) and leash_mod.is_exempt_path(rel)


@pytest.mark.parametrize("rel", R5_JUDGED)
def test_everything_else_is_judged(rel: str, tmp_path: Path):
    """R5 is not weakened by the layout's wider notion of what is not hashed (`is_excluded`)."""
    write(tmp_path / "pom.xml", "<project/>")  # `target/` beside it is a build directory for the hash
    layout = ProductLayout(root=tmp_path)
    assert not layout.is_exempt(rel) and not leash_mod.is_exempt_path(rel)


def test_the_leash_keeps_no_lists_of_its_own(monkeypatch):
    for name in ("EXEMPT_EXACT", "EXEMPT_GLOBS", "_CACHE_FILE", "CODE_WRITE_GLOBS"):
        assert not hasattr(leash_mod, name), name
    monkeypatch.setattr(layout_mod, "EXEMPT_EXACT", frozenset({"AGENTS.md", "NOTES.md"}))
    assert leash_mod.is_exempt_path("NOTES.md")


def test_the_guarded_globs_are_the_layouts(tmp_path: Path):
    assert leash_mod.code_and_ops_globs(None) == ("src/**", "tests/**", "deploy/**", "docs/ops/**", "ops/**")
    write(tmp_path / ".deltafuse/config.yaml", "workflow:\n  code_roots: ['svc/src/**', 'pom.xml']\n")
    layout = product_layout(tmp_path)
    assert leash_mod.code_and_ops_globs(tmp_path) == layout.guarded_globs()
    assert layout.guarded_globs() == ("svc/src/**", "pom.xml", "deploy/**", "docs/ops/**", "ops/**")
    for rel, guarded in [("pom.xml", True), ("svc/src/main/App.java", True), ("ops/run.sh", True),
                         ("src/app.py", False), ("svc/pom.xml", False), ("README.md", False)]:
        assert layout.is_guarded(rel) is guarded, rel
        assert leash_mod.is_product_path(rel, product_root=tmp_path) is guarded, rel
    # The specification is the product's once the baseline is accepted.
    assert not leash_mod.is_product_path("docs/spec/core.md", baseline="draft", product_root=tmp_path)
    assert leash_mod.is_product_path("docs/spec/core.md", baseline="accepted", product_root=tmp_path)
    # A guarded path is guarded whatever the hash leaves out (FW-17).
    assert layout.is_guarded("svc/src/__pycache__/payload.py") and not layout.is_code("svc/src/__pycache__/payload.py")


# --- a bare file name as a code root ----------------------------------------------------------

def test_a_file_is_a_code_root(tmp_path: Path, repo_root: Path, capsys):
    builder = product(tmp_path, repo_root, workflow={"code_roots": ["src/**", "pom.xml"]},
                      allowed=["src/main/java/demo/Calc.java", "pom.xml"])
    write(tmp_path / "pom.xml", "<project/>\n")
    write(tmp_path / "src/main/java/demo/Calc.java", "class Calc {}\n")
    write(tmp_path / "svc/pom.xml", "<project/>\n")
    assert main(["validate-config", str(tmp_path)]) == 0, capsys.readouterr()
    layout = product_layout(tmp_path)
    assert layout.is_code("pom.xml") and not layout.is_code("svc/pom.xml") and not layout.is_test("pom.xml")
    assert layout.code_files() == ["pom.xml", "src/main/java/demo/Calc.java"]
    before = compute_product_baseline_revision(tmp_path)
    write(tmp_path / "pom.xml", "<project><!-- a dependency --></project>\n")
    assert compute_product_baseline_revision(tmp_path) != before  # the build file is in the hashed tree
    assert builder.change_dir.is_dir()


def test_a_bare_directory_is_still_not_a_code_root(tmp_path: Path, repo_root: Path, capsys):
    """The twin: `src` names no file under it for any reader, so the config is refused."""
    product(tmp_path, repo_root, workflow={"code_roots": ["src"]})
    write(tmp_path / "src/app.py", "x = 1\n")
    assert main(["validate-config", str(tmp_path)]) != 0
    assert "code_roots" in "".join(capsys.readouterr())


# --- the envelope tells the test side by the layout ------------------------------------------

def _declare_envelope(root: Path, builder) -> list[str]:
    home = builder.change_dir.relative_to(root).as_posix()
    item = WorkItem(kind="ready", step="declare", skill="declare", gate="declaring", change_id="CHG-900",
                    path=home, task="TASK-001", task_path=f"{home}/tasks/TASK-001.md", reason="test")
    return leash_mod.envelope_write_globs(item, root)


@pytest.mark.parametrize("roots,test_root,stub", [
    (None, "tests/**", "src/calc.py"),
    (["svc/src/**", "svc/tests/**"], "svc/tests/**", "svc/src/calc.py"),
    (["app/**", "app/src/test/**"], "app/src/test/**", "app/calc.py"),
])
def test_declare_opens_the_test_roots_and_the_tasks_stub(tmp_path: Path, repo_root: Path, roots, test_root, stub):
    """`tests/**` was told by its spelling: under `svc/tests/**` Declare could write no test the
    task had not listed, while under the default layout it writes any."""
    builder = product(tmp_path, repo_root, workflow={"code_roots": roots} if roots else None, allowed=[stub])
    globs = _declare_envelope(tmp_path, builder)
    assert test_root in globs and stub in globs, globs
    code_only = [g for g in (roots or ["src/**", "tests/**"]) if g != test_root]
    assert not set(code_only) & set(globs), globs  # Declare does not open the code roots


def test_a_root_holding_code_and_tests_opens_only_what_the_task_names(tmp_path: Path, repo_root: Path):
    """The Maven layout, one root `src/**`: Declare writes the task's own paths, the test included."""
    paths = ["src/main/java/demo/Calc.java", "src/test/java/demo/CalcTest.java"]
    builder = product(tmp_path, repo_root, workflow={"code_roots": ["src/**", "pom.xml"]}, allowed=paths)
    globs = _declare_envelope(tmp_path, builder)
    assert set(paths) <= set(globs) and "src/**" not in globs and "pom.xml" not in globs, globs


# --- what the stricter exemptions mean for evidence -------------------------------------------

def test_a_dirty_file_outside_the_code_roots_is_named_for_what_it_is(tmp_path: Path, repo_root: Path):
    """`deltafuse evidence` takes the leash's exemptions for the paths the Worker answers for.
    Since R5 a dirty `README.md` or un-ignored build output is among them; the refusal said what
    Red may write, which is no help for a file that is not the task's at all. Real caches and
    what git ignores stay out."""
    from tests.fixtures.evidence_kit import git_init, pytest_argv

    builder = product(tmp_path, repo_root, allowed=["src/calc.py", "tests/test_calc.py"])
    write(tmp_path / ".gitignore", "target/\n")
    git_init(tmp_path)
    write(tmp_path / "tests/test_calc.py", "def test_x():\n    assert False\n")
    write(tmp_path / "tests/__pycache__/test_calc.cpython-314.pyc", "cache")
    write(tmp_path / "target/classes/A.class", "ignored build output")
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=pytest_argv("tests/test_calc.py"))
    assert red.authentic and red.payload["changed_paths"] == ["tests/test_calc.py"], red.errors

    write(tmp_path / "README.md", "edited\n")
    write(tmp_path / "build/out.bin", "un-ignored build output")
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=pytest_argv("tests/test_calc.py"))
    assert not red.authentic
    for rel in ("README.md", "build/out.bin"):
        named = [e for e in red.errors if f"'{rel}'" in e]
        assert named and "outside the product's code roots (src/**, tests/**)" in named[0], red.errors
        assert ".gitignore" in named[0] and "Red writes tests" not in named[0]


# --- an honest Change on a Maven product ------------------------------------------------------

def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root, capture_output=True, text=True)


def _commit(root: Path, label: str) -> None:
    """Through the pre-commit hook: under enforce a violation refuses the commit."""
    _git(root, "add", "-A")
    proc = _git(root, "commit", "-q", "-m", label)
    assert proc.returncode == 0, f"{label}: {proc.stdout}\n{proc.stderr}"


def _clean(root: Path) -> None:
    payload = run_leash(root)
    assert payload["violations"] == [], payload["violations"]


@needs_maven
def test_an_honest_change_on_a_maven_product_passes_under_enforce(tmp_path: Path, repo_root: Path, maven_turn, monkeypatch):
    """pom.xml is a code root, `target/` is ignored, the paths are the ones git reports: Red,
    Green, regression and the gates pass, the leash is clean and every commit passes the hook."""
    from deltafuse.core.installer import install

    monkeypatch.delenv("CI", raising=False)
    code, test, build = "src/main/java/demo/Calc.java", "src/test/java/demo/CalcTest.java", "pom.xml"
    root = tmp_path / "svc"
    root.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "kit@example.invalid"),
                 ("config", "user.name", "kit"), ("config", "core.autocrlf", "false")):
        assert _git(root, *args).returncode == 0
    maven_module(root, done=False)
    (root / test).unlink()  # the task's test is written in Declare
    builder = product(root, repo_root, workflow={"code_roots": ["src/**", "pom.xml"], "leash": "enforce"},
                      allowed=[code, test, build])
    install(target_dir=root, framework_root=repo_root)  # the hook, now that the mode is enforce
    ignore = root / ".gitignore"
    ignore.write_text(ignore.read_text(encoding="utf-8") + "target/\n", encoding="utf-8", newline="\n")
    change = builder.change_dir
    _git(root, "add", "-A")
    assert _git(root, "commit", "-q", "--no-verify", "-m", "decomposed").returncode == 0
    assert yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"] == "decomposed"

    # Declare
    maven_module(root, done=False)  # writes the test (and the same stub and pom)
    red = run_evidence(change, phase="red", task="TASK-001", argv=mvn("test", "-Dtest=CalcTest"), timeout=MAVEN_TIMEOUT)
    assert red.authentic, red.errors
    assert (root / "target").is_dir()
    assert red.payload["changed_paths"] == [test], red.payload["changed_paths"]  # no build output, no cache
    set_artifact_status(change, status="declared", task_id="TASK-001")
    _clean(root)
    advance_change(change, "declaring")
    _commit(root, "declared")

    # Implement: the code and the build file, both the task's
    write(root / code, CALC_DONE)
    pom = root / build
    pom.write_text(pom.read_text(encoding="utf-8").replace("</properties>", "<demo.note>x</demo.note></properties>"),
                   encoding="utf-8", newline="\n")
    green = run_evidence(change, phase="green", task="TASK-001", argv=mvn("test", "-Dtest=CalcTest"), timeout=MAVEN_TIMEOUT)
    assert green.authentic, green.errors
    assert sorted(green.payload["changed_paths"]) == sorted([code, build])
    regression = run_evidence(change, phase="regression", task="TASK-001", argv=mvn("test"), timeout=MAVEN_TIMEOUT)
    assert regression.authentic, regression.errors
    set_artifact_status(change, status="implemented", task_id="TASK-001")
    assert check_gate(change, "implemented") == []
    _clean(root)
    result = advance_change(change, "implemented")
    assert result["leash"]["checked"] and result["leash"]["violations"] == [], result["leash"]
    _commit(root, "implemented")

    # The same build file outside a task is the product's, and refused (R5 stands).
    pom.write_text(pom.read_text(encoding="utf-8") + "<!-- by hand -->\n", encoding="utf-8", newline="\n")
    assert any("pom.xml" in v for v in run_leash(root)["violations"])
