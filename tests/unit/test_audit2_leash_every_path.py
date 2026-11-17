"""Audit 2026-11-17 (df-leash), owner's decision R5: the leash judges every path that is not
explicitly exempt (FW-7), caches are exempt only where a cache really lies (FW-17), a git-ignored
file inside a code root is seen (FW-18), and a hand-written Decision is refused (FW-20)."""

from __future__ import annotations

import json
import sys

import pytest

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, ORACLE, TASK_FIELDS, cli, commit, git, leash, product_at, put, set_workflow, walk, write,
)

ROOT_FILES = [
    "conftest.py", "pytest.ini", "pyproject.toml", "pom.xml", "lib/evil.py", "app/main.py",
    ".github/workflows/deltafuse-leash.yml", "README.md", "CHANGELOG.md", ".gitignore",
    "docs/guide.md", "docs/decisions/notes.md",
]
DECISION = {"title": "Banner text", "kind": "architecture",
            "affects": {"capabilities": ["system.core"], "spec_refs": ["docs/spec/core.md"]}}
STILL_EXEMPT = ["docs/intake/source.md", "AGENTS.md", ".deltafuse/tmp/task.json", "docs/archive/intake/source.md"]


def _named(violations: list[str], rel: str) -> bool:
    return any(f"'{rel}'" in v for v in violations)


@pytest.mark.parametrize("rel", ROOT_FILES)
def test_a_file_outside_the_code_roots_is_judged(product_at, rel):
    """FW-7: only `src/**`, `tests/**` and the ops roots were product paths; a build file, a test
    configuration, the CI leash workflow itself were never judged, with or without an envelope."""
    root, _ = product_at("converged")
    put(root, rel, "changed = 1\n")
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], rel), data


def test_the_hook_refuses_a_root_file_too(product_at):
    root, _ = product_at("converged")
    put(root, "pom.xml", "<project/>\n")
    proc = commit(root, "build file", verify=True)
    assert proc.returncode != 0 and "pom.xml" in proc.stdout + proc.stderr


def test_a_ready_step_does_not_cover_a_root_file(product_at):
    """The twin: with an envelope open (Implement of TASK-001) the file is outside it."""
    root, _ = product_at("declared")
    put(root, "conftest.py", "import sys\n")
    put(root, ".github/workflows/deltafuse-leash.yml", "name: off\n")
    code, data = leash(root)
    assert code == 1, data
    assert _named(data["violations"], "conftest.py") and _named(data["violations"], ".github/workflows/deltafuse-leash.yml"), data


@pytest.mark.parametrize("rel", STILL_EXEMPT)
def test_the_exempt_paths_stay_exempt(product_at, rel):
    root, _ = product_at("converged")
    put(root, rel, "text\n")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data


def test_the_spec_is_free_only_while_the_baseline_is_draft(product_at):
    root, _ = product_at("converged")
    put(root, "docs/spec/new.md", "# New\n")
    assert leash(root)[1]["violations"] == []
    cfg = root / ".deltafuse" / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("baseline: draft", "baseline: accepted"), encoding="utf-8")
    commit(root, "the human accepts the baseline")
    put(root, "docs/spec/newer.md", "# Newer\n")
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], "docs/spec/newer.md"), data


def test_a_change_writes_a_root_file_the_human_put_in_the_code_roots(product_at):
    """How a Change changes `pom.xml` now: the human names it in `workflow.code_roots`, the task in
    its `allowed_paths`."""
    from deltafuse.core.config import validate_config

    root, change = product_at("specified")
    set_workflow(root, code_roots=["src/**", "tests/**", "pom.xml"])
    assert validate_config(root) == [], validate_config(root)
    commit(root, "the human adds pom.xml to the code roots")
    write(root, "task", {"identity": "TASK-001", "fields": {
        **TASK_FIELDS, "allowed_paths": ["src/app.py", "tests/test_banner.py", "pom.xml"]}, "body": "b"})
    cli("advance", change, "--gate", "decomposed")
    assert commit(root, "decompose", verify=True).returncode == 0
    put(root, "tests/test_banner.py", ORACLE)
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", sys.executable, "tests/test_banner.py")
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    cli("advance", change, "--gate", "declaring")
    assert commit(root, "declare", verify=True).returncode == 0
    put(root, "pom.xml", "<project/>\n")
    put(root, "src/app.py", "BANNER = 'hello'\n")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data
    assert "pom.xml" in data["envelope"]["write"], data["envelope"]
    put(root, "build.gradle", "plugins {}\n")
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], "build.gradle"), data


# --- FW-17: caches ----------------------------------------------------------------------

FAKE_CACHE = [
    "src/__pycache__/payload.py", "src/pkg/__pycache__/conftest.py", "tests/.pytest_cache/x.py",
    "src/stray.pyc", "src/__pycache__/deep/mod.cpython-312.pyc", ".pytest_cache/v/../../src/evil.py",
]
REAL_CACHE = [
    "src/__pycache__/app.cpython-312.pyc", "tests/__pycache__/test_banner.cpython-312-pytest-8.3.3.pyc",
    ".pytest_cache/v/cache/lastfailed", ".pytest_cache/CACHEDIR.TAG", ".pytest_cache/README.md",
    ".pytest_cache/.gitignore",
]


