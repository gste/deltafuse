"""Unit tests for Core authorization binding, path traversal security, and source identity (AW-06)."""

from pathlib import Path
import pytest

from deltafuse.core.artifact_policy import (
    create_authorization_context,
    resolve_artifact_path,
    validate_artifact_policy,
    revalidate_authorization_context,
    ArtifactPolicyError,
    AuthorizationContext,
)


def test_null_authorization_context_denied(tmp_path: Path):
    target = tmp_path / "docs/changes/CHG-001/tasks/TASK-001.md"
    with pytest.raises(ArtifactPolicyError, match="Null authorization context"):
        validate_artifact_policy(None, kind="task", operation="update", target_path=target)


def test_path_traversal_denied(tmp_path: Path):
    with pytest.raises(ArtifactPolicyError, match="traversal"):
        resolve_artifact_path(tmp_path, "../outside.md")

    with pytest.raises(ArtifactPolicyError, match="traversal"):
        resolve_artifact_path(tmp_path, "docs/changes/CHG-001/../../secret.txt")


def test_protected_deltafuse_path_denied(tmp_path: Path):
    with pytest.raises(ArtifactPolicyError, match="Protected path"):
        resolve_artifact_path(tmp_path, ".deltafuse/lock.yaml")

    with pytest.raises(ArtifactPolicyError, match="Protected path"):
        resolve_artifact_path(tmp_path, ".deltafuse/transitions.jsonl")


def test_windows_device_names_and_ads_denied(tmp_path: Path):
    with pytest.raises(ArtifactPolicyError, match="device name"):
        resolve_artifact_path(tmp_path, "CON.md")

    with pytest.raises(ArtifactPolicyError, match="Alternate Data Streams"):
        resolve_artifact_path(tmp_path, "tasks/TASK-001.md:stream")


def test_symlink_escaping_root_denied(tmp_path: Path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "escaped.md"
    outside_file.write_text("secret", encoding="utf-8")

    prod_root = tmp_path / "repo"
    prod_root.mkdir()
    link_path = prod_root / "symlink.md"

    try:
        link_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation not supported on this platform/privilege")

    with pytest.raises(ArtifactPolicyError, match="escapes product root"):
        resolve_artifact_path(prod_root, "symlink.md")


def test_worker_cannot_write_core_kinds(tmp_path: Path):
    chg_dir = tmp_path / "docs" / "changes" / "CHG-001"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-001\nstatus: active\n", encoding="utf-8")
    ctx = create_authorization_context(
        actor="worker",
        work_item="CHG-001",
        product_root=tmp_path,
        change_id="CHG-001",
        stage="implement",
    )
    target = tmp_path / "docs/changes/CHG-001/evidence/green/TASK-001.yaml"
    with pytest.raises(ArtifactPolicyError, match="Worker cannot write Core-only kind"):
        validate_artifact_policy(ctx, kind="evidence", operation="create", target_path=target)



def test_internal_core_actor_authorization(tmp_path: Path):
    ctx = create_authorization_context(
        actor="core",
        work_item="decide",
        product_root=tmp_path,
        change_id="CHG-001",
        stage="specified",
        internal_auth_token="INTERNAL_CORE_SECRET_TOKEN",
    )
    target = tmp_path / "docs/changes/CHG-001/change.yaml"
    out = validate_artifact_policy(ctx, kind="change", operation="update", target_path=target)
    assert out.authorized is True


def test_forged_actor_core_rejected():
    with pytest.raises(ArtifactPolicyError, match="Internal authentication required"):
        create_authorization_context(
            actor="core",
            work_item="decide",
            product_root=Path("/repo"),
            change_id="CHG-001",
            stage="specified",
        )


def test_revalidate_authorization_context(tmp_path: Path):
    ctx = create_authorization_context(
        actor="worker",
        work_item="CHG-001",
        product_root=tmp_path,
        change_id="CHG-001",
        stage="implement",
    )
    assert revalidate_authorization_context(ctx) is True


def test_aw37_mismatched_change_id_rejected(tmp_path: Path):
    """AW37-R1: Reject a valid-YAML Change whose id differs from directory/owner (e.g. CHG-999 in CHG-905)."""
    chg_dir = tmp_path / "docs" / "changes" / "CHG-905"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-999\nstatus: implementing\n", encoding="utf-8")

    ctx = create_authorization_context(
        actor="worker",
        work_item="CLI",
        product_root=tmp_path,
        change_id="CHG-905",
    )
    target = tmp_path / "docs" / "changes" / "CHG-905" / "tasks" / "TASK-001.md"
    with pytest.raises(ArtifactPolicyError, match="missing, unreadable, or malformed change.yaml"):
        validate_artifact_policy(ctx, kind="task", operation="create", target_path=target)


def test_aw37_invalid_or_invented_stage_rejected(tmp_path: Path):
    """AW37-R2: Reject unknown or invalid lifecycle states such as invented-stage."""
    chg_dir = tmp_path / "docs" / "changes" / "CHG-905"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-905\nstatus: invented-stage\n", encoding="utf-8")

    ctx = create_authorization_context(
        actor="worker",
        work_item="CLI",
        product_root=tmp_path,
        change_id="CHG-905",
    )
    target = tmp_path / "docs" / "changes" / "CHG-905" / "tasks" / "TASK-001.md"
    with pytest.raises(ArtifactPolicyError, match="Worker mutation denied for invalid or unauthorized stage"):
        validate_artifact_policy(ctx, kind="task", operation="create", target_path=target)

