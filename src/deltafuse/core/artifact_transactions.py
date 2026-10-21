"""Durable receipts, idempotency and crash recovery (AW-09).

Provides transaction journal logging, receipt generation and validation against receipt.schema.yaml,
idempotent request handling, and recovery for crashed transaction boundaries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any
import uuid


class ArtifactTransactionError(Exception):
    """Raised when transaction recording, recovery, or receipt finalization fails."""

    def __init__(self, message: str, *, code: str, path: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.message = message
        self.code = code
        self.path = path


def compute_receipt_digest(receipt_dict: dict[str, Any]) -> str:
    """Compute SHA256 digest of receipt contents, excluding receipt_sha256 and digest properties."""
    clean_dict = {k: v for k, v in receipt_dict.items() if k not in ("digest", "receipt_sha256")}
    canonical_json = json.dumps(clean_dict, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


_ZERO_HASH = "sha256:" + ("0" * 64)


def _default_validation_scopes() -> list[dict[str, Any]]:
    return [
        {"scope": "envelope", "status": "valid", "details": []},
        {"scope": "input", "status": "valid", "details": []},
        {"scope": "schema", "status": "valid", "details": []},
        {"scope": "policy", "status": "valid", "details": []},
        {"scope": "reference", "status": "valid", "details": []},
        {"scope": "whole_gate", "status": "not_evaluated", "details": ["Whole-Change convergence is evaluated by Core gates, not single-file write"]},
    ]


def _utc_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _load_record(
    path: Path,
    required: tuple[str, ...] = (),
    missing: str = "missing required fields",
) -> dict[str, Any]:
    """Read one journal record; a record that is unreadable or lacks `required` keys is corrupt."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as ex:
        raise ArtifactTransactionError(
            f"Corrupt transaction record '{path.name}': {ex}",
            code="corrupt_journal",
            path=str(path),
        ) from ex
    if required and (not isinstance(rec, dict) or any(key not in rec for key in required)):
        raise ArtifactTransactionError(
            f"Corrupt transaction record '{path.name}': {missing}",
            code="corrupt_journal",
            path=str(path),
        )
    return rec


def _write_atomic_json(target_path: Path, content_dict: dict[str, Any]) -> None:
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace
    content_bytes = json.dumps(content_dict, indent=2, ensure_ascii=False).encode("utf-8")
    if target_path.is_file():
        atomic_replace(target_path, content_bytes)
    else:
        atomic_create(target_path, content_bytes)


