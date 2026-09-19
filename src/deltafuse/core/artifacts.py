"""Typed Artifact Writer service (AW-10).

Wires create, update, validate, and describe operations through one high-level
service interface with transaction sequencing, bounded validation, Core field protection,
and read-only validate/describe guarantees.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from deltafuse.core.artifact_codec import ArtifactCodecError, serialize_artifact
from deltafuse.core.artifact_lock import (
    ArtifactLockError,
    ProductMutationLock,
    check_noop_mutation,
    revalidate_authority,
    validate_expected_hash,
)
from deltafuse.core.artifact_patch import ArtifactPatchError, apply_artifact_patch
from deltafuse.core.artifact_policy import (
    _INTERNAL_CORE_SECRET,
    ArtifactPolicyError,
    AuthorizationContext,
    create_authorization_context,
    resolve_artifact_path,
    validate_artifact_policy,
)
from deltafuse.core.artifact_reader import strict_read_artifact
from deltafuse.core.artifact_registry import ArtifactRegistry, ValidationDiagnostic
from deltafuse.core.artifact_storage import atomic_create, atomic_replace
from deltafuse.core.artifact_transactions import (
    ArtifactTransactionError,
    TransactionManager,
)


class ArtifactServiceError(Exception):
    """Raised when artifact service operations fail."""

    def __init__(self, message: str, *, code: str, path: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.message = message
        self.code = code
        self.path = path


class ArtifactService:
    """Typed Artifact Writer service enforcing schemas, transactions, and ownership invariants."""

    def __init__(
        self,
        product_root: Path,
        auth_context: AuthorizationContext | None = None,
        registry: ArtifactRegistry | None = None,
    ):
        self.product_root = Path(product_root).resolve()
        self.auth_context = auth_context
        self.registry = registry or ArtifactRegistry()
        self._transaction_mgr: TransactionManager | None = None

    @property
    def transaction_mgr(self) -> TransactionManager:
        if self._transaction_mgr is None:
            self._transaction_mgr = TransactionManager(self.product_root)
        return self._transaction_mgr

    def _resolve_target_path(self, kind: str, identity_or_target: str | Path) -> Path:
        raw_str = str(identity_or_target).replace("\\", "/")
        p = Path(identity_or_target)
        if p.is_absolute():
            resolved = p.resolve()
            try:
                resolved.relative_to(self.product_root)
            except ValueError:
                raise ArtifactPolicyError(
                    f"Target absolute path '{identity_or_target}' escapes product root '{self.product_root}'",
                    code="path_traversal_denied",
                    path=str(identity_or_target),
                )
            target_path = resolved
        elif "/" in raw_str or raw_str.endswith(".md") or raw_str.endswith(".yaml"):
            target_path = (self.product_root / raw_str).resolve()
        elif kind == "task":
            target_path = (self.product_root / "tasks" / f"{identity_or_target}.md").resolve()
        elif kind == "slice":
            target_path = (self.product_root / "slices" / f"{identity_or_target}.md").resolve()
        elif kind == "spec-delta":
            target_path = (self.product_root / "spec-delta.md").resolve()
        elif kind == "routing":
            target_path = (self.product_root / "routing.yaml").resolve()
        elif kind == "change":
            target_path = (self.product_root / "change.yaml").resolve()
        else:
            target_path = (self.product_root / f"{identity_or_target}.md").resolve()

        try:
            rel = target_path.relative_to(self.product_root)
            resolve_artifact_path(self.product_root, rel.as_posix())
        except ValueError:
            raise ArtifactPolicyError(
                f"Target path '{identity_or_target}' escapes product root",
                code="path_traversal_denied",
                path=str(identity_or_target),
            )

        if self.auth_context and self.auth_context.change_id and "docs/changes/" in target_path.as_posix():
            expected_prefix = (self.product_root / "docs" / "changes" / self.auth_context.change_id).as_posix()
            if not target_path.as_posix().startswith(expected_prefix) and self.product_root.name != self.auth_context.change_id:
                raise ArtifactPolicyError(
                    f"Target path '{identity_or_target}' outside Change boundary '{self.auth_context.change_id}'",
                    code="change_boundary_violation",
                    path=str(identity_or_target),
                )

        return target_path

    def create(
        self,
        kind: str,
        identity: str,
        semantic_payload: dict[str, Any],
        body: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new artifact atomically under schema and policy protection."""
        if not isinstance(semantic_payload, dict):
            raise ArtifactServiceError(
                "semantic_payload must be a dictionary",
                code="invalid_payload",
            )

        for core_field in ("status", "schema_version", "framework"):
            if core_field in semantic_payload:
                raise ArtifactPolicyError(
                    f"Field '{core_field}' is Core-owned and cannot be supplied in create",
                    code="core_owned_field",
                )

        target_path = self._resolve_target_path(kind, identity)

        outcome = validate_artifact_policy(self.auth_context, kind=kind, operation="create", target_path=target_path)
        if not outcome.authorized:
            raise ArtifactPolicyError(outcome.reason, code="policy_denied", path=str(target_path))

        descriptor = self.registry.get_descriptor(kind)
        allowed_fields = descriptor.get("creatable_semantic_fields") or descriptor.get("allowed_semantic_fields") or []

        for k in semantic_payload.keys():
            if allowed_fields and k not in allowed_fields:
                raise ArtifactServiceError(
                    f"Field '{k}' is not an allowed semantic field for kind '{kind}' create",
                    code="unexposed_field",
                )

        initial_status = "pending" if kind == "task" else "draft" if kind == "slice" else "proposed" if kind == "spec-delta" else "active"
        raw_change = getattr(self.auth_context, "change_id", None) or "CHG-001"
        change_id = raw_change if re.match(r"^CHG-[0-9]{3,}", raw_change) else "CHG-001"

        if kind == "task":
            raw_slice = getattr(self.auth_context, "work_item", None) or "SLICE-01"
            slice_id = raw_slice if re.match(r"^SLICE-[0-9]{2,}", raw_slice) else "SLICE-01"
            defaults = {
                "slice": slice_id,
                "kind": semantic_payload.get("kind", "feature"),
                "depends_on": [],
                "requirement_delta": "none",
                "spec_refs": ["docs/spec/overview.md"],
                "allowed_paths": [],
                "forbidden_paths": [],
                "context_budget": {"max_tokens": 100000, "max_files": 20},
            }
        else:
            defaults = {}

        metadata = {
            "id": identity,
            "change": change_id,
            "status": initial_status,
            **defaults,
            **semantic_payload,
        }
        if kind not in ("task", "slice"):
            metadata.pop("id", None)

        if kind == "task" and "title" in metadata:
            title_text = metadata.pop("title")
            if not body.strip().startswith("#"):
                body = f"# {identity}: {title_text}\n\n{body}"

        val_res = self.registry.validate_storage_schema(kind, metadata)
        if not val_res.valid:
            diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
            raise ArtifactServiceError(
                f"Storage schema validation failed for create '{kind}': {'; '.join(diag_msgs)}",
                code="schema_validation_failed",
                path=str(target_path),
            )

        content_str = serialize_artifact(metadata, body, kind=kind)
        content_bytes = content_str.encode("utf-8")
        expected_sha256 = hashlib.sha256(content_bytes).hexdigest()

        req_id = request_id or f"req-{hashlib.sha256(content_bytes).hexdigest()[:16]}"
        raw_req_bytes = json.dumps({"kind": kind, "identity": identity, "payload": semantic_payload}, sort_keys=True).encode("utf-8")

        with ProductMutationLock(self.product_root):
            revalidate_authority(self.auth_context, lambda: self.auth_context)

            tx = self.transaction_mgr.prepare_transaction(
                request_id=req_id,
                raw_request_bytes=raw_req_bytes,
                kind=kind,
                target_path=target_path,
                previous_sha256=None,
                expected_result_sha256=expected_sha256,
                auth_context=self.auth_context,
                operation="create",
            )

            if tx.get("state") == "committed":
                return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="committed", changed=True)

            atomic_create(target_path, content_bytes)
            self.transaction_mgr.mark_published(tx["transaction_id"])
            return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="committed", changed=True)

    def update(
        self,
        kind: str,
        target: str | Path,
        expected_sha256: str,
        patch: dict[str, Any],
        body_replacement: str | None = None,
        request_id: str | None = None,
        canonicalize_metadata: bool = False,
    ) -> dict[str, Any]:
        """Update an existing artifact atomically using typed JSON pointer patches."""
        target_path = self._resolve_target_path(kind, target)

        if not target_path.is_file():
            raise ArtifactServiceError(
                f"Target artifact '{target_path}' does not exist for update",
                code="target_not_found",
                path=str(target_path),
            )

        outcome = validate_artifact_policy(self.auth_context, kind=kind, operation="update", target_path=target_path)
        if not outcome.authorized:
            raise ArtifactPolicyError(outcome.reason, code="policy_denied", path=str(target_path))

        existing_bytes = target_path.read_bytes()
        validate_expected_hash(target_path, expected_sha256)

        has_frontmatter = not target_path.name.endswith((".yaml", ".yml"))
        parse_res = strict_read_artifact(existing_bytes, has_frontmatter_delimiters=has_frontmatter)
        existing_meta = parse_res.metadata
        existing_body = parse_res.raw_body

        patch_outcome = apply_artifact_patch(
            existing_meta,
            patch,
            kind=kind,
            body=existing_body,
            body_replacement=body_replacement,
            registry=self.registry,
        )

        updated_meta = patch_outcome.updated_metadata
        body_text = patch_outcome.updated_body

        if kind == "task" and "title" in updated_meta:
            title_text = updated_meta.pop("title")
            body_text = f"# {updated_meta.get('id', 'TASK')}: {title_text}\n\n" + re.sub(r"^# [^\n]*\n*", "", body_text)

        val_res = self.registry.validate_storage_schema(kind, updated_meta)
        if not val_res.valid:
            diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
            raise ArtifactServiceError(
                f"Storage schema validation failed for update '{kind}': {'; '.join(diag_msgs)}",
                code="schema_validation_failed",
                path=str(target_path),
            )

        canon_optin = canonicalize_metadata or bool(patch.get("canonicalize_metadata", False))
        existing_text = existing_bytes.decode("utf-8")
        try:
            candidate_str = serialize_artifact(
                updated_meta,
                body_text,
                kind=kind,
                existing_raw_content=existing_text,
                canonicalize_metadata=canon_optin,
                has_frontmatter_delimiters=has_frontmatter,
            )
        except ArtifactCodecError as ex:
            raise ArtifactServiceError(
                str(ex),
                code="invalid_payload" if ex.code == "format_change_required" else ex.code,
                path=str(target_path),
            ) from ex

        candidate_bytes = candidate_str.encode("utf-8")
        candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()

        if check_noop_mutation(existing_bytes, candidate_bytes):
            req_id = request_id or f"req-noop-{hashlib.sha256(candidate_bytes).hexdigest()[:16]}"
            raw_req_bytes = json.dumps({"kind": kind, "target": str(target_path), "patch": patch}, sort_keys=True).encode("utf-8")
            tx = self.transaction_mgr.prepare_transaction(
                request_id=req_id,
                raw_request_bytes=raw_req_bytes,
                kind=kind,
                target_path=target_path,
                previous_sha256=expected_sha256,
                expected_result_sha256=expected_sha256,
                auth_context=self.auth_context,
                operation="update",
            )
            return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="unchanged", changed=False)

        req_id = request_id or f"req-{hashlib.sha256(candidate_bytes).hexdigest()[:16]}"
        raw_req_bytes = json.dumps({"kind": kind, "target": str(target_path), "patch": patch}, sort_keys=True).encode("utf-8")

        with ProductMutationLock(self.product_root):
            validate_expected_hash(target_path, expected_sha256)
            revalidate_authority(self.auth_context, lambda: self.auth_context)

            tx = self.transaction_mgr.prepare_transaction(
                request_id=req_id,
                raw_request_bytes=raw_req_bytes,
                kind=kind,
                target_path=target_path,
                previous_sha256=expected_sha256,
                expected_result_sha256=candidate_sha256,
                auth_context=self.auth_context,
                operation="update",
            )

            if tx.get("state") == "committed":
                return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="committed", changed=True)

            atomic_replace(target_path, candidate_bytes, expected_sha256=expected_sha256)
            self.transaction_mgr.mark_published(tx["transaction_id"])
            return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="committed", changed=True)

    def validate(self, kind: str, target: str | Path) -> dict[str, Any]:
        """Strictly read-only validation check. Does NOT open transactions or alter files."""
        target_path = self._resolve_target_path(kind, target)

        if not target_path.is_file():
            return {
                "valid": False,
                "target": str(target_path),
                "scopes": ["input", "schema"],
                "diagnostics": [
                    {
                        "code": "file_not_found",
                        "json_pointer": "",
                        "stage": "input",
                        "message": f"Target file '{target_path}' does not exist",
                    }
                ],
            }

        content_bytes = target_path.read_bytes()
        try:
            has_frontmatter = not target_path.name.endswith((".yaml", ".yml"))
            parse_res = strict_read_artifact(content_bytes, has_frontmatter_delimiters=has_frontmatter)
        except Exception as ex:
            return {
                "valid": False,
                "target": str(target_path),
                "scopes": ["input"],
                "diagnostics": [
                    {
                        "code": "parse_error",
                        "json_pointer": "",
                        "stage": "input",
                        "message": f"Failed to parse frontmatter: {ex}",
                    }
                ],
            }

        val_res = self.registry.validate_storage_schema(kind, parse_res.metadata)
        diags = [
            {
                "code": d.code,
                "json_pointer": d.path,
                "stage": d.stage,
                "message": d.message,
            }
            for d in val_res.diagnostics
        ]

        return {
            "valid": val_res.valid,
            "target": str(target_path),
            "scopes": ["input", "schema", "policy"],
            "diagnostics": diags,
        }

    def describe(self, kind: str, operation: str = "create") -> dict[str, Any]:
        """Strictly read-only inspection of per-kind operation descriptor."""
        descriptor = self.registry.get_descriptor(kind)
        return {
            "kind": kind,
            "operation": operation,
            "allowed_semantic_fields": descriptor.get("creatable_semantic_fields") or descriptor.get("allowed_semantic_fields") or [],
            "core_owned_fields": descriptor.get("core_owned_fields") or ["id", "change", "status", "schema_version", "framework"],
            "schema_id": f"https://deltafuse.dev/schemas/v3/{kind}.schema.yaml",
            "schema_version": "3",
        }
