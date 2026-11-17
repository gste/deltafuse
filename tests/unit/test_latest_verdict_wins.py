"""Audit 2026-11, FL-2: the human's latest verdict on an artifact is the one that counts.

After `decide --gap` the Core set spec-delta.md back to `proposed`. A one-word hand edit to
`accepted` reproduced the bytes of the old acceptance, the old receipt matched them again, and
the `specified` gate closed with no new verdict over a changed docs/spec - with the Human Gate
password set, too: the check was "some receipt matches these bytes", not "the last word on this
file is that verdict".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.decide import apply_decision
from deltafuse.core.fsm import check_gate
from deltafuse.core.gate_receipts import has_valid_receipt
from deltafuse.core.installer import install
from deltafuse.core.transitions import TransitionError, advance_change, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder


def _accepted(repo: Path, delta: Path, cid: str) -> bool:
    return has_valid_receipt(
        repo, kind="spec", status="accepted", artifact_id=cid, rel_path=delta.relative_to(repo).as_posix(), artifact=delta
    )


def test_an_acceptance_before_a_gap_reopen_is_not_replayed_by_restoring_its_bytes(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-710", title="Gap")
        .step_through_decompose()
        .step_declare()
        .step_implement()
    )
    change = builder.change_dir
    delta = change / "spec-delta.md"
    accepted_bytes = delta.read_bytes()
    assert _accepted(tmp_path, delta, "CHG-710")

    (change / "verification.md").write_text("# V\n\n- Outcome: spec-gap\n", encoding="utf-8")
    apply_decision(change, status="reopened", gap="spec-gap", note="REQ-01 lacks the banner text")
    assert b"status: proposed" in delta.read_bytes()
    advance_change(change, "analyzed")
    set_artifact_status(change, status="specified", slice_id="SLICE-01")

    # The one-word hand edit: the very bytes the human accepted before the reopen.
    delta.write_bytes(accepted_bytes)
    assert not _accepted(tmp_path, delta, "CHG-710")
    with pytest.raises(TransitionError, match="without deltafuse decide"):
        set_artifact_status(change, status="specification-proposed", change_status=True)
    errors = check_gate(change, "specified", assume_status="specification-proposed")
    assert any("without deltafuse decide" in e for e in errors), errors

    # The human's own new verdict still closes the gate.
    delta.write_bytes(accepted_bytes.replace(b"status: accepted", b"status: proposed"))
    set_artifact_status(change, status="specification-proposed", change_status=True)
    assert apply_decision(change, status="accepted", spec=True)["ok"]
    assert _accepted(tmp_path, delta, "CHG-710")


def test_a_rejection_is_not_undone_by_restoring_the_accepted_bytes(tmp_path: Path, repo_root: Path):
    """The nearest bypass: the later verdict is a rejection, not a reopen."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-711", title="Reject").step_through_decompose()
    change = builder.change_dir
    delta = change / "spec-delta.md"
    accepted_bytes = delta.read_bytes()

    apply_decision(change, status="rejected", spec=True)
    delta.write_bytes(accepted_bytes)
    assert not _accepted(tmp_path, delta, "CHG-711")
    builder.step_declare()
    for gate in ("declaring", "converged"):
        errors = check_gate(change, gate)
        assert any("spec-delta.md is not accepted by the human" in e for e in errors), (gate, errors)


def test_a_crlf_checkout_of_the_accepted_delta_still_counts(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-712", title="Eol").step_through_decompose()
    delta = builder.change_dir / "spec-delta.md"
    delta.write_bytes(delta.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert _accepted(tmp_path, delta, "CHG-712")
