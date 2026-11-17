"""Audit 2026-11, FL-7: verification.md holds one verdict, wherever its `Outcome:` lines stand.

A file with `- Outcome: converged` under one claim and `- Outcome: spec-gap ... Do not converge`
as the overall verdict closed the `converged` gate: only the first `Outcome:` line was read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.decide import apply_decision
from deltafuse.core.fsm import check_gate, verification_gap
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue
from deltafuse.core.transitions import TransitionError, advance_change
from tests.fixtures.change_builder import MockChangeBuilder

TWO = (
    "# Change Verification\n\n## CR-001\n- Outcome: converged\n\n## Overall\n\n- Outcome: `spec-gap`\n\n"
    "REQ-02 does not say what the banner holds. Do not converge.\n"
)


def _verified(tmp_path: Path, repo_root: Path, cid: str, text: str) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="V").step_through_decompose()
    builder.step_declare().step_implement()
    forge, builder._core_advance = builder._core_advance, lambda gate: None
    builder.step_verify()  # the verification run and the task statuses, without the transition
    builder._core_advance = forge
    (builder.change_dir / "verification.md").write_text(text, encoding="utf-8")
    return builder.change_dir


def test_converged_first_and_a_gap_after_does_not_converge(tmp_path: Path, repo_root: Path):
    change = _verified(tmp_path, repo_root, "CHG-820", TWO)
    errors = check_gate(change, "converged")
    assert any("several outcomes" in e and "spec-gap" in e for e in errors), errors
    with pytest.raises(TransitionError, match="spec-gap"):
        advance_change(change, "converged")

    # The queue and the human's way back read the same verdict.
    assert verification_gap(change) == "spec-gap"
    reason = build_work_queue(tmp_path).blocked[0].reason
    assert "Verify recorded the gap 'spec-gap'" in reason
    assert apply_decision(change, status="reopened", gap="spec-gap", note="REQ-02")["change_status"] == "analyzing"


@pytest.mark.parametrize(
    "text",
    [
        "# V\n\n- Outcome: spec-gap\n\n## Later\n\n- Outcome: converged\n",
        "# V\n\n- Outcome: converged\n- Outcome: converged\n\n**Outcome**: `test-gap`\n",
        "# V\n\n- Outcome: converged\n\n* Outcome: not-reproduced\n",
        "# V\n\n- Outcome: converged\n\n- Outcome: `converged | tasks-missing | spec-gap`\n",
    ],
)
def test_no_arrangement_of_a_second_verdict_converges(tmp_path: Path, repo_root: Path, text: str):
    change = _verified(tmp_path, repo_root, "CHG-821", text)
    assert any("Gate converged: verification.md" in e for e in check_gate(change, "converged"))


def test_one_verdict_said_twice_is_still_that_verdict(tmp_path: Path, repo_root: Path):
    change = _verified(tmp_path, repo_root, "CHG-822", "# V\n\n- Outcome: converged\n\n## Overall\n\n- Outcome: `converged`\n")
    assert check_gate(change, "converged") == []
    assert advance_change(change, "converged")["to"] == "converged"
