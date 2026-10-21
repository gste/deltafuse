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

from deltafuse.core.assets import bundle_root, source_assets_root, verify_manifest
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

    def find_product_lock(self, product_root: Path | str | None = None) -> Path | None:
        root = Path(product_root).resolve() if product_root else self.product_root
        if root is None:
            return None
        curr = root
        for _ in range(6):
            cand = curr / ".deltafuse" / "lock.yaml"
            if cand.is_file():
                return cand
            if curr.parent == curr:
                break
            curr = curr.parent
        return root / ".deltafuse" / "lock.yaml"

    def verify_product_lock(self, product_root: Path | str | None = None) -> None:
        """Verify that product_root contains a valid .deltafuse/lock.yaml pin. Fail closed if absent/corrupt."""
        root = Path(product_root).resolve() if product_root else self.product_root
        if root is None:
            return
        lock_file = self.find_product_lock(root)
        if lock_file is None or not lock_file.is_file():
            raise ArtifactRegistryError(f"Missing required product lock file '.deltafuse/lock.yaml' in '{root}'")
        try:
            data = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
        except Exception as ex:
            raise ArtifactRegistryError(f"Malformed .deltafuse/lock.yaml: unparseable YAML ({ex})") from ex
        if not isinstance(data, dict):
            raise ArtifactRegistryError("Malformed .deltafuse/lock.yaml: top-level content must be a mapping")

        from deltafuse.core.lock import lock_schema_version_errors
        ver_errors = lock_schema_version_errors(data)
        if ver_errors:
            raise ArtifactRegistryError(f"Malformed .deltafuse/lock.yaml: {ver_errors[0]}")

        fw = data.get("framework")
        if not isinstance(fw, dict):
            raise ArtifactRegistryError("Malformed .deltafuse/lock.yaml: 'framework' must be a mapping")

        raw_version = fw.get("version")
        raw_source = fw.get("source")
        raw_hash = fw.get("content_hash")

        if raw_version is None or not isinstance(raw_version, str) or not raw_version.strip():
            raise ArtifactRegistryError("Malformed .deltafuse/lock.yaml: missing or invalid framework.version")

        if raw_source is None or not isinstance(raw_source, str) or not raw_source.strip():
            raise ArtifactRegistryError("Malformed .deltafuse/lock.yaml: missing or invalid framework.source")

        if raw_hash is None or not isinstance(raw_hash, str) or not raw_hash.strip():
            raise ArtifactRegistryError("Malformed .deltafuse/lock.yaml: missing or invalid framework.content_hash")

        lock_ver = raw_version.strip()
        lock_hash = raw_hash.strip()

        if not re.match(r"^sha256:[a-fA-F0-9]{64}$", lock_hash):
            raise ArtifactRegistryError(
                f"Malformed .deltafuse/lock.yaml: invalid framework.content_hash format '{lock_hash}'"
            )

        from deltafuse.core.assets import get_executing_framework_identity
        exec_version, valid_hashes = get_executing_framework_identity()

        if lock_ver != exec_version:
            raise ArtifactRegistryError(
                f"Product lock framework version '{lock_ver}' does not match running framework version '{exec_version}'"
            )

        if not valid_hashes:
            raise ArtifactRegistryError(
                "Executing framework asset identity is unavailable; cannot verify product lock content_hash"
            )

        if lock_hash.lower() not in valid_hashes:
            raise ArtifactRegistryError(
                f"Product lock framework content_hash '{lock_hash}' does not match running framework asset identity"
            )

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

        raise ArtifactRegistryError("Could not resolve process/artifact-operations directory from verified installed asset bundle or source checkout")

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

    def get_descriptor_bytes(self, kind: str) -> bytes:
        manifest = self.get_manifest()
        descriptors = manifest.get("descriptors", {})
        if kind not in descriptors:
            raise ArtifactRegistryError(f"Unsupported kind '{kind}'; no descriptor entry found in manifest")
        entry = descriptors[kind]
        ops_dir = self._resolve_operations_dir()
        desc_path = ops_dir / entry["file"]
        if not desc_path.is_file():
            raise ArtifactRegistryError(f"Descriptor file missing for kind '{kind}': {desc_path}")
        return desc_path.read_bytes()

    def get_descriptor_hash(self, kind: str) -> str:
        raw = self.get_descriptor_bytes(kind)
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def get_descriptor(self, kind: str) -> dict[str, Any]:
        if kind in self._descriptors_cache:
            return self._descriptors_cache[kind]

        raw = self.get_descriptor_bytes(kind)
        try:
            data = yaml.safe_load(raw.decode("utf-8"))
        except Exception as ex:
            raise ArtifactRegistryError(f"Failed to parse descriptor for kind '{kind}': {ex}") from ex

        if not isinstance(data, dict):
            raise ArtifactRegistryError(f"Descriptor for kind '{kind}' must be a dict")

        self._descriptors_cache[kind] = data
        return data

    def get_storage_schema_bytes(self, kind: str) -> bytes:
        try:
            from deltafuse.core.assets import resolve_assets
            schemas_dir = resolve_assets("schemas")
        except Exception:
            src_root = source_assets_root()
            if src_root:
                schemas_dir = src_root / "schemas"
            else:
                schemas_dir = Path("process/schemas").resolve()
        schema_file = schemas_dir / f"{kind}.schema.yaml"
        if not schema_file.is_file():
            raise ArtifactRegistryError(f"Storage schema file missing for kind '{kind}': {schema_file}")
        return schema_file.read_bytes()

    def get_storage_schema_hash(self, kind: str) -> str:
        raw = self.get_storage_schema_bytes(kind)
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def get_storage_schema(self, kind: str) -> dict[str, Any]:
        try:
            return self._schema_registry.get_schema(kind)
        except KeyError as ex:
            raise ArtifactRegistryError(f"Unsupported storage schema kind '{kind}'") from ex

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

        def _find_file(candidates: list[Path]) -> tuple[Path | None, dict[str, Any] | None, str | None]:
            for cand in candidates:
                if cand and cand.is_file():
                    if repo_root or root:
                        check_base = repo_root or root
                        try:
                            cand.resolve().relative_to(check_base)
                        except ValueError:
                            continue
                    try:
                        from deltafuse.core.artifact_reader import strict_read_artifact
                        has_fm = not cand.name.endswith((".yaml", ".yml"))
                        pres = strict_read_artifact(cand.read_bytes(), has_frontmatter_delimiters=has_fm)
                        return cand, pres.metadata, None
                    except Exception as ex:
                        return cand, None, str(ex)
            return None, None, None

        def _candidates(*parts: str | Path, change_scoped: bool = True, cdir_extra: str | None = None) -> list[Path]:
            # Search order decides which file wins: root, then (in a Change) the Change
            # directory under repo_root and under root, then change_dir, then repo_root.
            cands = [root.joinpath(*parts)]
            if change_scoped and cid:
                if repo_root:
                    cands.append(repo_root.joinpath("docs", "changes", cid, *parts))
                cands.append(root.joinpath("docs", "changes", cid, *parts))
            if cdir:
                cands.append(cdir.joinpath(*parts))
                if cdir_extra:
                    cands.append(cdir / cdir_extra)
            if repo_root:
                cands.append(repo_root.joinpath(*parts))
            return cands

        def _check_ref(pointer: str, ref_id: str, noun: str, missing: str, candidates: list[Path]) -> None:
            found, meta, err = _find_file(candidates)
            if not found:
                message = f"Referenced {missing} '{ref_id}' does not exist"
            elif err:
                message = f"Referenced {noun} '{found.name}' is malformed or invalid: {err}"
            elif not meta or not meta.get("id") or meta.get("id") != ref_id:
                actual_id = meta.get("id") if meta else None
                message = f"Referenced {noun} '{found.name}' has identity '{actual_id}', expected '{ref_id}'"
            elif cid and meta.get("change") and meta.get("change") != cid:
                message = f"Referenced {noun} '{found.name}' belongs to Change '{meta.get('change')}', expected '{cid}'"
            else:
                return
            diagnostics.append(
                ValidationDiagnostic(code="missing_reference", stage="reference", path=pointer, message=message)
            )

        if kind == "task" and root:
            slice_id = payload.get("slice")
            if slice_id:
                _check_ref(
                    "/slice", slice_id, "slice file", "slice file",
                    _candidates("slices", f"{slice_id}.md", cdir_extra=f"{slice_id}.md"),
                )

        if kind in ("task", "slice") and root:
            deps = payload.get("depends_on") or []
            if isinstance(deps, list):
                dep_dir = "tasks" if kind == "task" else "slices"
                for dep_id in deps:
                    if not isinstance(dep_id, str):
                        continue
                    _check_ref(
                        "/depends_on", dep_id, "dependency file", "dependency",
                        _candidates(dep_dir, f"{dep_id}.md"),
                    )

            spec_refs = payload.get("spec_refs") or []
            draft_specs: frozenset[str] | None = None
            if isinstance(spec_refs, list):
                for ref in spec_refs:
                    if not isinstance(ref, str):
                        continue
                    ref_path_str = ref.split("#")[0].strip()
                    if not ref_path_str:
                        continue
                    exists = any(c.is_file() for c in _candidates(Path(ref_path_str), change_scoped=False))

                    if not exists:
                        # Check if it's a declared future spec change in spec-delta.md
                        sd_path, sd_meta, _ = _find_file(_candidates("spec-delta.md"))

                        is_declared = False
                        if sd_path and sd_meta:
                            added = sd_meta.get("added") or []
                            modified = sd_meta.get("modified") or []
                            declared_paths = set(added + modified)
                            if ref_path_str in declared_paths or ref_path_str == "spec-delta.md" or ref_path_str.endswith("spec-delta.md"):
                                is_declared = True

                        if not is_declared:
                            # A capability proposed in Analyze (`deltafuse capability
                            # propose`, q8) promises a spec file that Specify writes
                            # later. The gate side already allows the reference
                            # (check_gate passes drafts=draft_spec_files); without it
                            # here the Writer refused the slice the propose flow exists
                            # for and named spec-delta.md as the way out - a Specify
                            # artifact that does not exist in Analyze and is outside its
                            # write scope, so `analyzed` could never close.
                            if draft_specs is None:
                                from deltafuse.core.integrity import draft_spec_files

                                draft_specs = (
                                    draft_spec_files(repo_root) if repo_root else frozenset()
                                )
                            is_declared = ref_path_str in draft_specs

                        if not is_declared:
                            diagnostics.append(
                                ValidationDiagnostic(
                                    code="missing_reference",
                                    stage="reference",
                                    path="/spec_refs",
                                    message=(
                                        f"Referenced spec path '{ref_path_str}' does not exist, is not "
                                        "declared in spec-delta, and is not a spec file a draft "
                                        "capability promises"
                                    ),
                                )
                            )

            design_ref = payload.get("design_ref")
            if design_ref and isinstance(design_ref, str):
                d_path_str = design_ref.split("#")[0].strip()
                if d_path_str:
                    if not any(c.is_file() for c in _candidates(Path(d_path_str), change_scoped=False)):
                        message = f"Referenced design file '{d_path_str}' does not exist"
                        if d_path_str.lower() in {"null", "none", "~", "n/a"}:
                            # Gemma 31B shakedown cls-g31p3-m02 (2026-10-04): the string
                            # "null" four decompose steps running, each step new enough
                            # to have lost the previous one's guess at the cause.
                            message += (
                                "; a task without a design has design_ref null (the JSON "
                                "value, not the string \"null\") or no design_ref at all"
                            )
                        diagnostics.append(
                            ValidationDiagnostic(
                                code="missing_reference",
                                stage="reference",
                                path="/design_ref",
                                message=message,
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
