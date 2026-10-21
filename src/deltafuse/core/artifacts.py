"""Typed Artifact Writer service (AW-10).

Wires create, update, validate, and describe operations through one high-level
service interface with transaction sequencing, bounded validation, Core field protection,
and read-only validate/describe guarantees.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from deltafuse.core.artifact_codec import ArtifactCodecError, serialize_artifact
from deltafuse.core.artifact_lock import (
    ProductMutationLock,
    check_noop_mutation,
    revalidate_authority,
    validate_expected_hash,
)
from deltafuse.core.artifact_patch import apply_artifact_patch
from deltafuse.core.artifact_policy import (
    ArtifactPolicyError,
    AuthorizationContext,
    resolve_artifact_path,
    validate_artifact_policy,
)
from deltafuse.core.artifact_reader import strict_read_artifact
from deltafuse.core.artifact_registry import ArtifactRegistry
from deltafuse.core.artifact_storage import atomic_create, atomic_replace
from deltafuse.core.artifact_transactions import (
    ArtifactTransactionError,
    TransactionManager,
    recover_pending_transactions,
)


class ArtifactServiceError(Exception):
    """Raised when artifact service operations fail."""

    def __init__(self, message: str, *, code: str, path: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.message = message
        self.code = code
        self.path = path


def verify_published_artifact(
    target_path: Path,
    expected_sha256: str,
    kind: str,
    registry: ArtifactRegistry,
) -> None:
    """Verify published target artifact on disk before transaction receipt finalization."""
    from deltafuse.core.artifact_storage import verify_published_target_readback, ArtifactStorageError
    try:
        live_bytes = verify_published_target_readback(target_path, expected_sha256)
    except ArtifactStorageError as ex:
        raise ArtifactTransactionError(ex.message, code="readback_verification_failed", path=str(target_path)) from ex

    try:
        has_frontmatter = not target_path.name.endswith((".yaml", ".yml"))
        parse_res = strict_read_artifact(live_bytes, has_frontmatter_delimiters=has_frontmatter)
    except Exception as ex:
        raise ArtifactTransactionError(
            f"Strict parsing failed on published target readback '{target_path}': {ex}",
            code="readback_verification_failed",
            path=str(target_path),
        ) from ex

    val_res = registry.validate_storage_schema(kind, parse_res.metadata)
    if not val_res.valid:
        diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
        raise ArtifactTransactionError(
            f"Storage schema validation failed on published target readback '{target_path}': {'; '.join(diag_msgs)}",
            code="readback_verification_failed",
            path=str(target_path),
        )


class ArtifactService:
    """Typed Artifact Writer service enforcing schemas, transactions, and ownership invariants."""

    def __init__(
        self,
        product_root: Path,
        auth_context: AuthorizationContext | None = None,
        registry: ArtifactRegistry | None = None,
        change_dir: Path | None = None,
    ):
        from deltafuse.core.artifact_lock import resolve_product_root
        raw_root = Path(product_root).resolve()
        self.product_root = resolve_product_root(raw_root)
        self.change_dir = Path(change_dir).resolve() if change_dir else raw_root
        self.auth_context = auth_context
        self.registry = registry or ArtifactRegistry(self.product_root)
        self._transaction_mgr: TransactionManager | None = None

    @property
    def transaction_mgr(self) -> TransactionManager:
        if self._transaction_mgr is None:
            self._transaction_mgr = TransactionManager(self.product_root, change_dir=self.change_dir)
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
            target_path = (self.change_dir / raw_str).resolve()
        elif kind == "task":
            target_path = (self.change_dir / "tasks" / f"{identity_or_target}.md").resolve()
        elif kind == "slice":
            target_path = (self.change_dir / "slices" / f"{identity_or_target}.md").resolve()
        elif kind == "spec-delta":
            target_path = (self.change_dir / "spec-delta.md").resolve()
        elif kind == "routing":
            target_path = (self.change_dir / "routing.yaml").resolve()
        elif kind == "change":
            target_path = (self.change_dir / "change.yaml").resolve()
        elif kind == "decision":
            # Decisions live at the product root, not inside the Change.
            target_path = (self.product_root / "docs" / "decisions" / f"{identity_or_target}.md").resolve()
        else:
            target_path = (self.change_dir / f"{identity_or_target}.md").resolve()

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

    def _get_live_auth_context(self) -> AuthorizationContext | None:
        if not self.auth_context:
            return None
        from deltafuse.core.artifact_policy import resolve_change_stage, _INACTIVE_STAGES, _VALID_ACTIVE_STAGES
        root = Path(self.product_root).resolve()
        disk_stage = resolve_change_stage(root, self.auth_context.change_id)
        if disk_stage in _INACTIVE_STAGES or disk_stage in ("missing_change_authority", "invalid_change_stage") or disk_stage not in _VALID_ACTIVE_STAGES:
            import dataclasses
            return dataclasses.replace(self.auth_context, stage=disk_stage)
        return self.auth_context

    @staticmethod
    def _check_request_id(request_id: str | None) -> None:
        if request_id and not re.match(r"^[a-zA-Z0-9_\-]+$", request_id):
            raise ArtifactServiceError(
                f"Invalid request_id pattern: '{request_id}'",
                code="invalid_envelope",
            )

    @staticmethod
    def _require_valid(result: Any, message: str, code: str, target_path: Path) -> None:
        if not result.valid:
            diag_msgs = [f"{d.path}: {d.message}" for d in result.diagnostics]
            raise ArtifactServiceError(f"{message}: {'; '.join(diag_msgs)}", code=code, path=str(target_path))

    def _request_bytes(self, request: dict[str, Any]) -> bytes:
        """The canonical request bytes the idempotency hash covers, with the authority snapshot."""
        request["auth_context"] = {
            "actor": getattr(self.auth_context, "actor", None),
            "work_item": getattr(self.auth_context, "work_item", None),
            "stage": getattr(self.auth_context, "stage", None),
            "change_id": getattr(self.auth_context, "change_id", None),
            "fingerprint": getattr(self.auth_context, "fingerprint", None),
        } if self.auth_context else None
        return json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")

    @contextlib.contextmanager
    def _mutation(self):
        """Hold the product lock, recheck live authority and recover interrupted transactions."""
        with ProductMutationLock(self.product_root):
            revalidate_authority(self.auth_context, lambda: self._get_live_auth_context())
            recover_pending_transactions(self.product_root)
            yield

    def _committed_receipt(
        self, tx: dict[str, Any], durable_outcome: str = "committed", changed: bool = True
    ) -> dict[str, Any] | None:
        if tx.get("state") != "committed":
            return None
        receipt = self.transaction_mgr.get_receipt(tx["transaction_id"])
        if receipt:
            return receipt
        return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome=durable_outcome, changed=changed)

    def _replay(self, req_id: str, raw_req_hash: str, recorded_outcome: bool) -> dict[str, Any] | None:
        """The receipt of an already committed request, or None; a reused id with another payload is refused."""
        existing_tx = self.transaction_mgr.find_transaction_by_request_id(req_id)
        if existing_tx is None:
            return None
        if existing_tx.get("raw_request_hash") != raw_req_hash:
            raise ArtifactTransactionError(
                f"Request ID '{req_id}' re-used with different payload",
                code="idempotency_conflict",
            )
        if recorded_outcome:
            return self._committed_receipt(
                existing_tx, existing_tx.get("outcome", "committed"), existing_tx.get("changed", True)
            )
        return self._committed_receipt(existing_tx)

    def _prepare(
        self,
        req_id: str,
        raw_req_bytes: bytes,
        kind: str,
        target_path: Path,
        operation: str,
        previous_sha256: str | None,
        result_sha256: str,
        payload_sha256: str,
        schema_hashes: tuple[str, str],
    ) -> dict[str, Any]:
        return self.transaction_mgr.prepare_transaction(
            request_id=req_id,
            raw_request_bytes=raw_req_bytes,
            normalized_payload_hash=payload_sha256,
            kind=kind,
            target_path=target_path,
            previous_sha256=previous_sha256,
            expected_result_sha256=result_sha256,
            auth_context=self.auth_context,
            operation=operation,
            operation_schema_hash=schema_hashes[0],
            storage_schema_hash=schema_hashes[1],
        )

    def _publish(
        self,
        tx: dict[str, Any],
        kind: str,
        target_path: Path,
        content_bytes: bytes,
        result_sha256: str,
        previous_sha256: str | None,
    ) -> dict[str, Any]:
        """Publish the prepared bytes, read them back, then finalize the receipt."""
        receipt = self._committed_receipt(tx)
        if receipt is not None:
            return receipt

        if previous_sha256 is None:
            atomic_create(target_path, content_bytes)
        else:
            atomic_replace(target_path, content_bytes, expected_sha256=previous_sha256)
        self.transaction_mgr.mark_published(tx["transaction_id"])
        try:
            verify_published_artifact(
                target_path=target_path,
                expected_sha256=result_sha256,
                kind=kind,
                registry=self.registry,
            )
        except Exception as ex:
            self.transaction_mgr.mark_readback_failed(tx["transaction_id"], str(ex))
            if isinstance(ex, ArtifactTransactionError):
                raise
            raise ArtifactTransactionError(
                f"Readback verification failed after publication of '{target_path}': {ex}",
                code="readback_verification_failed",
                path=str(target_path),
            ) from ex

        try:
            return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="committed", changed=True)
        except ArtifactTransactionError:
            raise
        except Exception as ex:
            raise ArtifactTransactionError(
                f"Receipt finalization failed after publication of '{target_path}': {ex}",
                code="receipt_finalization_failed",
                path=str(target_path),
            ) from ex

    def create(
        self,
        kind: str,
        identity: str,
        semantic_payload: dict[str, Any],
        body: str = "",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new artifact atomically under schema and policy protection."""
        self.registry.verify_product_lock(self.product_root)
        self._check_request_id(request_id)

        if not isinstance(semantic_payload, dict):
            raise ArtifactServiceError(
                "semantic_payload must be a JSON mapping",
                code="invalid_payload",
            )

        for core_field in ("id", "change", "status", "schema_version", "framework"):
            if core_field in semantic_payload:
                raise ArtifactServiceError(
                    f"Cannot write Core-owned field '{core_field}' through semantic_payload",
                    code="core_owned_field",
                )

        target_path = self._resolve_target_path(kind, identity)

        outcome = validate_artifact_policy(self.auth_context, kind=kind, operation="create", target_path=target_path)
        if not outcome.authorized:
            raise ArtifactPolicyError(outcome.reason, code="policy_denied", path=str(target_path))

        descriptor = self.registry.get_descriptor(kind)
        allowed_fields = descriptor.get("creatable_semantic_fields") or descriptor.get("allowed_semantic_fields") or []

        # cls-g31s-m02 (2026-10-04): told only that 'kind' was not allowed, the Worker sent
        # the same fields nine times; the refusal now names the fields that are.
        for k in semantic_payload.keys():
            if allowed_fields and k not in allowed_fields:
                raise ArtifactServiceError(
                    f"Field '{k}' is not an allowed semantic field for kind '{kind}' create. "
                    f"Allowed fields: {', '.join(sorted(allowed_fields))}.",
                    code="unexposed_field",
                )

        if not self.auth_context:
            raise ArtifactPolicyError("No authorization context provided", code="policy_denied")

        raw_change = getattr(self.auth_context, "change_id", None)
        if not raw_change or not re.match(r"^CHG-[0-9]{3,}", str(raw_change)):
            raise ArtifactPolicyError(
                f"Missing or invalid change authorization context: '{raw_change}'",
                code="missing_core_context",
            )
        change_id = str(raw_change)

        payload_copy = dict(semantic_payload)

        if kind == "task":
            raw_slice = payload_copy.pop("slice", None)
            if not raw_slice and self.auth_context and self.auth_context.work_item:
                if re.match(r"^SLICE-[0-9]{2,}", str(self.auth_context.work_item)):
                    raw_slice = self.auth_context.work_item

            if not raw_slice or not re.match(r"^SLICE-[0-9]{2,}", str(raw_slice)):
                raise ArtifactPolicyError(
                    f"Missing or invalid slice in payload or authorization context: '{raw_slice}'",
                    code="missing_core_context",
                )

            if (
                self.auth_context
                and self.auth_context.work_item
                and re.match(r"^SLICE-[0-9]{2,}", str(self.auth_context.work_item))
                and str(raw_slice) != str(self.auth_context.work_item)
            ):
                raise ArtifactPolicyError(
                    f"Payload slice '{raw_slice}' conflicts with authorized work_item '{self.auth_context.work_item}'",
                    code="policy_denied",
                )

            slice_id = str(raw_slice)
        else:
            slice_id = None

        initial_status = "pending" if kind == "task" else "draft" if kind == "slice" else "proposed" if kind in ("spec-delta", "decision") else "active"
        if kind == "task":
            title_text = payload_copy.pop("title", None)
            if title_text:
                if not body.strip().startswith("#"):
                    body = f"# {identity}: {title_text}\n\n{body}"
            else:
                first_line = body.strip().split("\n")[0] if body.strip() else ""
                if not first_line.startswith("#"):
                    raise ArtifactServiceError(
                        "Task creation requires a title either in semantic_payload or as a markdown header in body",
                        code="required_property_missing",
                        path="/title",
                    )

        metadata = {
            "id": identity,
            "change": change_id,
            "status": initial_status,
            **payload_copy,
        }
        if kind == "task":
            metadata["slice"] = slice_id

        if kind not in ("task", "slice", "decision"):
            metadata.pop("id", None)

        self._require_valid(
            self.registry.validate_storage_schema(kind, metadata),
            f"Storage schema validation failed for create '{kind}'", "schema_validation_failed", target_path,
        )
        self._require_valid(
            self.registry.validate_references(
                kind,
                metadata,
                product_root=self.product_root,
                change_dir=self.change_dir,
                change_id=change_id,
            ),
            f"Reference validation failed for create '{kind}'", "missing_reference", target_path,
        )

        content_str = serialize_artifact(metadata, body, kind=kind)
        content_bytes = content_str.encode("utf-8")
        expected_sha256 = hashlib.sha256(content_bytes).hexdigest()

        req_id = request_id or f"req-{expected_sha256[:16]}"
        raw_req_bytes = self._request_bytes({
            "operation": "create",
            "kind": kind,
            "identity": identity,
            "target": str(target_path),
            "semantic_payload": semantic_payload,
            "body": body,
        })
        raw_req_hash = hashlib.sha256(raw_req_bytes).hexdigest()

        schema_hashes = (self.registry.get_descriptor_hash(kind), self.registry.get_storage_schema_hash(kind))

        with self._mutation():
            receipt = self._replay(req_id, raw_req_hash, recorded_outcome=False)
            if receipt is not None:
                return receipt
            tx = self._prepare(
                req_id, raw_req_bytes, kind, target_path, "create",
                None, expected_sha256, expected_sha256, schema_hashes,
            )
            return self._publish(tx, kind, target_path, content_bytes, expected_sha256, None)

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
        self.registry.verify_product_lock(self.product_root)
        self._check_request_id(request_id)
        if not expected_sha256 or not re.match(r"^(sha256:[a-fA-F0-9]{64}|[a-fA-F0-9]{64})$", str(expected_sha256)):
            raise ArtifactServiceError(
                f"Invalid expected_sha256 format: '{expected_sha256}'",
                code="invalid_envelope",
            )

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

        canon_optin = canonicalize_metadata or bool(patch.get("canonicalize_metadata", False)) if isinstance(patch, dict) else False
        raw_req_bytes = self._request_bytes({
            "operation": "update",
            "kind": kind,
            "target": str(target_path),
            "expected_sha256": expected_sha256,
            "patch": patch,
            "body_replacement": body_replacement,
            "canonicalize_metadata": canon_optin,
        })
        raw_req_hash = hashlib.sha256(raw_req_bytes).hexdigest()

        if request_id:
            with self._mutation():
                receipt = self._replay(request_id, raw_req_hash, recorded_outcome=True)
                if receipt is not None:
                    return receipt

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

        self._require_valid(
            self.registry.validate_storage_schema(kind, updated_meta),
            f"Storage schema validation failed for update '{kind}'", "schema_validation_failed", target_path,
        )
        self._require_valid(
            self.registry.validate_references(
                kind,
                updated_meta,
                product_root=self.product_root,
                change_dir=self.change_dir,
                change_id=updated_meta.get("change") or getattr(self.auth_context, "change_id", None),
            ),
            f"Reference validation failed for update '{kind}'", "missing_reference", target_path,
        )

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

        schema_hashes = (self.registry.get_descriptor_hash(kind), self.registry.get_storage_schema_hash(kind))

        is_noop = check_noop_mutation(existing_bytes, candidate_bytes)
        req_id = request_id or f"req-{'noop-' if is_noop else ''}{candidate_sha256[:16]}"

        with self._mutation():
            receipt = self._replay(req_id, raw_req_hash, recorded_outcome=True)
            if receipt is not None:
                return receipt

            validate_expected_hash(target_path, expected_sha256)

            if is_noop:
                try:
                    verify_published_artifact(
                        target_path=target_path,
                        expected_sha256=expected_sha256,
                        kind=kind,
                        registry=self.registry,
                    )
                except ArtifactTransactionError:
                    raise
                except Exception as ex:
                    raise ArtifactTransactionError(
                        f"Readback verification failed for no-op target '{target_path}': {ex}",
                        code="readback_verification_failed",
                        path=str(target_path),
                    ) from ex

                tx = self._prepare(
                    req_id, raw_req_bytes, kind, target_path, "update",
                    expected_sha256, expected_sha256, candidate_sha256, schema_hashes,
                )
                return self.transaction_mgr.finalize_receipt(tx["transaction_id"], durable_outcome="unchanged", changed=False)

            tx = self._prepare(
                req_id, raw_req_bytes, kind, target_path, "update",
                expected_sha256, candidate_sha256, candidate_sha256, schema_hashes,
            )
            return self._publish(tx, kind, target_path, candidate_bytes, candidate_sha256, expected_sha256)
