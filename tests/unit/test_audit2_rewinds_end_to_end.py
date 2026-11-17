"""Audit 2026-11-17, at the merge of the lifecycle and leash branches: the rewinds `decide`
really writes are step boundaries for the leash and for `advance` under `leash: enforce`.

The leash branch tested its rewind rule with receipts it wrote itself, by literals copied from
core/transitions.py. Here the human's real commands write them (FL-6, FL-8), every step is
committed through the pre-commit hook, and the Worker's rework passes the leash at `advance`.
"""

from __future__ import annotations

import sys

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, ORACLE, cli, commit, git, leash, product_at, put, walk,
)

RUN = [sys.executable, "tests/test_banner.py"]
TASK_FILE = f"docs/changes/{CHANGE}/tasks/TASK-001.md"


def _hooked(root, label: str) -> None:
    proc = commit(root, label, verify=True)
    assert proc.returncode == 0, f"{label}: the hook refused\n{proc.stdout}\n{proc.stderr}"


def _clean(root) -> None:
    code, payload = leash(root)
    assert code == 0 and not payload.get("violations"), payload


def _steps(root, dirty: list[str]) -> list[str]:
    from deltafuse.core.leash import collect_chain_envelopes

    return [env["step"] for env in collect_chain_envelopes(root, base="HEAD", dirty=dirty)]


def test_the_leash_reads_the_rewind_marks_from_the_receipt_chain():
    """One source: what `decide` writes, the chain replays and the leash reads are the same names."""
    from deltafuse.core import leash as leash_mod, transitions

    assert not hasattr(leash_mod, "TASK_REOPEN_REASON") and not hasattr(leash_mod, "SPEC_REJECTED_GAP")
    reopen = {"kind": "artifact-status", "artifact": "change", "reason": transitions.TASK_REOPEN_REASON}
    assert transitions.is_task_reopen_rewind(reopen) and leash_mod.rewind_gate(reopen) == "declaring"
    reject = {"kind": transitions.GAP_REOPEN_KIND, "gap": transitions.SPEC_REJECTED_GAP}
    assert leash_mod.rewind_gate(reject) == "analyzed"


def test_a_task_reopened_after_the_implemented_gate_is_reworked_under_enforce(product_at):
    root, change = product_at("implemented")
    cli("state", change, "--task", "TASK-001", "--status", "blocked")
    _hooked(root, "the Worker blocks the task")
    cli("decide", change, "--task", "TASK-001", "--status", "reopened", "--note", "the banner is wrong")
    _clean(root)
    _hooked(root, "the human reopens the task")
    assert _steps(root, [TASK_FILE]) == ["implement"]  # as the `declaring` gate left it; not Verify

    # Declare again: the oracle, Red, the gate.
    put(root, "tests/test_banner.py", ORACLE.replace("BANNER", "GREETING").replace("no banner", "no greeting"))
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", *RUN)
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    _clean(root)
    _hooked(root, "declared again")
    # Implement again: the product file the task owns is inside the envelope, not Verify's.
    put(root, "src/app.py", "GREETING = 'hello'\n")
    code, payload = leash(root)
    assert code == 0 and not payload.get("violations"), payload
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *RUN)
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    code, out = cli("advance", change, "--gate", "implemented", check=False)
    assert code == 0, out
    _hooked(root, "implemented again")


def test_a_write_outside_the_reopened_task_is_still_refused(product_at):
    """The bypass: the rewind opens the reopened task's step, not the product."""
    root, change = product_at("implemented")
    cli("state", change, "--task", "TASK-001", "--status", "blocked")
    commit(root, "blocked")
    cli("decide", change, "--task", "TASK-001", "--status", "reopened")
    commit(root, "reopened")
    put(root, "src/other.py", "Y = 2\n")
    code, payload = leash(root)
    assert code != 0 and any("src/other.py" in v for v in payload["violations"]), payload
    proc = commit(root, "outside the task", verify=True)
    assert proc.returncode != 0


def test_a_rejected_accepted_specification_is_specified_again_under_enforce(product_at):
    root, change = product_at("implemented")
    cli("decide", change, "--spec", "--status", "rejected")
    _clean(root)
    _hooked(root, "the human rejects the accepted specification")

    spec = root / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("print a banner", "print a greeting banner"),
                    encoding="utf-8")
    _clean(root)  # Specify writes the specification again; under Verify's envelope it was a violation
    cli("state", change, "--slice", "SLICE-01", "--status", "specified")
    cli("state", change, "--change", "--status", "specification-proposed")
    _hooked(root, "specify again")
    code, out = cli("decide", change, "--spec", "--status", "accepted", check=False)
    assert code == 0, out
    _clean(root)
    _hooked(root, "accepted again")
    # The Core walked the gates already passed: the Change is in Implement again.
    put(root, "src/app.py", "BANNER = 'hello, greeting'\n")
    _clean(root)
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *RUN)
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    code, out = cli("advance", change, "--gate", "implemented", check=False)
    assert code == 0, out
    _hooked(root, "implemented again")


def test_product_code_written_while_the_specification_is_rejected_is_refused(product_at):
    """The bypass: after the rejection the step is Specify, so the Implement envelope is closed."""
    root, change = product_at("implemented")
    cli("decide", change, "--spec", "--status", "rejected")
    commit(root, "rejected")
    put(root, "src/app.py", "BANNER = 'again'\n")
    code, payload = leash(root)
    assert code != 0 and any("src/app.py" in v for v in payload["violations"]), payload
