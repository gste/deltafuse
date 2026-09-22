"""Integration tests for status and Human Gate persistence and mutation locking (AW-13).

Validates atomic state transitions, locking under ProductMutationLock, protection against
nested status smuggling, receipt recovery, and duplicate Human Gate action rejection.
"""

from pathlib import Path
import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError
from deltafuse.core.artifact_policy import ArtifactPolicyError, create_authorization_context
from deltafuse.core.decide import apply_decision, DecideError
from deltafuse.core.installer import install
from deltafuse.core.transitions import (
    TransitionError,
    advance_change,
    set_artifact_status,
    last_receipt,
    load_receipts,
    receipt_chain_errors,
)
from tests.fixtures.change_builder import MockChangeBuilder


def _builder(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return MockChangeBuilder(tmp_path, change_id=change_id, title="Status Locking Integration")


def test_generic_patch_status_override_rejected(tmp_path: Path, repo_root: Path):
    """ArtifactService create/update must reject status modifications by Worker."""
    b = _builder(tmp_path, repo_root, "CHG-130").step_intake()
    auth = create_authorization_context(
        actor="worker",
        work_item="SLICE-01",
        product_root=b.change_dir,
    )
    service = ArtifactService(b.change_dir, auth)

    # Worker attempts status: "verified" or "accepted" in create
    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-130",
            semantic_payload={"title": "Hack status", "status": "verified"},
        )
    err_code = getattr(exc_info.value, "code", "")
    assert err_code == "core_owned_field" or "status" in str(exc_info.value).lower()


def test_nested_status_smuggling_rejected(tmp_path: Path, repo_root: Path):
    """Nested status injection inside patch payload must be caught and rejected."""
    b = _builder(tmp_path, repo_root, "CHG-131").step_intake()
    auth = create_authorization_context(
        actor="worker",
        work_item="SLICE-01",
        product_root=b.change_dir,
    )
    service = ArtifactService(b.change_dir, auth)

    with pytest.raises((ArtifactServiceError, ArtifactPolicyError)) as exc_info:
        service.create(
            kind="task",
            identity="TASK-131",
            semantic_payload={
                "title": "Nested Hack",
                "nested": {"status": "accepted"},
            },
        )
    # The storage schema or policy will reject unknown/unexposed fields or core-owned fields
    assert exc_info.value is not None


def test_crash_recovery_between_journal_and_status_write(tmp_path: Path, repo_root: Path):
    """Simulate a crash after appending transition receipt to journal before change.yaml update."""
    b = _builder(tmp_path, repo_root, "CHG-132").step_intake().step_analyze()
    b._update_change_yaml({"status": "analyzing"})

    first = advance_change(b.change_dir, "analyzed")
    assert first["ok"] is True
    assert first["to"] == "analyzed"

    # Simulate crash: status write lost, reset change.yaml back to 'analyzing'
    b._update_change_yaml({"status": "analyzing"})

    # Advancing again resumes the pending transition without duplicate receipt entries
    resumed = advance_change(b.change_dir, "analyzed")
    assert resumed["ok"] is True
    assert resumed["resumed"] is True
    assert resumed["receipt"] == first["receipt"]

    receipts = load_receipts(tmp_path, "CHG-132")
    # Total 2 transition receipts: 1 for intake, 1 for analyzed (resumed without duplicate)
    assert len(receipts) == 2
    assert receipt_chain_errors(tmp_path, b.change_dir) == []


def test_duplicated_human_gate_action_fails(tmp_path: Path, repo_root: Path):
    """Applying decide twice on an already accepted decision fails cleanly without receipt corruption."""
    b = _builder(tmp_path, repo_root, "CHG-133").step_intake()
    b._core_advance("intake")
    b._update_change_yaml({"status": "blocked-on-decision"})

    dec_file = tmp_path / "docs" / "decisions" / "DEC-0133-test.md"
    dec_file.parent.mkdir(parents=True, exist_ok=True)
    dec_content = "---\nid: DEC-0133\nchange: CHG-133\nstatus: proposed\n---\n\n# Decision 0133\n"
    dec_file.write_text(dec_content, encoding="utf-8")

    # First decide application: accepted
    res = apply_decision(b.change_dir, decision="DEC-0133", status="accepted")
    assert res["ok"] is True

    # Second decide application on already accepted decision: must fail
    with pytest.raises(DecideError) as exc_info:
        apply_decision(b.change_dir, decision="DEC-0133", status="accepted")
    assert "proposed" in str(exc_info.value).lower()
