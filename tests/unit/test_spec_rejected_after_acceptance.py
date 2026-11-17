"""Audit 2026-11, FL-6 (owner decision R8): rejecting an accepted specification does something.

`deltafuse decide <change> --spec --status rejected` on a Change past `specified` exited 0,
wrote the verdict and left the Change where it was: `next` went on to Declare and Implement,
the `converged` gate then refused for ever, and nothing could re-propose, re-accept or close.
The rejection now returns the Change to `analyzed`, as a rejected proposal always did.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.decide import apply_decision
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import TransitionError, advance_change, receipt_chain_errors, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

SPEC = (
    "# Core Spec\n\n## REQ-01 Banner\n\nWHEN the system starts THE SYSTEM SHALL print a banner.\n\n"
    "## REQ-02 Exit\n\nThe system SHALL exit with 0.\n"
)
MOVED = "The edit after acceptance"


def _status(path: Path) -> str:
    if path.name == "change.yaml":
        return str(yaml.safe_load(path.read_text(encoding="utf-8")).get("status"))
    return str(parse_frontmatter(path.read_text(encoding="utf-8"))[0].get("status"))


def _specified(tmp_path: Path, repo_root: Path, cid: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    return MockChangeBuilder(tmp_path, change_id=cid, title="Text").step_intake().step_analyze().step_specify()


def _moved(errors: list[str]) -> bool:
    return any("changed after the human accepted it" in e and "docs/spec/core.md#REQ-01" in e for e in errors)


def _accept_again(change: Path) -> dict:
    set_artifact_status(change, status="specified", slice_id="SLICE-01")
    set_artifact_status(change, status="specification-proposed", change_status=True)
    return apply_decision(change, status="accepted", spec=True)


def test_rejecting_after_decompose_returns_the_change_to_analyzed(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-730").step_decompose()
    change = builder.change_dir

    result = apply_decision(change, status="rejected", spec=True)
    assert result["ok"] and result["change_status"] == "analyzed"
    assert _status(change / "change.yaml") == "analyzed"
    assert _status(change / "spec-delta.md") == "rejected"
    assert _status(change / "slices" / "SLICE-01.md") == "draft"
    assert receipt_chain_errors(tmp_path, change) == []
    # No gate ahead opens on the rejected specification.
    with pytest.raises(TransitionError):
        advance_change(change, "decomposed")
    selected = select_next(build_work_queue(tmp_path))
    assert (selected.step, selected.specify_pass) == ("specify", "slice")

    accepted = _accept_again(change)
    assert accepted["ok"], accepted
    # The task was still pending: `decomposed` passes on what is on disk, `declaring` waits.
    assert _status(change / "change.yaml") == "decomposed"
    assert receipt_chain_errors(tmp_path, change) == []
    assert select_next(build_work_queue(tmp_path)).step == "declare"


def test_rejecting_after_implement_takes_the_evidence_of_the_rejected_spec_along(tmp_path: Path, repo_root: Path):
    """The bypass the audit walked: reject at `implemented`, then go on to Verify."""
    builder = _specified(tmp_path, repo_root, "CHG-731").step_decompose().step_declare().step_implement()
    change = builder.change_dir
    (change / "verification.md").write_text("# V\n\n- Outcome: `converged`\n", encoding="utf-8")

    result = apply_decision(change, status="rejected", spec=True)
    assert result["change_status"] == "analyzed" and _status(change / "change.yaml") == "analyzed"
    assert _status(change / "tasks" / "TASK-001.md") == "declared"
    archive = change / "reopened" / "verify.1"
    assert (archive / "verification.md").is_file() and not (change / "verification.md").exists()
    assert (archive / "evidence" / "green" / "TASK-001.yaml").is_file()
    assert not (change / "evidence" / "green" / "TASK-001.yaml").exists()
    assert receipt_chain_errors(tmp_path, change) == []
    with pytest.raises(TransitionError):
        advance_change(change, "converged")
    assert select_next(build_work_queue(tmp_path)).step == "specify"

    assert _accept_again(change)["ok"]
    # decomposed and declaring pass on what is on disk; implemented waits for a fresh Green.
    assert _status(change / "change.yaml") == "declared"
    assert receipt_chain_errors(tmp_path, change) == []
    selected = select_next(build_work_queue(tmp_path))
    assert (selected.step, selected.task) == ("implement", "TASK-001")


def test_a_rejection_before_any_acceptance_still_only_records_the_verdict(tmp_path: Path, repo_root: Path):
    """The twin paths stay as they were: a proposal goes back to `analyzed`, and a Change that
    never proposed keeps its status - the human can always say no."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-732", title="No").step_intake().step_analyze()
    change = builder.change_dir
    (change / "spec-delta.md").write_text(
        "---\nchange: CHG-732\nstatus: proposed\nslices: [SLICE-01]\nadded: []\nmodified: []\nremoved: []\n---\n\n# D\n",
        encoding="utf-8",
    )
    assert apply_decision(change, status="rejected", spec=True)["change_status"] is None
    assert _status(change / "change.yaml") == "analyzing"
    assert receipt_chain_errors(tmp_path, change) == []


def test_the_rejected_change_can_be_closed(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-733").step_decompose()
    change = builder.change_dir
    apply_decision(change, status="rejected", spec=True)
    closed = apply_decision(change, status="rejected", close=True, note="the specification was rejected")
    assert closed["change_status"] == "rejected"
    assert receipt_chain_errors(tmp_path, change) == []


def test_the_human_accepts_the_new_text_by_answering_again(tmp_path: Path, repo_root: Path):
    """The way out the FL-13 refusal names: the human rejects, the Worker proposes, the human accepts."""
    builder = _specified(tmp_path, repo_root, "CHG-734")
    change = builder.change_dir
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(SPEC.replace("SHALL print a banner.", f"SHALL print a banner. {MOVED}."), encoding="utf-8")
    assert _moved(check_gate(change, "decomposed"))

    assert apply_decision(change, status="rejected", spec=True)["change_status"] == "analyzed"
    assert _accept_again(change)["ok"]
    assert not any("changed after the human accepted it" in e for e in check_gate(change, "decomposed"))
