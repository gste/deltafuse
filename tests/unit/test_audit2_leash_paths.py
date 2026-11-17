"""Audit 2026-11-17 (df-leash), S4: one path normaliser for `leash --file`, task `allowed_paths`
and Writer targets; envelopes scoped to their Change; a task that was not declared before the step
opens nothing; a missing `workflow.leash` read the same way everywhere."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, TASK_FIELDS, cli, commit, git, leash, product_at, put, set_workflow, walk, write,
)


# --- FW-1: `leash --file` ---------------------------------------------------------------

def test_file_mode_control_a_relative_product_path_is_refused(product_at):
    root, _ = product_at("converged")
    put(root, "src/existing.py", "X = 2\n")
    code, data = leash(root, "--file", "src/existing.py")
    assert code == 1 and data["violations"], data


@pytest.mark.parametrize("spelling", ["absolute", "absolute-posix", "dotdot", "x-dotdot", "dot", "double-slash"])
def test_file_mode_judges_a_product_path_however_it_is_spelled(product_at, spelling):
    """FW-1: an absolute path, or one with `..`, matched no glob and passed as "not a product path"."""
    root, _ = product_at("converged")
    put(root, "src/existing.py", "X = 2\n")
    arg = {
        "absolute": str(root / "src" / "existing.py"),
        "absolute-posix": (root / "src" / "existing.py").as_posix(),
        "dotdot": "docs/intake/../../src/existing.py",
        "x-dotdot": "x/../src/existing.py",
        "dot": "src/./existing.py",
        "double-slash": "src//existing.py",
    }[spelling]
    code, data = leash(root, "--file", arg)
    assert code == 1, data
    assert data["paths"] == ["src/existing.py"], data
    assert any("src/existing.py" in v for v in data["violations"]), data


def test_file_mode_refuses_a_path_outside_the_product(product_at, tmp_path):
    """The bypass next to FW-1: a path that leaves the product is not silently "no violation"."""
    root, _ = product_at("converged")
    outside = tmp_path / "elsewhere.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    for arg in (str(outside), "../elsewhere.py", "src/../../elsewhere.py"):
        code, out = cli("leash", root, "--file", arg, check=False)
        assert code == 2, (arg, out)
        assert "outside the product" in out, out


# --- FW-8: task allowed_paths ------------------------------------------------------------

DOTDOT = ["src/../.deltafuse/gate-password.yaml", "src/../.git/hooks/pre-commit"]


def _hand_task(change: Path, allowed: list[str]) -> None:
    """A task file as a Worker's file tool would write it (the Writer is the other entry point)."""
    import yaml

    meta = {"id": "TASK-001", "change": "CHG-701", "slice": "SLICE-01", "status": "pending",
            "kind": "feature", "depends_on": [], "requirement_delta": "added",
            "spec_refs": ["docs/spec/core.md#REQ-02"], "design_ref": None,
            "allowed_paths": allowed, "forbidden_paths": [],
            "context_budget": {"max_tokens": 64000, "max_files": 24}}
    (change / "tasks").mkdir(exist_ok=True)
    (change / "tasks" / "TASK-001.md").write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# TASK-001: t\n\nbody\n", encoding="utf-8")


def test_the_decomposed_gate_refuses_allowed_paths_with_dotdot(product_at):
    """FW-8: `src/../.deltafuse/gate-password.yaml` starts with `src/`, so the gate took it as under
    `src/**` and `next --json` handed it to the host as a path the Worker may write."""
    from deltafuse.core.leash import task_envelope_errors

    root, change = product_at("specified")
    _hand_task(change, ["src/app.py", *DOTDOT])
    errors = task_envelope_errors(change)
    assert len(errors) == 2 and all("TASK-001" in e for e in errors), errors
    code, out = cli("advance", change, "--gate", "decomposed", check=False)
    assert code != 0, out


@pytest.mark.parametrize("bad", ["/etc/passwd", "C:/Windows/x.py", "src" + chr(92) + ".." + chr(92) + "x.py", "./src/app.py", "src//app.py",
                                 "src" + chr(92) + "x.py", " src/x.py"])
def test_the_decomposed_gate_refuses_other_unnormalised_allowed_paths(product_at, bad):
    from deltafuse.core.leash import task_envelope_errors

    root, change = product_at("specified")
    _hand_task(change, ["src/app.py", bad])
    assert task_envelope_errors(change), bad


def test_the_writer_refuses_allowed_paths_with_dotdot(product_at):
    """The same trick through the Writer: it wrote the task and the gate then passed it."""
    root, change = product_at("specified")
    code, out = write(root, "task", {"identity": "TASK-001", "fields": {
        **TASK_FIELDS, "allowed_paths": ["src/app.py", *DOTDOT]}, "body": "b"}, check=False)
    assert code != 0, out
    assert not (change / "tasks" / "TASK-001.md").exists()
    code, out = write(root, "task", {"identity": "TASK-001", "fields": {
        **TASK_FIELDS, "forbidden_paths": ["src/../src/**"]}, "body": "b"}, check=False)
    assert code != 0, out


def test_an_envelope_never_carries_a_dotdot_path(product_at):
    """Behind the gate: a declared task that already holds such a path opens nothing with it."""
    from deltafuse.core.leash import envelope_write_globs
    from deltafuse.core.queue import _item_for_step

    root, change = product_at("decomposed")
    task = change / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace(
        "- src/app.py", "- src/app.py\n- src/../.deltafuse/gate-password.yaml"), encoding="utf-8")
    rel = change.relative_to(root).as_posix()
    for step in ("declare", "implement"):
        item = _item_for_step(step, change_id="CHG-701", path=rel, task="TASK-001",
                              task_path=f"{rel}/tasks/TASK-001.md", reason="t")
        globs = envelope_write_globs(item, root)
        assert not any(".." in g for g in globs), globs
