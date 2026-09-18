"""ArtifactRegistry: schema resolution, asset lock pinning, and structured validation (AW-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import yaml
import jsonschema

from deltafuse.core.assets import AssetError, bundle_root, source_assets_root, verify_manifest
from deltafuse.core.schemas import SchemaRegistry


class ArtifactRegistryError(Exception):
    """Raised when descriptor or schema resolution fails."""


@dataclass(frozen=True)
class ValidationDiagnostic:
    """Structured diagnostic representation of a validation failure."""

    code: str
    stage: str  # "input", "schema", "policy", "reference", "concurrency"
    path: str  # JSON Pointer path, e.g. "/source/request"
    message: str
    hint: str | None = None


@dataclass
class ValidationResult:
    """Overall result of structured artifact validation."""

    valid: bool
    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)
    scopes: list[dict[str, Any]] = field(default_factory=list)


def _json_pointer(path: tuple[Any, ...]) -> str:
    if not path:
        return "/"
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in path)


def _map_validator_code(validator_name: str) -> str:
    mapping = {
        "additionalProperties": "unexpected_property",
        "required": "required_property_missing",
        "pattern": "invalid_pattern",
        "type": "type_mismatch",
        "enum": "enum_mismatch",
        "minItems": "insufficient_items",
        "const": "constant_mismatch",
    }
    return mapping.get(validator_name, f"schema_{validator_name}")


class ArtifactRegistry:
    """Authoritative registry resolving pinned schemas and performing structured validation."""

    def __init__(self, product_root: Path | str | None = None):
        self.product_root = Path(product_root).resolve() if product_root else None
        self._schema_registry = SchemaRegistry()
        self._descriptors_cache: dict[str, dict[str, Any]] = {}
        self._manifest: dict[str, Any] | None = None
        self._operations_dir: Path | None = None

    def _resolve_operations_dir(self) -> Path:
        if self._operations_dir is not None:
            return self._operations_dir

        # Try source checkout root first
        src_root = source_assets_root()
        if src_root:
            candidate = src_root / "artifact-operations"
            if candidate.is_dir():
                self._operations_dir = candidate
                return candidate

        # Try packaged bundle root
        b_root = bundle_root()
        if b_root:
            problems = verify_manifest(b_root)
            if problems:
                raise ArtifactRegistryError(f"Corrupt asset bundle: {'; '.join(problems)}")
            candidate = b_root / "artifact-operations"
            if candidate.is_dir():
                self._operations_dir = candidate
                return candidate

        # Fallback to local process/artifact-operations relative to working dir if exists
        local_cand = Path("process/artifact-operations")
        if local_cand.is_dir():
            self._operations_dir = local_cand
            return local_cand

        raise ArtifactRegistryError("Could not resolve process/artifact-operations directory from bundle or source")

    def get_manifest(self) -> dict[str, Any]:
        if self._manifest is not None:
            return self._manifest
        ops_dir = self._resolve_operations_dir()
        manifest_file = ops_dir / "manifest.json"
        if not manifest_file.is_file():
            raise ArtifactRegistryError(f"Missing manifest.json in {ops_dir}")
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as ex:
            raise ArtifactRegistryError(f"Failed to read manifest.json: {ex}") from ex
        self._manifest = data
        return data

    def get_descriptor(self, kind: str) -> dict[str, Any]:
        if kind in self._descriptors_cache:
            return self._descriptors_cache[kind]

        manifest = self.get_manifest()
        descriptors = manifest.get("descriptors", {})
        if kind not in descriptors:
            raise ArtifactRegistryError(f"Unsupported kind '{kind}'; no descriptor entry found in manifest")

        entry = descriptors[kind]
        ops_dir = self._resolve_operations_dir()
        desc_path = ops_dir / entry["file"]
        if not desc_path.is_file():
            raise ArtifactRegistryError(f"Descriptor file missing for kind '{kind}': {desc_path}")

        try:
            data = yaml.safe_load(desc_path.read_text(encoding="utf-8"))
        except Exception as ex:
            raise ArtifactRegistryError(f"Failed to parse descriptor for kind '{kind}': {ex}") from ex

        if not isinstance(data, dict):
            raise ArtifactRegistryError(f"Descriptor for kind '{kind}' must be a dict")

        self._descriptors_cache[kind] = data
        return data

    def get_storage_schema(self, kind: str, expected_hash: str | None = None) -> dict[str, Any]:
        try:
            schema = self._schema_registry.get_schema(kind)
        except KeyError as ex:
            raise ArtifactRegistryError(f"Unsupported storage schema kind '{kind}'") from ex

        if expected_hash:
            # Check schema bytes hash matches expected_hash
            raw = json.dumps(schema, sort_keys=True).encode("utf-8")
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            if expected_hash != digest and not expected_hash.endswith(hashlib.sha256(raw).hexdigest()):
                raise ArtifactRegistryError(
                    f"Schema byte hash mismatch for kind '{kind}'; expected {expected_hash}, got {digest}"
                )

        return schema

    def validate_storage_schema(self, kind: str, payload: dict[str, Any]) -> ValidationResult:
        try:
            schema = self.get_storage_schema(kind)
        except ArtifactRegistryError as ex:
            return ValidationResult(
                valid=False,
                diagnostics=[
                    ValidationDiagnostic(
                        code="unsupported_kind",
                        stage="schema",
                        path="/",
                        message=str(ex),
                    )
                ],
                scopes=[{"scope": "schema", "status": "invalid", "details": [str(ex)]}],
            )

        validator_cls = jsonschema.validators.validator_for(schema)
        validator = validator_cls(schema)
        raw_errors = list(validator.iter_errors(payload))

        if not raw_errors:
            return ValidationResult(
                valid=True,
                diagnostics=[],
                scopes=[{"scope": "schema", "status": "valid", "details": []}],
            )

        diagnostics: list[ValidationDiagnostic] = []
        for err in raw_errors:
            pointer = _json_pointer(err.path)
            code = _map_validator_code(err.validator or "validation")
            msg = err.message
            diagnostics.append(
                ValidationDiagnostic(
                    code=code,
                    stage="schema",
                    path=pointer,
                    message=msg,
                )
            )

        return ValidationResult(
            valid=False,
            diagnostics=diagnostics,
            scopes=[{"scope": "schema", "status": "invalid", "details": [d.message for d in diagnostics]}],
        )

    def validate_operation_input(
        self,
        kind: str,
        operation: str,
        *,
        semantic_payload: dict[str, Any] | None = None,
        patch: dict[str, Any] | None = None,
    ) -> ValidationResult:
        try:
            desc = self.get_descriptor(kind)
        except ArtifactRegistryError as ex:
            return ValidationResult(
                valid=False,
                diagnostics=[ValidationDiagnostic(code="unsupported_kind", stage="input", path="/", message=str(ex))],
            )

        allowed_ops = desc.get("allowed_operations", [])
        if operation not in allowed_ops:
            return ValidationResult(
                valid=False,
                diagnostics=[
                    ValidationDiagnostic(
                        code="operation_not_allowed",
                        stage="input",
                        path="/operation",
                        message=f"Operation '{operation}' is not allowed for kind '{kind}'; allowed: {allowed_ops}",
                    )
                ],
            )

        diagnostics: list[ValidationDiagnostic] = []
        core_owned = set(desc.get("core_owned_fields", []))

        if operation == "create" and semantic_payload is not None:
            for key in semantic_payload:
                if key in core_owned:
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="core_owned_field",
                            stage="input",
                            path=f"/{key}",
                            message=f"Field '{key}' is Core-owned and cannot be written via public Worker create",
                            hint="Use Core command (e.g. deltafuse advance or deltafuse state)",
                        )
                    )

        if operation == "update" and patch is not None:
            set_ops = patch.get("set") or []
            for item in set_ops:
                p = item.get("path") or ""
                root_field = p.lstrip("/").split("/")[0]
                if root_field in core_owned:
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="core_owned_field",
                            stage="input",
                            path=p,
                            message=f"Field '{root_field}' is Core-owned and cannot be modified via patch",
                            hint="Use Core command to mutate lifecycle state",
                        )
                    )

            remove_ops = patch.get("remove") or []
            for p in remove_ops:
                root_field = p.lstrip("/").split("/")[0]
                if root_field in core_owned:
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="core_owned_field",
                            stage="input",
                            path=p,
                            message=f"Field '{root_field}' is Core-owned and cannot be removed via patch",
                        )
                    )

        valid = len(diagnostics) == 0
        return ValidationResult(
            valid=valid,
            diagnostics=diagnostics,
            scopes=[{"scope": "input", "status": "valid" if valid else "invalid", "details": [d.message for d in diagnostics]}],
        )

    def validate_references(
        self,
        kind: str,
        payload: dict[str, Any],
        change_dir: Path | str | None = None,
    ) -> ValidationResult:
        diagnostics: list[ValidationDiagnostic] = []
        cdir = Path(change_dir).resolve() if change_dir else None

        if kind == "task" and cdir:
            slice_id = payload.get("slice")
            if slice_id:
                slice_file = cdir / "slices" / f"{slice_id}.md"
                if not slice_file.is_file():
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="missing_reference",
                            stage="reference",
                            path="/slice",
                            message=f"Referenced slice file '{slice_file.name}' does not exist in {cdir / 'slices'}",
                        )
                    )

        valid = len(diagnostics) == 0
        scopes = [
            {
                "scope": "reference",
                "status": "valid" if valid else "invalid",
                "details": [d.message for d in diagnostics],
            },
            {
                "scope": "whole_gate",
                "status": "not_evaluated",
                "details": ["Whole-Change convergence is evaluated by Core gates, not single-file write"],
            },
        ]

        return ValidationResult(valid=valid, diagnostics=diagnostics, scopes=scopes)