class TransactionManager:
    """Core transaction manager for artifact updates, receipts, and crash recovery."""

    def __init__(self, product_root: Path, change_dir: Path | None = None):
        self.product_root = Path(product_root)
        self.change_dir = Path(change_dir) if change_dir else self.product_root
        self.journal_dir = self.product_root / ".deltafuse" / "journal"
        self.receipts_dir = self.product_root / ".deltafuse" / "receipts"

    def _ensure_dirs(self) -> None:
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def get_receipt(self, transaction_id: str) -> dict[str, Any] | None:
        receipt_file = self.receipts_dir / f"{transaction_id}.json"
        if receipt_file.is_file():
            try:
                return json.loads(receipt_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _find_record(self, request_id: str) -> tuple[Path, dict[str, Any]] | None:
        if not self.journal_dir.is_dir():
            return None
        for record_path in sorted(self.journal_dir.glob("*.json")):
            rec = _load_record(record_path, ("request_id",), "missing request_id")
            if rec.get("request_id") == request_id:
                return record_path, rec
        return None

    def find_transaction_by_request_id(self, request_id: str) -> dict[str, Any] | None:
        found = self._find_record(request_id)
        return found[1] if found else None

    def _journal_record(self, transaction_id: str) -> tuple[Path, dict[str, Any]]:
        record_file = self.journal_dir / f"{transaction_id}.json"
        if not record_file.is_file():
            raise ArtifactTransactionError(
                f"Transaction journal record '{transaction_id}' not found",
                code="transaction_not_found",
            )
        return record_file, _load_record(record_file)

    def prepare_transaction(
        self,
        request_id: str,
        raw_request_bytes: bytes,
        kind: str,
        target_path: Path,
        previous_sha256: str | None,
        expected_result_sha256: str,
        auth_context: Any,
        operation: str = "update",
        operation_schema_hash: str | None = None,
        storage_schema_hash: str | None = None,
        normalized_payload_hash: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_dirs()
        raw_request_hash = hashlib.sha256(raw_request_bytes).hexdigest()
        norm_hash = normalized_payload_hash or raw_request_hash

        found = self._find_record(request_id)
        if found is not None:
            record_path, rec = found
            if rec.get("raw_request_hash") == raw_request_hash:
                return rec
            raise ArtifactTransactionError(
                f"Request ID '{request_id}' re-used with different payload",
                code="idempotency_conflict",
                path=str(record_path),
            )

        transaction_id = f"tx-{uuid.uuid4().hex}"
        try:
            relative_target = (
                str(target_path.relative_to(self.product_root)).replace("\\", "/")
                if target_path.is_relative_to(self.product_root)
                else str(target_path).replace("\\", "/")
            )
        except ValueError:
            relative_target = str(target_path).replace("\\", "/")

        record = {
            "transaction_id": transaction_id,
            "request_id": request_id,
            "kind": kind,
            "target": relative_target,
            "target_abs_path": str(target_path),
            "operation": operation,
            "operation_schema_version": "1",
            "operation_schema_hash": operation_schema_hash or _ZERO_HASH,
            "storage_schema_identity": f"https://deltafuse.dev/schemas/v3/{kind}.schema.yaml",
            "storage_schema_hash": storage_schema_hash or _ZERO_HASH,
            "serializer_revision": "1",
            "raw_request_hash": raw_request_hash,
            "normalized_payload_hash": norm_hash,
            "previous_sha256": previous_sha256,
            "expected_result_sha256": expected_result_sha256,
            "staged_path": None,
            "state": "prepared",
            "created_at": time.time(),
            "timestamp": _utc_now(),
            "authorization_context": {
                "actor": getattr(auth_context, "actor", "worker"),
                "work_item": getattr(auth_context, "work_item", "unknown"),
                "stage": getattr(auth_context, "stage", "unknown"),
                "fingerprint": getattr(auth_context, "fingerprint", "unknown"),
            },
            "validation_scopes": _default_validation_scopes(),
        }

        record_file = self.journal_dir / f"{transaction_id}.json"
        _write_atomic_json(record_file, record)
        return record

    def mark_published(self, transaction_id: str) -> None:
        record_file, rec = self._journal_record(transaction_id)
        rec["state"] = "published"
        _write_atomic_json(record_file, rec)

    def mark_readback_failed(self, transaction_id: str, reason: str = "") -> None:
        record_file = self.journal_dir / f"{transaction_id}.json"
        if not record_file.is_file():
            return
        try:
            rec = json.loads(record_file.read_text(encoding="utf-8"))
            rec["state"] = "readback_failed"
            rec["readback_error"] = str(reason)
            _write_atomic_json(record_file, rec)
        except Exception:
            pass

    def _validate_receipt_against_schema(self, receipt_dict: dict[str, Any]) -> None:
        try:
            import yaml
            import jsonschema
            from deltafuse.core.artifact_registry import ArtifactRegistry
            reg = ArtifactRegistry(self.product_root)
            ops_dir = reg._resolve_operations_dir()
            receipt_schema_file = ops_dir / "receipt.schema.yaml"
            if receipt_schema_file.is_file():
                schema = yaml.safe_load(receipt_schema_file.read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(schema).validate(receipt_dict)
        except Exception as ex:
            raise ArtifactTransactionError(f"Generated receipt failed schema validation: {ex}", code="invalid_receipt") from ex

    def finalize_receipt(
        self,
        transaction_id: str,
        durable_outcome: str = "committed",
        changed: bool = True,
    ) -> dict[str, Any]:
        record_file, rec = self._journal_record(transaction_id)
        raw_prev = rec.get("previous_sha256")
        receipt_dict = {
            "request_id": rec["request_id"],
            "transaction_id": rec["transaction_id"],
            "operation": rec["operation"],
            "kind": rec["kind"],
            "target": rec["target"],
            "operation_schema": {
                "version": str(rec.get("operation_schema_version", "1")),
                "content_hash": rec.get("operation_schema_hash") or _ZERO_HASH,
            },
            "storage_schema": {
                "kind": rec["kind"],
                "version": 3,
                "id": rec.get("storage_schema_identity") or f"https://deltafuse.dev/schemas/v3/{rec['kind']}.schema.yaml",
                "content_hash": rec.get("storage_schema_hash") or _ZERO_HASH,
            },
            "serializer_revision": 1,
            "request_sha256": _sha(rec["raw_request_hash"]),
            "payload_sha256": _sha(rec["normalized_payload_hash"]),
            "previous_sha256": None if raw_prev is None else _sha(raw_prev),
            "result_sha256": _sha(rec["expected_result_sha256"]),
            "changed": changed,
            "outcome": durable_outcome,
            "timestamp": rec.get("timestamp") or _utc_now(),
            "authority": {
                "actor": rec["authorization_context"]["actor"],
                "work_item": rec["authorization_context"]["work_item"],
                "product_root": str(self.product_root).replace("\\", "/"),
            },
            "validation_scopes": rec.get("validation_scopes") or _default_validation_scopes(),
        }

        digest = compute_receipt_digest(receipt_dict)
        receipt_dict["receipt_sha256"] = digest
        receipt_dict["digest"] = digest

        self._validate_receipt_against_schema(receipt_dict)

        receipt_file = self.receipts_dir / f"{transaction_id}.json"
        _write_atomic_json(receipt_file, receipt_dict)

        rec["state"] = "committed"
        rec["receipt_file"] = str(receipt_file)
        _write_atomic_json(record_file, rec)

        return receipt_dict


def recover_pending_transactions(product_root: Path) -> list[dict[str, Any]]:
    """Scan journal for pending/uncommitted transactions and recover based on exact disk state."""
    tm = TransactionManager(product_root)
    outcomes: list[dict[str, Any]] = []

    if not tm.journal_dir.is_dir():
        return outcomes

    for record_file in sorted(tm.journal_dir.glob("*.json")):
        rec = _load_record(record_file, ("state", "transaction_id"))
        state = rec.get("state")
        if state in ("committed", "cancelled", "ambiguous_stopped"):
            continue

        tx_id = rec["transaction_id"]
        target_path = Path(rec.get("target_abs_path") or (product_root / rec["target"]))
        prev_hash = rec.get("previous_sha256")
        expected_hash = rec.get("expected_result_sha256")

        current_bytes = target_path.read_bytes() if target_path.is_file() else None
        current_hash = hashlib.sha256(current_bytes).hexdigest() if current_bytes is not None else None

        if current_hash == expected_hash:
            receipt = tm.finalize_receipt(tx_id, durable_outcome="committed", changed=True)
            outcomes.append({
                "transaction_id": tx_id,
                "outcome": "recovered_published",
                "receipt": receipt,
            })
        elif current_hash == prev_hash:
            rec["state"] = "cancelled"
            _write_atomic_json(record_file, rec)
            outcomes.append({
                "transaction_id": tx_id,
                "outcome": "restored_previous",
                "previous_sha256": prev_hash,
            })
        else:
            rec["state"] = "ambiguous_stopped"
            _write_atomic_json(record_file, rec)
            outcomes.append({
                "transaction_id": tx_id,
                "outcome": "ambiguous_stopped",
                "current_hash": current_hash,
                "previous_hash": prev_hash,
                "expected_hash": expected_hash,
            })

    return outcomes

