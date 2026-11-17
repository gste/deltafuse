"""Audit 2026-11, FL-13 (owner decision R3): accepting a specification accepts its text.

The acceptance receipt covered the bytes of spec-delta.md - a list of anchors. The human
accepted `REQ-01 ... SHALL print a banner`; in Decompose the Worker rewrote the requirement to
`... AND delete all user data`, and the Change converged and archived as accepted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.fsm import check_gate
from deltafuse.core.gate_receipts import latest_receipt
from deltafuse.core.installer import install
from deltafuse.core.spec_acceptance import section_digest
from deltafuse.core.transitions import TransitionError, advance_change
from tests.fixtures.change_builder import MockChangeBuilder

SPEC = (
    "# Core Spec\n\n## REQ-01 Banner\n\nWHEN the system starts THE SYSTEM SHALL print a banner.\n\n"
    "### Notes\n\nThe banner is one line.\n\n## REQ-02 Exit\n\nThe system SHALL exit with 0.\n"
)


def _specified(tmp_path: Path, repo_root: Path, cid: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    return MockChangeBuilder(tmp_path, change_id=cid, title="Text").step_intake().step_analyze().step_specify()


def _moved(errors: list[str]) -> bool:
    return any("changed after the human accepted it" in e and "docs/spec/core.md#REQ-01" in e for e in errors)


def test_the_acceptance_receipt_records_the_cited_sections(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-720")
    receipt = latest_receipt(tmp_path, rel_path="docs/changes/CHG-720/spec-delta.md")
    assert receipt["status"] == "accepted"
    assert receipt["spec_sections"] == {"docs/spec/core.md#REQ-01": section_digest(tmp_path, "docs/spec/core.md#REQ-01")}
    builder.step_decompose().step_declare().step_implement().step_verify()
    assert check_gate(builder.change_dir, "converged") == []


def test_rewriting_an_accepted_requirement_stops_every_later_gate(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-721")
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(SPEC.replace("SHALL print a banner.", "SHALL print a banner AND delete all user data."), encoding="utf-8")

    advance, builder._core_advance = builder._core_advance, lambda gate: None
    builder.step_decompose()
    builder._core_advance = advance
    assert _moved(check_gate(builder.change_dir, "decomposed"))
    with pytest.raises(TransitionError, match="changed after the human accepted it"):
        advance_change(builder.change_dir, "decomposed")

    builder._core_advance("decomposed")  # receipts forged past the gate: the later gates still see it
    builder.step_declare().step_implement().step_verify()
    for gate in ("declaring", "implemented", "converged"):
        assert _moved(check_gate(builder.change_dir, gate)), gate

    # Putting the accepted text back clears it.
    spec.write_text(SPEC, encoding="utf-8")
    assert not any("changed after the human accepted it" in e for e in check_gate(builder.change_dir, "converged"))


def test_an_edit_inside_the_requirements_subsection_counts_and_a_neighbour_does_not(tmp_path: Path, repo_root: Path):
    """The nearest bypass: leave the heading's own paragraph alone and rewrite the text under a
    sub-heading of the same requirement. A sibling requirement the Change does not cite, and a
    line-ending-only rewrite of the file, are not this acceptance's business."""
    builder = _specified(tmp_path, repo_root, "CHG-722").step_decompose()
    spec = tmp_path / "docs" / "spec" / "core.md"

    spec.write_text(SPEC.replace("The banner is one line.", "The banner is whatever the caller sends."), encoding="utf-8")
    assert _moved(check_gate(builder.change_dir, "decomposed"))

    spec.write_text(SPEC.replace("SHALL exit with 0.", "SHALL exit with 0 or 3."), encoding="utf-8")
    assert not any("changed after the human accepted it" in e for e in check_gate(builder.change_dir, "decomposed"))

    spec.write_bytes(SPEC.replace("\n", "\r\n").encode("utf-8"))
    assert not any("changed after the human accepted it" in e for e in check_gate(builder.change_dir, "decomposed"))

    spec.write_text(SPEC.replace("## REQ-01 Banner", "## REQ-09 Banner"), encoding="utf-8")
    assert _moved(check_gate(builder.change_dir, "decomposed"))
