"""Audit 2026-11-17, FW-13 at the merge: what `deltafuse leash` knows, its text mode says, and
`deltafuse next` warns about a missing pre-commit hook.

The leash payload carried `warnings` (no hook runs the leash in this clone) and `note` (why a
diff was not judged), and the text mode printed neither from the payload: the warning came from
a `print` inside `run_leash`, the note not at all - "no write envelope" stood for "first commit"
and for "DeltaFuse is not installed at the base". `next`, the command a Worker runs at every
step, said nothing about a clone whose commits nobody judges.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from pathlib import Path

from deltafuse.cli import main
from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    REPO_ROOT, cli, commit, env, git, product_at, put, set_workflow, walk,
)


def _run(*argv) -> tuple[int, str, str]:
    """`deltafuse <argv>`: (exit code, stdout, stderr), the two streams apart."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main([str(a) for a in argv])
        except SystemExit as ex:
            code = int(ex.code or 0)
    return code, out.getvalue(), err.getvalue()


def _clone(root: Path, tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True, capture_output=True, env=env())
    return clone


# --- `deltafuse leash`, text mode ---------------------------------------------------------

def test_leash_text_mode_prints_the_warning_once_and_json_stays_json(product_at, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("converged")
    clone = _clone(root, tmp_path)
    code, out, err = _run("leash", clone)
    assert code == 0 and err.count("pre-commit hook is not active") == 1, (out, err)
    assert "warning" in err and "pre-commit" not in out
    code, out, err = _run("leash", clone, "--json")
    payload = json.loads(out)  # stdout is the payload and nothing else
    assert payload["warnings"] and err.count("pre-commit hook is not active") == 1, err


def test_run_leash_itself_prints_nothing(product_at, tmp_path, monkeypatch, capsys):
    """The twin: the payload is the answer; `advance` and hosts calling `run_leash` get no stray print."""
    from deltafuse.core.leash_run import run_leash

    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("converged")
    payload = run_leash(_clone(root, tmp_path))
    assert payload["warnings"]
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_leash_text_mode_says_why_a_diff_was_not_judged(tmp_path, monkeypatch):
    """`note`: the commit that installs DeltaFuse into a repository with history."""
    from deltafuse.core.installer import install

    monkeypatch.delenv("CI", raising=False)
    root = tmp_path / "service"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    put(root, "pom.xml", "<project/>\n")
    commit(root, "history before DeltaFuse")
    install(target_dir=root, framework_root=REPO_ROOT)
    code, out, err = _run("leash", root)
    assert code == 0 and "not installed at the base" in out, (out, err)
    assert "no write envelope" not in out
    payload = json.loads(_run("leash", root, "--json")[1])
    assert "not installed at the base" in payload["note"]


def test_the_hook_says_the_first_commit_is_not_judged(tmp_path, monkeypatch):
    """The twin `note`, through the hook's entry (the index): the first commit of a repository."""
    from deltafuse.core.installer import install
    from deltafuse.core.leash import INDEX_ENV

    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    install(target_dir=root, framework_root=REPO_ROOT)
    git(root, "add", "-A")
    monkeypatch.setenv(INDEX_ENV, "1")
    code, out, err = _run("leash", root)
    assert code == 0 and "first commit" in out, (out, err)
    assert "pre-commit" not in err  # inside the hook there is no missing-hook warning


# --- `deltafuse next` -----------------------------------------------------------------------

def test_next_warns_about_a_missing_hook(product_at, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("declared")
    clone = _clone(root, tmp_path)
    code, out, err = _run("next", clone, "--json")
    snapshot = json.loads(out)
    assert len(snapshot["warnings"]) == 1 and "pre-commit" in snapshot["warnings"][0], snapshot["warnings"]
    assert "deltafuse init" in snapshot["warnings"][0]
    code, out, err = _run("next", clone, "--human")
    assert "pre-commit hook is not active" in err and "pre-commit hook is not active" not in out, (out, err)
    # --json --human: the guide rides in the payload, stdout stays one JSON document
    code, out, err = _run("next", clone, "--json", "--human")
    assert json.loads(out)["warnings"]


def test_next_warns_when_git_runs_hooks_from_elsewhere(product_at, monkeypatch):
    """The twin: the hook is installed, and `core.hooksPath` set later moves git away from it."""
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("declared")
    assert json.loads(_run("next", root, "--json")[1])["warnings"] == []
    git(root, "config", "core.hooksPath", ".husky")
    put(root, ".husky/pre-commit", "#!/bin/sh\nexit 0\n")
    assert json.loads(_run("next", root, "--json")[1])["warnings"]


def test_next_is_silent_in_ci_with_the_hook_and_with_the_leash_off(product_at, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    root, _ = product_at("declared")
    code, out, err = _run("next", root, "--human")
    assert "pre-commit" not in err, err
    clone = _clone(root, tmp_path)
    monkeypatch.setenv("CI", "true")
    assert json.loads(_run("next", clone, "--json")[1])["warnings"] == []
    assert "pre-commit hook" not in _run("next", clone, "--human")[2]
    monkeypatch.delenv("CI")
    set_workflow(clone, leash="off")
    assert json.loads(_run("next", clone, "--json")[1])["warnings"] == []
