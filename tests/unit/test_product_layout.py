"""One layout of the product for the Red freeze, stale evidence and the context budget.

Audit 2026-11-17, S2 (FE-2, FE-4): each of the three knew its own list of directories beside
`workflow.code_roots`. A product that keeps code in `app/**` froze no Red oracle (a weakened
assertion closed `implemented`), and its evidence never went stale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.context import validate_task_context_budget
from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.hasher import compute_product_baseline_revision, compute_red_oracle_digest
from deltafuse.core.product_layout import ProductLayout, product_layout
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.evidence_kit import only, product, pytest_argv, write


# --- the layout itself --------------------------------------------------------------------------

def test_code_roots_come_from_the_config_or_the_defaults(tmp_path: Path):
    assert product_layout(tmp_path).code_roots == ("src/**", "tests/**")
    write(tmp_path / ".deltafuse/config.yaml", "workflow:\n  code_roots: ['app/**', 'test/**']\n")
    layout = product_layout(tmp_path)
    assert layout.code_roots == ("app/**", "test/**") and layout.configured
    assert layout.is_code("app/limiter.py") and not layout.is_code("src/limiter.py")


@pytest.mark.parametrize("rel", [
    "tests/test_x.py", "tests/data/rates.json", "tests/conftest.py", "test/test_x.py", "app/test_x.py",
    "app/x_test.py", "app/conftest.py", "src/test/java/demo/CalcTest.java", "svc/src/test/resources/a.yml",
    "services/calc/src/test/java/demo/Calc.java", "svc/src/integrationTest/java/demo/Flow.java",
    "app/java/demo/CalcTest.java", "app/demo/CalcIT.kt", "web/cart.test.ts", "pkg/cart_test.go",
])
def test_a_test_is_a_test_wherever_it_is(rel: str):
    assert ProductLayout(root=None).is_test(rel)


@pytest.mark.parametrize("rel", [
    "src/limiter.py", "app/contest.py", "src/main/java/demo/Calc.java", "app/latest/report.py",
    "src/main/java/demo/Testimony.java", "tests/__pycache__/test_x.cpython-314.pyc", ".deltafuse/tmp/test_x.py",
])
def test_product_code_and_caches_are_not_tests(rel: str):
    assert not ProductLayout(root=None).is_test(rel)


def test_a_build_directory_is_excluded_only_beside_its_build_file(tmp_path: Path):
    write(tmp_path / "svc/pom.xml", "<project/>")
    write(tmp_path / "svc/target/classes/demo/Calc.java", "x")
    write(tmp_path / "svc/src/main/java/demo/Calc.java", "x")
    write(tmp_path / "src/build/steps.py", "x = 1\n")  # a package named `build`, no Gradle beside it
    write(tmp_path / "src/target/aim.py", "x = 1\n")
    write(tmp_path / "src/__pycache__/steps.cpython-314.pyc", "x")
    write(tmp_path / "src/node_modules/lib/index.js", "x")
    layout = ProductLayout(root=tmp_path, code_roots=("svc/**", "src/**"))
    assert layout.code_files() == ["src/build/steps.py", "src/target/aim.py", "svc/pom.xml",
                                   "svc/src/main/java/demo/Calc.java"]


def test_the_cores_own_bookkeeping_is_never_product_code(tmp_path: Path):
    """A product whose code root is the repository itself still has a stable tree."""
    write(tmp_path / "main.py", "x = 1\n")
    write(tmp_path / "docs/changes/CHG-001/evidence/green/TASK-001.yaml", "x: 1\n")
    write(tmp_path / "docs/archive/CHG-000/change.yaml", "x: 1\n")
    write(tmp_path / ".deltafuse/journal/transitions.jsonl", "{}\n")
    assert ProductLayout(root=tmp_path, code_roots=("**",)).code_files() == ["main.py"]


# --- FE-2: the Red oracle is frozen wherever the test file is -------------------------------------

def _limiter(tmp_path: Path, repo_root: Path, code_rel: str, test_rel: str, workflow: dict | None):
    builder = product(tmp_path, repo_root, allowed=[code_rel, test_rel], workflow=workflow)
    write(tmp_path / code_rel, "def cooldown():\n    return 0\n")
    head = f"import sys\nsys.path.insert(0, {str(Path(code_rel).parent.as_posix())!r})\nfrom limiter import cooldown\n\n\n"
    write(tmp_path / test_rel, head + "def test_cooldown():\n    assert cooldown() >= 30\n")
    return builder, head


@pytest.mark.parametrize("test_rel", ["app/test_limiter.py", "test/test_limiter.py", "app/checks.py"])
def test_red_freezes_a_test_outside_tests_and_a_rewritten_oracle_is_refused(tmp_path: Path, repo_root: Path, test_rel: str):
    """`app/checks.py` is the bypass: no test directory, no test name - the command names the file."""
    builder, head = _limiter(tmp_path, repo_root, "app/limiter.py", test_rel, {"code_roots": ["app/**", "test/**"]})
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=pytest_argv(test_rel), changed_paths=[test_rel])
    assert red.authentic, red.errors
    frozen = red.payload.get("red_oracle_tests")
    assert frozen and [t["path"] for t in frozen["tests"]] == [test_rel]
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    # Implement rewrites the oracle instead of the product.
    write(tmp_path / test_rel, head + "def test_cooldown():\n    assert cooldown() >= 0\n")
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=pytest_argv(test_rel), changed_paths=[test_rel])
    assert not green.authentic
    assert only(green.errors, "frozen Red oracle"), green.errors
    run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=pytest_argv(test_rel.split("/")[0]),
                 changed_paths=[test_rel])
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert only(check_gate(builder.change_dir, "implemented"), "frozen Red oracle")


def test_the_whole_file_freeze_follows_the_layout_too(tmp_path: Path):
    """A runner without a report freezes the declared test files whole (`red_oracle`)."""
    write(tmp_path / "app/test_limiter.py", "def test_x():\n    assert 1 == 2\n")
    write(tmp_path / "app/limiter.py", "x = 1\n")
    before = compute_red_oracle_digest(tmp_path, ["app/test_limiter.py", "app/limiter.py"])
    assert before is not None
    write(tmp_path / "app/limiter.py", "x = 2\n")  # product code is not the oracle
    assert compute_red_oracle_digest(tmp_path, ["app/test_limiter.py", "app/limiter.py"]) == before
    write(tmp_path / "app/test_limiter.py", "def test_x():\n    assert 1 == 1\n")
    assert compute_red_oracle_digest(tmp_path, ["app/test_limiter.py", "app/limiter.py"]) != before


# --- FE-4: evidence goes stale when the product's tree moves, wherever the code is ------------------

@pytest.mark.parametrize("roots,code_rel", [
    (["svc/src/**", "tests/**"], "svc/src/limiter.py"),
    (["*/src/**", "tests/**"], "svc/src/limiter.py"),
    (["app/**"], "app/limiter.py"),
])
def test_green_goes_stale_when_code_under_a_code_root_moves(tmp_path: Path, repo_root: Path, roots, code_rel):
    test_rel = "tests/test_limiter.py" if "tests/**" in roots else "app/test_limiter.py"
    builder, _ = _limiter(tmp_path, repo_root, code_rel, test_rel, {"code_roots": roots})
    red = run_evidence(builder.change_dir, phase="red", task="TASK-001", argv=pytest_argv(test_rel), changed_paths=[test_rel])
    assert red.authentic, red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")
    write(tmp_path / code_rel, "def cooldown():\n    return 30\n")
    paths = [test_rel, code_rel]
    green = run_evidence(builder.change_dir, phase="green", task="TASK-001", argv=pytest_argv(test_rel), changed_paths=paths)
    reg = run_evidence(builder.change_dir, phase="regression", task="TASK-001", argv=pytest_argv(), changed_paths=paths)
    assert green.authentic and reg.authentic, (green.errors, reg.errors)
    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert check_gate(builder.change_dir, "implemented") == []
    write(tmp_path / code_rel, "def cooldown():\n    return 0\n")  # the product is broken again
    assert only(check_gate(builder.change_dir, "implemented"), "stale evidence")


def test_the_base_revision_covers_tests_and_ignores_caches_and_build_products(tmp_path: Path):
    write(tmp_path / "src/limiter.py", "x = 1\n")
    write(tmp_path / "tests/test_limiter.py", "def test_x():\n    assert True\n")
    write(tmp_path / "src/pom.xml", "<project/>")
    base = compute_product_baseline_revision(tmp_path)
    write(tmp_path / "src/__pycache__/limiter.cpython-314.pyc", "junk")
    write(tmp_path / "tests/.pytest_cache/v/cache/lastfailed", "{}")
    write(tmp_path / "src/target/surefire-reports/TEST-x.xml", "<testsuite/>")
    write(tmp_path / "docs/changes/CHG-001/evidence/green/TASK-001.yaml", "x: 1\n")
    assert compute_product_baseline_revision(tmp_path) == base
    # The bypass of 3.3.13: a test weakened after the run is a moved tree too.
    write(tmp_path / "tests/test_limiter.py", "def test_x():\n    assert True or False\n")
    assert compute_product_baseline_revision(tmp_path) != base


# --- the context budget counts what the layout calls product files ---------------------------------

def test_the_budget_counts_a_package_named_build_and_skips_real_build_products(tmp_path: Path):
    """`build` and `target` were skipped by name anywhere, so a glob over them counted nothing."""
    write(tmp_path / "src/build/steps.py", "x = 1\n" * 4000)
    budget = {"max_tokens": 1000, "max_files": 24}
    assert only(validate_task_context_budget(budget, [], ["src/**"], tmp_path), "tokens")
    other = tmp_path / "other"
    write(other / "svc/pom.xml", "<project/>")
    write(other / "svc/target/classes/big.txt", "x = 1\n" * 4000)
    assert validate_task_context_budget(budget, [], ["svc/**"], other) == []


# --- FE-10: a checkout that rewrites line endings moves neither the oracle nor the tree -------------

JAVA_TEST = "package demo;\nclass CalcTest {\n    void adds() {}\n}\n"


def _crlf(path: Path) -> None:
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def test_an_autocrlf_checkout_moves_neither_the_frozen_oracle_nor_the_base_revision(tmp_path: Path):
    from deltafuse.core.oracle import freeze_red_oracle, red_oracle_changes
    from tests.fixtures.evidence_kit import git_init
    from tests.fixtures.git import git

    java = tmp_path / "src/test/java/demo/CalcTest.java"
    code = tmp_path / "src/main/java/demo/Calc.java"
    write(java, JAVA_TEST)
    write(code, "package demo;\nclass Calc {\n}\n")
    frozen = freeze_red_oracle(tmp_path, ["src/test/java/demo/CalcTest.java"], ["demo.CalcTest::adds"])
    base = compute_product_baseline_revision(tmp_path)
    git_init(tmp_path, autocrlf="true")
    java.unlink()
    code.unlink()
    git(tmp_path, "checkout", "--", ".")  # what a fresh clone or `git stash pop` does on Windows
    assert b"\r\n" in java.read_bytes()
    assert red_oracle_changes(tmp_path, frozen) == []
    assert compute_product_baseline_revision(tmp_path) == base
    java.write_bytes(java.read_bytes().replace(b"void adds() {}", b"void adds() { return; }"))
    assert red_oracle_changes(tmp_path, frozen) != []  # a change of content is still a change
    assert compute_product_baseline_revision(tmp_path) != base


def test_line_endings_do_not_move_the_pytest_config_or_the_whole_file_freeze(tmp_path: Path):
    """The twins of the Java oracle: the `config` digest and the report-less `red_oracle`."""
    from deltafuse.core.oracle import freeze_red_oracle, red_oracle_changes

    write(tmp_path / "tests/test_limiter.py", "def test_cooldown():\n    assert 1 == 2\n")
    write(tmp_path / "tests/data/rates.csv", "a,b\n1,2\n")
    write(tmp_path / "pytest.ini", "[pytest]\naddopts = -q\n")
    declared = ["tests/test_limiter.py", "tests/data/rates.csv"]
    frozen = freeze_red_oracle(tmp_path, declared, ["tests.test_limiter::test_cooldown"])
    whole = compute_red_oracle_digest(tmp_path, declared)
    for rel in ("tests/test_limiter.py", "tests/data/rates.csv", "pytest.ini"):
        _crlf(tmp_path / rel)
    assert red_oracle_changes(tmp_path, frozen) == []
    assert compute_red_oracle_digest(tmp_path, declared) == whole
    write(tmp_path / "pytest.ini", "[pytest]\naddopts = -q -p no:terminal\n")
    assert any("configuration" in c for c in red_oracle_changes(tmp_path, frozen))


def test_a_binary_file_is_hashed_as_it_is(tmp_path: Path):
    from deltafuse.core.product_layout import content_sha256

    (tmp_path / "a.bin").write_bytes(b"\x00\x01\r\n\x02")
    (tmp_path / "b.bin").write_bytes(b"\x00\x01\n\x02")
    assert content_sha256(tmp_path / "a.bin") != content_sha256(tmp_path / "b.bin")
