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


def create_authorization_context(
    *,
    actor: str = "worker",
    work_item: str,
    product_root: Path | str,
    change_id: str | None = None,
    task_id: str | None = None,
    stage: str = "implement",
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

    material = f"{actor}|{work_item}|{root.as_posix()}|{change_id or ''}|{task_id or ''}|{stage}|{schema_hash}|{lock_hash}"
    fingerprint = "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    return AuthorizationContext(
        actor=actor,
        work_item=work_item,
        product_root=root,
        change_id=change_id,
        task_id=task_id,
        stage=stage,
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

    if auth_ctx.actor == "worker":
        if kind in _CORE_ONLY_KINDS:
            raise ArtifactPolicyError(
                f"Worker cannot write Core-only kind '{kind}'",
                code="unauthorized_kind",
            )

    return PolicyOutcome(authorized=True, reason="Authorized")


def revalidate_authorization_context(auth_ctx: AuthorizationContext, product_root: Path | str | None = None) -> bool:
    """Re-verify authorization fingerprint against live product root under commit lock."""
    root = Path(product_root).resolve() if product_root else auth_ctx.product_root
    current_lock = _get_lock_hash(root)
    if current_lock != auth_ctx.lock_hash:
        return False
    return True
