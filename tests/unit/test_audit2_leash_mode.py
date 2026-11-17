"""Audit 2026-11-17 (df-leash), FW-6: a config without `workflow.leash` is read the same way by the
hook's guard, the leash command, `advance` and the installer - as `enforce`."""

from __future__ import annotations

import sys

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, ORACLE, cli, commit, leash, product_at, put, set_workflow, walk,
)


def _to_implement_with_a_stray_commit(root, change) -> None:
    put(root, "tests/test_banner.py", ORACLE)
    run = [sys.executable, "tests/test_banner.py"]
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    cli("advance", change, "--gate", "declaring")
    assert commit(root, "declare", verify=True).returncode == 0
    put(root, "src/app.py", "BANNER = 'hello'\n")
    put(root, "src/existing.py", "X = 'outside TASK-001 allowed_paths'\n")
    commit(root, "stray")  # --no-verify
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *run, check=False)
    cli("state", change, "--task", "TASK-001", "--status", "implemented", check=False)


def test_control_advance_refuses_a_stray_commit_under_enforce(product_at):
    root, change = product_at("decomposed")
    _to_implement_with_a_stray_commit(root, change)
    code, out = cli("advance", change, "--gate", "implemented", check=False)
    assert code != 0 and "src/existing.py" in out, out


def test_advance_still_checks_after_the_key_was_removed(product_at):
    """FW-6: a commit that deletes `workflow.leash` passed the hook (missing was `enforce` for the
    guard, so nothing was relaxed), and from then on `advance` read missing as `off` and did not
    check the step at all."""
    root, change = product_at("decomposed")
    set_workflow(root, leash=None)
    assert commit(root, "drop the key", verify=True).returncode == 0
    _to_implement_with_a_stray_commit(root, change)
    code, out = cli("advance", change, "--gate", "implemented", check=False)
    assert code != 0 and "src/existing.py" in out, out


def test_every_reader_takes_a_missing_key_as_enforce(product_at):
    """The twins: the leash command, the verdict mode, `advance`'s own reader, the installer."""
    from deltafuse.core.installer import install
    from deltafuse.core.leash import load_leash_mode, verdict_leash_mode
    from deltafuse.core.leash_run import leash_at_advance
    from tests.fixtures.leash_walk import REPO_ROOT

    root, change = product_at("decomposed")
    set_workflow(root, leash=None)
    commit(root, "drop the key")
    assert load_leash_mode(root) == "enforce"
    assert verdict_leash_mode(root, base="HEAD", head=None) == "enforce"
    assert leash_at_advance(change, root)["mode"] == "enforce"
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.unlink()
    install(target_dir=root, framework_root=REPO_ROOT)
    assert hook.is_file(), "the installer read a missing key as off and installed no hook"


def test_a_value_that_is_no_mode_is_enforce_too(product_at):
    """A typo (`leash: strict`) is not a way to turn the leash off."""
    from deltafuse.core.leash import load_leash_mode
    from deltafuse.core.leash_run import leash_at_advance

    root, change = product_at("decomposed")
    set_workflow(root, leash="strict")
    assert load_leash_mode(root) == "enforce"
    assert leash_at_advance(change, root) is not None

