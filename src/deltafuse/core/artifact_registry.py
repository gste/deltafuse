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

    def get_envelope_schema(self) -> dict[str, Any]:
        cand1 = Path("docs/contracts/artifact-writer.schema.yaml")
        if cand1.is_file():
            return yaml.safe_load(cand1.read_text(encoding="utf-8"))
        src_root = source_assets_root()
        if src_root:
            cand2 = src_root / "contracts" / "artifact-writer.schema.yaml"
            if cand2.is_file():
                return yaml.safe_load(cand2.read_text(encoding="utf-8"))
        b_root = bundle_root()
        if b_root:
            cand3 = b_root / "contracts" / "artifact-writer.schema.yaml"
            if cand3.is_file():
                return yaml.safe_load(cand3.read_text(encoding="utf-8"))
        raise ArtifactRegistryError("Could not locate artifact-writer.schema.yaml contract")

    def validate_operation_envelope(self, envelope: dict[str, Any]) -> ValidationResult:
        schema = self.get_envelope_schema()
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(envelope), key=lambda e: (list(e.path), e.message))
        if not errors:
            return ValidationResult(valid=True, scopes=[{"scope": "envelope", "status": "valid"}])
        diags: list[ValidationDiagnostic] = []
        for err in errors:
            code = _map_validator_code(err.validator)
            ptr = _json_pointer(err.path)
            diags.append(ValidationDiagnostic(code=code, stage="input", path=ptr, message=err.message))
        return ValidationResult(valid=False, diagnostics=diags, scopes=[{"scope": "envelope", "status": "invalid"}])


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
        product_root: Path | str | None = None,
        change_dir: Path | str | None = None,
        change_id: str | None = None,
    ) -> ValidationResult:
        diagnostics: list[ValidationDiagnostic] = []
        root = Path(product_root).resolve() if product_root else (Path(change_dir).resolve() if change_dir else None)
        cdir = Path(change_dir).resolve() if change_dir else None
        cid = change_id or (payload.get("change") if isinstance(payload, dict) else None)

        repo_root = root
        if repo_root:
            curr = repo_root
            for _ in range(6):
                if (curr / "docs" / "spec").is_dir() or (curr / ".deltafuse").is_dir():
                    repo_root = curr
                    break
                if curr.parent == curr:
                    break
                curr = curr.parent

        def _find_file(candidates: list[Path]) -> tuple[Path | None, dict[str, Any] | None]:
            for cand in candidates:
                if cand and cand.is_file():
                    try:
                        from deltafuse.core.artifact_reader import strict_read_artifact
                        has_fm = not cand.name.endswith((".yaml", ".yml"))
                        pres = strict_read_artifact(cand.read_bytes(), has_frontmatter_delimiters=has_fm)
                        return cand, pres.metadata
                    except Exception:
                        return cand, None
            return None, None

        if kind == "task" and root:
            slice_id = payload.get("slice")
            if slice_id:
                slice_candidates = [
                    root / "slices" / f"{slice_id}.md",
                    cdir / "slices" / f"{slice_id}.md" if cdir else None,
                    cdir / f"{slice_id}.md" if cdir else None,
                ]
                if repo_root:
                    slice_candidates.append(repo_root / "slices" / f"{slice_id}.md")
                if cid:
                    slice_candidates.insert(1, root / "docs" / "changes" / cid / "slices" / f"{slice_id}.md")
                    if repo_root:
                        slice_candidates.insert(1, repo_root / "docs" / "changes" / cid / "slices" / f"{slice_id}.md")
                valid_candidates = [c for c in slice_candidates if c is not None]

                found_path, slice_meta = _find_file(valid_candidates)
                if not found_path:
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="missing_reference",
                            stage="reference",
                            path="/slice",
                            message=f"Referenced slice file '{slice_id}' does not exist",
                        )
                    )
                elif slice_meta and slice_meta.get("id") and slice_meta.get("id") != slice_id:
                    diagnostics.append(
                        ValidationDiagnostic(
                            code="missing_reference",
                            stage="reference",
                            path="/slice",
                            message=f"Referenced slice file '{found_path.name}' has identity '{slice_meta.get('id')}', expected '{slice_id}'",
                        )
                    )

        if kind in ("task", "slice") and root:
            deps = payload.get("depends_on") or []
            if isinstance(deps, list):
                for dep_id in deps:
                    if not isinstance(dep_id, str):
                        continue
                    if kind == "task":
                        dep_candidates = [
                            root / "tasks" / f"{dep_id}.md",
                            cdir / "tasks" / f"{dep_id}.md" if cdir else None,
                        ]
                        if repo_root:
                            dep_candidates.append(repo_root / "tasks" / f"{dep_id}.md")
                        if cid:
                            dep_candidates.insert(1, root / "docs" / "changes" / cid / "tasks" / f"{dep_id}.md")
                            if repo_root:
                                dep_candidates.insert(1, repo_root / "docs" / "changes" / cid / "tasks" / f"{dep_id}.md")
                    else:
                        dep_candidates = [
                            root / "slices" / f"{dep_id}.md",
                            cdir / "slices" / f"{dep_id}.md" if cdir else None,
                        ]
                        if repo_root:
                            dep_candidates.append(repo_root / "slices" / f"{dep_id}.md")
                        if cid:
                            dep_candidates.insert(1, root / "docs" / "changes" / cid / "slices" / f"{dep_id}.md")
                            if repo_root:
                                dep_candidates.insert(1, repo_root / "docs" / "changes" / cid / "slices" / f"{dep_id}.md")

                    valid_dep_cands = [c for c in dep_candidates if c is not None]
                    found_dep_path, dep_meta = _find_file(valid_dep_cands)
                    if not found_dep_path:
                        diagnostics.append(
                            ValidationDiagnostic(
                                code="missing_reference",
                                stage="reference",
                                path="/depends_on",
                                message=f"Referenced dependency '{dep_id}' does not exist",
                            )
                        )
                    elif dep_meta and dep_meta.get("id") and dep_meta.get("id") != dep_id:
                        diagnostics.append(
                            ValidationDiagnostic(
                                code="missing_reference",
                                stage="reference",
                                path="/depends_on",
                                message=f"Referenced dependency file '{found_dep_path.name}' has identity '{dep_meta.get('id')}', expected '{dep_id}'",
                            )
                        )

            spec_refs = payload.get("spec_refs") or []
            if isinstance(spec_refs, list):
                for ref in spec_refs:
                    if not isinstance(ref, str):
                        continue
                    ref_path_str = ref.split("#")[0].strip()
                    if not ref_path_str:
                        continue
                    ref_path = Path(ref_path_str)

                    ref_candidates = [
                        root / ref_path,
                        cdir / ref_path if cdir else None,
                    ]
                    if repo_root:
                        ref_candidates.append(repo_root / ref_path)
                    valid_ref_cands = [c for c in ref_candidates if c is not None]
                    exists = any(c.is_file() for c in valid_ref_cands)

                    if not exists:
                        # Check if it's a declared future spec change in spec-delta.md
                        spec_delta_candidates = [
                            root / "spec-delta.md",
                            cdir / "spec-delta.md" if cdir else None,
                        ]
                        if repo_root:
                            spec_delta_candidates.append(repo_root / "spec-delta.md")
                        if cid:
                            spec_delta_candidates.insert(1, root / "docs" / "changes" / cid / "spec-delta.md")
                            if repo_root:
                                spec_delta_candidates.insert(1, repo_root / "docs" / "changes" / cid / "spec-delta.md")
                        valid_sd_cands = [c for c in spec_delta_candidates if c is not None]
                        sd_path, sd_meta = _find_file(valid_sd_cands)

                        is_declared = False
                        if sd_path and sd_meta:
                            added = sd_meta.get("added") or []
                            modified = sd_meta.get("modified") or []
                            declared_paths = set(added + modified)
                            if ref_path_str in declared_paths or ref_path_str == "spec-delta.md" or ref_path_str.endswith("spec-delta.md"):
                                is_declared = True

                        if not is_declared:
                            diagnostics.append(
                                ValidationDiagnostic(
                                    code="missing_reference",
                                    stage="reference",
                                    path="/spec_refs",
                                    message=f"Referenced spec path '{ref_path_str}' does not exist and is not declared in spec-delta",
                                )
                            )

            design_ref = payload.get("design_ref")
            if design_ref and isinstance(design_ref, str):
                d_path_str = design_ref.split("#")[0].strip()
                if d_path_str:
                    d_path = Path(d_path_str)
                    d_cands = [root / d_path, cdir / d_path if cdir else None]
                    if repo_root:
                        d_cands.append(repo_root / d_path)
                    if not any(c.is_file() for c in d_cands if c is not None):
                        diagnostics.append(
                            ValidationDiagnostic(
                                code="missing_reference",
                                stage="reference",
                                path="/design_ref",
                                message=f"Referenced design file '{d_path_str}' does not exist",
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

