"""Audit 2026-11-17 (df-leash side of two df-lifecycle changes).

FW-10: the pre-commit hook and `deltafuse leash` judge only on the Core the product pins, with a
config that matches the lock (df-lifecycle made the gates, `state`, `evidence` and `next` ask the
same; the check lives in core/lock.py so both read one answer).

Rewinds: the receipts with which the Core takes a Change back are step boundaries for the leash -
a reopened gap (to Analyze), a rejected accepted specification (`gap-reopen` with gap
`spec-rejected`, to `analyzed`; FL-6) and a task reopened after the `implemented` gate
(`artifact-status` of the Change, reason "task reopened", to `declared`; FL-8).
"""

from __future__ import annotations

import re

import pytest

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, cli, commit, git, leash, product_at, put, walk,
)


# --- FW-10 ------------------------------------------------------------------------------

def _another_core(root) -> None:
    lock = root / ".deltafuse" / "lock.yaml"
    lock.write_text(re.sub(r"sha256:[0-9a-f]{64}", "sha256:" + "ab" * 32, lock.read_text(encoding="utf-8")),
                    encoding="utf-8")


def _config_ahead_of_lock(root) -> None:
    config = root / ".deltafuse" / "config.yaml"
    text = config.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(\s*version:\s*)\S+", r"\g<1>9.9.9", text, count=1)
    text = re.sub(r"deltafuse://v[0-9.]+", "deltafuse://v9.9.9", text, count=1)
    config.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("break_pin", [_another_core, _config_ahead_of_lock])
def test_the_leash_refuses_on_a_core_the_product_does_not_pin(product_at, break_pin):
    root, _ = product_at("declared")
    code, out = cli("leash", root, check=False)
    assert code == 0, out
    break_pin(root)
    code, out = cli("leash", root, check=False)
    assert code == 2 and "pin" in out, out


@pytest.mark.parametrize("break_pin", [_another_core, _config_ahead_of_lock])
def test_the_hook_and_the_other_leash_modes_refuse_too(product_at, break_pin):
    """The twins: the hook (the index), `--file`, and CI's `--base/--head`."""
    root, _ = product_at("declared")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    break_pin(root)
    proc = commit(root, "judged by another Core", verify=True)
    assert proc.returncode != 0 and "pin" in proc.stdout + proc.stderr, proc.stdout + proc.stderr
    code, out = cli("leash", root, "--file", "src/app.py", check=False)
    assert code == 2 and "pin" in out, out
    code, out = cli("leash", root, "--base", base, "--head", "HEAD", check=False)
    assert code == 2 and "pin" in out, out


def test_the_pin_check_is_the_one_in_lock(product_at):
    from deltafuse.core.lock import product_pin_errors

    root, _ = product_at("declared")
    assert product_pin_errors(root) == []
    _another_core(root)
    assert product_pin_errors(root)
    assert product_pin_errors(root.parent) == []  # no lock: not a product, not judged here


# --- rewind receipts --------------------------------------------------------------------

def _rewind(root, **entry) -> None:
    from deltafuse.core.transitions import append_receipt

    append_receipt(root, {"change": CHANGE, **entry})


TASK_REOPEN = {"kind": "artifact-status", "artifact": "change", "reason": "task reopened",
               "from": "implemented", "to": "declared"}
SPEC_REJECTED = {"kind": "gap-reopen", "gap": "spec-rejected", "from": "implemented", "to": "analyzed"}
GAP = {"kind": "gap-reopen", "gap": "spec-gap", "from": "verifying", "to": "analyzing"}


TASK_FILE = f"docs/changes/{CHANGE}/tasks/TASK-001.md"


def _steps(root, base="HEAD") -> list[str]:
    """The steps the chain opens; Declare and Implement open per task, here for a changed TASK-001."""
    from deltafuse.core.leash import collect_chain_envelopes

    return [env["step"] for env in collect_chain_envelopes(root, base=base, dirty=[TASK_FILE])]


@pytest.mark.parametrize("entry,gate", [(TASK_REOPEN, "declaring"), (SPEC_REJECTED, "analyzed"), (GAP, "intake")])
def test_a_rewind_receipt_sets_the_last_gate(entry, gate):
    import json

    from deltafuse.core.leash import _last_gates

    lines = [json.dumps({"kind": "transition", "change": CHANGE, "gate": "implemented"}),
             json.dumps({"change": CHANGE, **entry})]
    assert _last_gates(lines) == {CHANGE: gate}
    # an ordinary status receipt of the Change is not a rewind
    lines.append(json.dumps({"kind": "artifact-status", "artifact": "change", "change": CHANGE,
                             "from": "analyzed", "to": "specification-proposed"}))
    assert _last_gates(lines) == {CHANGE: gate}


def test_after_a_task_reopen_rewind_the_step_is_implement_again(product_at):
    """Committed at the rewind, the Change read as still past `implemented`: the task's product
    file, written again in Implement, was judged against the Verify envelope."""
    root, _ = product_at("implemented")
    assert _steps(root) == ["verify"]
    _rewind(root, **TASK_REOPEN)
    commit(root, "the human reopens a task")
    assert _steps(root) == ["implement"]


def test_after_a_rejected_specification_the_step_is_specify_again(product_at):
    root, _ = product_at("implemented")
    _rewind(root, **SPEC_REJECTED)
    commit(root, "the human rejects the accepted specification")
    assert _steps(root) == ["specify"]


def test_a_rewind_inside_the_diff_opens_the_steps_from_there_on(product_at):
    """Uncommitted: the chain since the base went back and goes on from the rewound step."""
    root, _ = product_at("implemented")
    _rewind(root, **SPEC_REJECTED)
    assert _steps(root) == ["specify"]
    root, _ = product_at("implemented", "q")
    _rewind(root, **TASK_REOPEN)
    assert _steps(root) == ["implement"]


@pytest.mark.parametrize("entry", [TASK_REOPEN, SPEC_REJECTED])
def test_a_rewind_is_where_the_next_step_starts_for_advance(product_at, entry):
    """`advance` judges the step from the commit before the one that recorded its last step
    receipt; a rewind is such a receipt."""
    from deltafuse.core.leash import step_base

    root, change = product_at("implemented")
    before = git(root, "rev-parse", "HEAD").stdout.strip()
    assert step_base(root, change) != before
    _rewind(root, **entry)
    commit(root, "rewind")
    put(root, "docs/intake/note.md", "later\n")
    commit(root, "later")
    assert step_base(root, change) == before