def _no_ignore_file(root) -> None:
    git(root, "rm", "-q", "--cached", ".gitignore")
    (root / ".gitignore").unlink()
    commit(root, "no .gitignore")


@pytest.mark.parametrize("rel", FAKE_CACHE[:5])
def test_a_file_in_a_cache_directory_that_is_no_cache_file_is_judged(product_at, rel):
    """FW-17: anything under a `__pycache__/` or `.pytest_cache/` directory, and any `*.pyc`, was
    exempt - `src/__pycache__/payload.py` is product code by any other name."""
    root, _ = product_at("converged")
    _no_ignore_file(root)
    put(root, rel)
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], rel), data


@pytest.mark.parametrize("rel", REAL_CACHE)
def test_a_real_cache_file_is_exempt(product_at, rel):
    root, _ = product_at("converged")
    _no_ignore_file(root)
    put(root, rel, "cache\n")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data


def test_the_exemption_is_the_same_for_the_function_other_modules_use():
    from deltafuse.core.leash import is_exempt_path

    for rel in FAKE_CACHE + ROOT_FILES:
        assert not is_exempt_path(rel), rel
    for rel in REAL_CACHE + STILL_EXEMPT:
        assert is_exempt_path(rel), rel


# --- FW-18: git-ignored files -----------------------------------------------------------

def test_a_git_ignored_file_in_a_code_root_is_judged(product_at):
    """FW-18: the leash listed untracked files with `--exclude-standard`, so a file a `.gitignore`
    line names was invisible to the leash, the hook's twin `advance` and CI."""
    root, _ = product_at("converged")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "src/hidden.py\n*.local.py\n", encoding="utf-8")
    commit(root, "the human's ignore rules")
    put(root, "src/hidden.py")
    put(root, "src/pkg/settings.local.py")
    code, data = leash(root)
    assert code == 1, data
    assert _named(data["violations"], "src/hidden.py") and _named(data["violations"], "src/pkg/settings.local.py"), data


def test_a_new_directory_whose_only_file_is_ignored_is_judged(product_at):
    """The twin: git names such a directory as one ignored entry, not the file in it."""
    root, _ = product_at("converged")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "hidden.py\n", encoding="utf-8")
    commit(root, "the human's ignore rules")
    put(root, "src/newpkg/hidden.py")
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], "src/newpkg/hidden.py"), data


def test_advance_sees_the_ignored_file_too(product_at):
    from deltafuse.core.leash_run import leash_at_advance

    root, change = product_at("declared")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "src/hidden.py\n", encoding="utf-8")
    commit(root, "the human's ignore rules")
    put(root, "src/hidden.py")
    verdict = leash_at_advance(change, root)
    assert any("src/hidden.py" in v for v in verdict["violations"]), verdict


def test_an_ignore_rule_is_itself_judged(product_at):
    """`.gitignore` is a product file: the Worker does not hide a file by adding a line to it."""
    root, _ = product_at("declared")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "src/hidden.py\n", encoding="utf-8")
    put(root, "src/pkg/.gitignore", "*\n")
    code, data = leash(root)
    assert code == 1 and _named(data["violations"], ".gitignore") and _named(data["violations"], "src/pkg/.gitignore"), data


def test_a_directory_git_ignores_as_a_whole_is_not_listed(product_at):
    """Build output (`target/`, `node_modules/`, an ignored `__pycache__/`): thousands of files the
    human told git to ignore as a directory. Documented limitation."""
    root, _ = product_at("converged")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "target/\n", encoding="utf-8")
    commit(root, "the human's ignore rules")
    put(root, "src/target/classes/App.class", "bytes\n")
    put(root, "src/__pycache__/app.cpython-312.pyc", "bytes\n")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data


# --- FW-20: Decisions -------------------------------------------------------------------

def test_a_hand_written_decision_is_refused(product_at):
    """FW-20: the hand-written check ran only for a path inside an envelope, and no envelope holds
    `docs/decisions/`; nor was the path product code. So the check never ran."""
    root, _ = product_at("analyzed")
    put(root, "docs/decisions/DEC-0999-by-hand.md",
        "---\nid: DEC-0999\nstatus: accepted\nowner: human\n---\n# Decided by nobody\n")
    code, data = leash(root)
    assert code == 1, data
    assert any("DEC-0999-by-hand.md" in v and "by hand" in v for v in data["violations"]), data
    assert commit(root, "decision", verify=True).returncode != 0


def test_a_decision_the_writer_proposed_passes(product_at):
    root, change = product_at("analyzed")
    write(root, "decision", {"fields": DECISION, "body": "Which text?"})
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data


def test_a_hand_edit_of_a_proposed_decision_is_refused(product_at):
    """The twin: the file exists and is the Writer's; the edit is not."""
    root, change = product_at("analyzed")
    write(root, "decision", {"fields": DECISION, "body": "Which text?"})
    decision = next((root / "docs" / "decisions").glob("DEC-0001*.md"))
    decision.write_text(decision.read_text(encoding="utf-8").replace("status: proposed", "status: accepted"),
                        encoding="utf-8")
    code, data = leash(root)
    assert code == 1 and any("by hand" in v for v in data["violations"]), data
