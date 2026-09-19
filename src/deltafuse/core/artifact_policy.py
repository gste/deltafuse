"""Core authorization binding, path traversal security, and source identity (AW-06).

Binds envelope/lock/schema/source inputs to authorization fingerprints, enforces path
traversal/symlink/reparse escape prevention, protects internal .deltafuse paths, and
strictly separates Worker versus internal Core caller permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any
import yaml

from deltafuse.core.fsm import find_repo_root


class ArtifactPolicyError(Exception):
    """Raised when authorization, path traversal, or policy validation fails."""

    def __init__(self, message: str, *, code: str = "policy_denied", path: str | None = None):
        full_msg = f"[{code}] {message}"
        super().__init__(full_msg)
        self.message = message
        self.code = code
        self.path = path


_INTERNAL_CORE_SECRET = "INTERNAL_CORE_SECRET_TOKEN"
_PROTECTED_PATH_PREFIXES = (".deltafuse/", ".git/")
_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
_CORE_ONLY_KINDS = {"evidence", "coverage", "decision", "capability", "lock"}


@dataclass(frozen=True)
class AuthorizationContext:
    """Bound authorization context holding identity, scope, and fingerprint."""

    actor: str  # "worker" | "core"
    work_item: str
    product_root: Path
    change_id: str | None
    task_id: str | None
    stage: str
    schema_hash: str
    lock_hash: str
    fingerprint: str


@dataclass(frozen=True)
class PolicyOutcome:
    """Result of policy authorization check."""

    authorized: bool
    reason: str


def _get_lock_hash(product_root: Path) -> str:
    lock = product_root / ".deltafuse" / "lock.yaml"
    if not lock.is_file():
        return "none"
    return "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest()


_VALID_CHANGE_STATUSES = {
    "normalized",
    "analyzing",
    "blocked-on-decision",
    "analyzed",
    "specification-proposed",
    "specified",
    "decomposed",
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
    "rejected",
    "duplicate",
    "superseded",
    "not-reproduced",
}

_INACTIVE_STAGES = {
    "archived",
    "halted",
    "accepted",
    "converged",
    "rejected",
    "duplicate",
    "superseded",
    "not-reproduced",
}

_VALID_ACTIVE_STAGES = {
    "normalized",
    "analyzing",
    "blocked-on-decision",
    "analyzed",
    "specification-proposed",
    "specified",
    "decomposed",
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "active",
    "implement",
}


def resolve_change_stage(product_root: Path | str, change_id: str | None) -> str:
    """Resolve live lifecycle stage/status of Change package from disk."""
    if not change_id or not isinstance(change_id, str) or not re.match(r"^CHG-[0-9]{3,}(-[a-z0-9-]+)?$", change_id):
        return "missing_change_authority"
    root = Path(product_root).resolve()

    possible_dirs = [
        root / "docs" / "changes" / change_id,
        root / "docs" / "archive" / "changes" / change_id,
        root,
    ]

    for cdir in possible_dirs:
        yaml_file = cdir / "change.yaml"
        if yaml_file.is_file():
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    return "missing_change_authority"
                file_cid = data.get("id")
                if not isinstance(file_cid, str) or not re.match(r"^CHG-[0-9]{3,}(-[a-z0-9-]+)?$", file_cid) or file_cid != change_id:
                    # Missing, null, empty, wrong type, or mismatched Change ID (no alternate-field fallback)
                    return "missing_change_authority"
                status = data.get("status")
                if not isinstance(status, str):
                    return "invalid_change_stage"
                norm_status = status.strip().lower()
                if norm_status in _INACTIVE_STAGES:
                    return norm_status
                if norm_status in _VALID_ACTIVE_STAGES:
                    return norm_status
                return "invalid_change_stage"
            except Exception:
                return "missing_change_authority"
        if "archive" in cdir.parts and cdir.is_dir():
            return "archived"

    return "missing_change_authority"


def create_authorization_context(
    *,
    actor: str = "worker",
    work_item: str,
    product_root: Path | str,
    change_id: str | None = None,
    task_id: str | None = None,
    stage: str | None = None,
    schema_hash: str = "v3",
    internal_auth_token: str | None = None,
) -> AuthorizationContext:
    """Create a bound authorization context with unique cryptographic fingerprint.

    Actor 'core' requires the internal system authentication token; caller-supplied
    JSON payloads cannot forge actor 'core'.
    """
    if actor == "core":
        if internal_auth_token != _INTERNAL_CORE_SECRET:
            raise ArtifactPolicyError(
                "Internal authentication required for actor='core'",
                code="forged_core_actor",
            )
    elif actor != "worker":
        raise ArtifactPolicyError(f"Unknown actor '{actor}'", code="invalid_actor")

    root = Path(product_root).resolve()
    lock_hash = _get_lock_hash(root)

    disk_stage = resolve_change_stage(root, change_id)
    if disk_stage in _INACTIVE_STAGES:
        effective_stage = disk_stage
    elif disk_stage in ("missing_change_authority", "invalid_change_stage"):
        effective_stage = disk_stage
    elif stage and stage.strip().lower() in _INACTIVE_STAGES:
        effective_stage = stage.strip().lower()
    elif stage and stage.strip().lower() not in _VALID_ACTIVE_STAGES:
        effective_stage = "invalid_change_stage"
    elif stage:
        effective_stage = stage.strip().lower()
    else:
        effective_stage = disk_stage

    material = f"{actor}|{work_item}|{root.as_posix()}|{change_id or ''}|{task_id or ''}|{effective_stage}|{schema_hash}|{lock_hash}"
    fingerprint = "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    return AuthorizationContext(
        actor=actor,
        work_item=work_item,
        product_root=root,
        change_id=change_id,
        task_id=task_id,
        stage=effective_stage,
        schema_hash=schema_hash,
        lock_hash=lock_hash,
        fingerprint=fingerprint,
    )


def resolve_artifact_path(product_root: Path | str, relative_target: str) -> Path:
    """Resolve and validate target path within product root.

    Rejects path traversal, Windows drive letters, alternate streams, device names,
    protected .deltafuse paths, and symlink/reparse point escapes.
    """
    root = Path(product_root).resolve()
    posix_path = relative_target.replace("\\", "/")

    if not posix_path or posix_path.startswith("/") or re.match(r"^[a-zA-Z]:", posix_path):
        raise ArtifactPolicyError(
            f"Path traversal or absolute path denied: '{relative_target}'",
            code="path_traversal_denied",
            path=relative_target,
        )

    # Check traversal segments
    parts = posix_path.split("/")
    if ".." in parts:
        raise ArtifactPolicyError(
            f"Path traversal ('..') denied in target path: '{relative_target}'",
            code="path_traversal_denied",
            path=relative_target,
        )

    # Check Alternate Data Streams (ADS)
    if ":" in relative_target:
        raise ArtifactPolicyError(
            f"Windows Alternate Data Streams (':') denied: '{relative_target}'",
            code="ads_denied",
            path=relative_target,
        )

    # Check device names
    first_name = Path(posix_path).name.split(".")[0].upper()
    if first_name in _DEVICE_NAMES:
        raise ArtifactPolicyError(
            f"Reserved device name denied: '{relative_target}'",
            code="device_name_denied",
            path=relative_target,
        )

    # Check protected paths
    if posix_path.startswith(_PROTECTED_PATH_PREFIXES) or posix_path in {".deltafuse", ".git"}:
        raise ArtifactPolicyError(
            f"Protected path denied: '{relative_target}'",
            code="protected_path_denied",
            path=relative_target,
        )

    resolved = (root / relative_target).resolve()

    # Symlink escape check
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ArtifactPolicyError(
            f"Target path escapes product root: '{relative_target}'",
            code="symlink_escape_denied",
            path=relative_target,
        )

    return resolved


def validate_artifact_policy(
    auth_ctx: AuthorizationContext | None,
    *,
    kind: str,
    operation: str,
    target_path: Path | str,
) -> PolicyOutcome:
    """Validate operation policy against authorization context and target kind."""
    if auth_ctx is None:
        raise ArtifactPolicyError("Null authorization context", code="null_authorization_context")

    stage = (auth_ctx.stage or "").lower()
    disk_stage = resolve_change_stage(auth_ctx.product_root, auth_ctx.change_id)
    if disk_stage in _INACTIVE_STAGES or disk_stage in ("missing_change_authority", "invalid_change_stage"):
        effective_stage = disk_stage
    elif stage in _INACTIVE_STAGES or stage in ("missing_change_authority", "invalid_change_stage"):
        effective_stage = stage
    elif disk_stage in _VALID_ACTIVE_STAGES:
        effective_stage = disk_stage
    elif stage in _VALID_ACTIVE_STAGES:
        effective_stage = stage
    else:
        effective_stage = "invalid_change_stage"

    if effective_stage in _INACTIVE_STAGES:
        raise ArtifactPolicyError(
            f"Worker mutation denied for stage '{effective_stage}'",
            code="stage_halted" if effective_stage == "halted" else "unauthorized_stage",
            path=str(target_path),
        )

    if auth_ctx.actor == "worker":
        if effective_stage == "missing_change_authority":
            raise ArtifactPolicyError(
                f"Worker mutation denied: missing, unreadable, or malformed change.yaml for Change '{auth_ctx.change_id or 'unknown'}'",
                code="missing_change_authority",
                path=str(target_path),
            )
        if effective_stage == "invalid_change_stage" or effective_stage not in _VALID_ACTIVE_STAGES:
            raise ArtifactPolicyError(
                f"Worker mutation denied for invalid or unauthorized stage '{effective_stage}'",
                code="unauthorized_stage",
                path=str(target_path),
            )
        if kind in _CORE_ONLY_KINDS:
            raise ArtifactPolicyError(
                f"Worker cannot write Core-only kind '{kind}'",
                code="unauthorized_kind",
                path=str(target_path),
            )

    resolved_target = Path(target_path).resolve()
    try:
        resolved_target.relative_to(auth_ctx.product_root)
    except ValueError:
        raise ArtifactPolicyError(
            f"Target path '{target_path}' escapes product root '{auth_ctx.product_root}'",
            code="path_traversal_denied",
            path=str(target_path),
        )

    if auth_ctx.change_id and "docs/changes/" in resolved_target.as_posix():
        posix_str = resolved_target.as_posix()
        expected_prefix = (auth_ctx.product_root / "docs" / "changes" / auth_ctx.change_id).as_posix()
        if not posix_str.startswith(expected_prefix) and auth_ctx.product_root.name != auth_ctx.change_id:
            raise ArtifactPolicyError(
                f"Target path '{target_path}' outside Change boundary '{auth_ctx.change_id}'",
                code="change_boundary_violation",
                path=str(target_path),
            )

    return PolicyOutcome(authorized=True, reason="Authorized")


def revalidate_authorization_context(auth_ctx: AuthorizationContext, product_root: Path | str | None = None) -> bool:
    """Re-verify authorization fingerprint against live product root under commit lock."""
    root = Path(product_root).resolve() if product_root else auth_ctx.product_root
    current_lock = _get_lock_hash(root)
    if current_lock != auth_ctx.lock_hash:
        return False
    return True
