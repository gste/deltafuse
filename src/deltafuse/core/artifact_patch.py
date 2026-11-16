"""Typed JSON Pointer patch application and immutable-field protection for DeltaFuse artifacts (AW-05).

Applies set/remove pointer operations, enforces Core-owned immutable field boundaries,
rejects array index edits and overlapping pointers, preserves unpatched metadata/body,
and verifies complete post-patch storage schema candidates.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from deltafuse.core.artifact_registry import ArtifactRegistry, ArtifactRegistryError


class ArtifactPatchError(Exception):
    """Raised when patch parsing, pointer validation, core-field protection, or post-patch verification fails."""

    def __init__(self, message: str, *, code: str = "patch_error", path: str | None = None):
        full_msg = f"[{code}] {message}"
        super().__init__(full_msg)
        self.message = message
        self.code = code
        self.path = path


@dataclass(frozen=True)
class PatchOutcome:
    """Outcome of applying a typed patch to an artifact."""

    updated_metadata: dict[str, Any]
    updated_body: str
    changed: bool
    applied_ops_count: int


_ABSENT = object()


def _value_at(data: Any, tokens: list[str]) -> Any:
    """The value at a token path, or _ABSENT."""
    for token in tokens:
        if not isinstance(data, dict) or token not in data:
            return _ABSENT
        data = data[token]
    return data


def _parse_pointer(ptr: str) -> list[str]:
    if not isinstance(ptr, str) or not ptr.startswith("/"):
        raise ArtifactPatchError(f"Invalid JSON Pointer '{ptr}'; must start with '/'", code="invalid_pointer")

    raw_tokens = ptr.lstrip("/").split("/")
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in raw_tokens]

    for t in tokens:
        if t.isdigit() or t == "-":
            raise ArtifactPatchError(
                f"Numeric array index edits ('{ptr}') are unsupported in v1; replace whole collection",
                code="array_index_unsupported",
                path=ptr,
            )

    return tokens


def _check_pointer_overlaps(pointers: list[str]) -> None:
    norm_pointers = [p.rstrip("/") for p in pointers if p]
    for i, p1 in enumerate(norm_pointers):
        for j, p2 in enumerate(norm_pointers):
            if i != j:
                if p1 == p2:
                    raise ArtifactPatchError(f"Duplicate patch pointer '{p1}'", code="overlapping_patch_pointers", path=p1)
                if p2.startswith(p1 + "/"):
                    raise ArtifactPatchError(
                        f"Contains overlapping ancestor/descendant patch pointers: '{p1}' and '{p2}'",
                        code="overlapping_patch_pointers",
                        path=p2,
                    )


def apply_artifact_patch(
    metadata: dict[str, Any],
    patch: dict[str, Any],
    *,
    kind: str = "task",
    body: str = "",
    body_replacement: str | None = None,
    registry: ArtifactRegistry | None = None,
) -> PatchOutcome:
    """Apply a typed set/remove patch to artifact metadata and return the resulting PatchOutcome."""
    if registry is None:
        registry = ArtifactRegistry()

    try:
        desc = registry.get_descriptor(kind)
    except ArtifactRegistryError as ex:
        raise ArtifactPatchError(f"Unsupported artifact kind '{kind}': {ex}", code="unsupported_kind") from ex

    core_owned = set(desc.get("core_owned_fields", []))

    set_ops = patch.get("set") or []
    remove_ops = patch.get("remove") or []

    all_pointers: list[str] = []
    for item in set_ops:
        if isinstance(item, dict) and "path" in item:
            all_pointers.append(item["path"])
    for p in remove_ops:
        if isinstance(p, str):
            all_pointers.append(p)

    _check_pointer_overlaps(all_pointers)

    # Core-owned field protection check. A Core-owned name may be a path (`analysis/routing`):
    # a pointer at it or inside it is refused outright; a pointer at one of its ancestors
    # (`/analysis`) is refused below when it changes the Core-owned value (audit 2026-11-16,
    # df-leash #17: only the first token was compared, so setting /analysis rewrote it).
    owned_paths = [[tok for tok in str(field).split("/") if tok] for field in core_owned]
    guarded_ancestors: list[list[str]] = []
    for ptr in all_pointers:
        tokens = _parse_pointer(ptr)
        for owned in owned_paths:
            if owned and tokens[: len(owned)] == owned:
                raise ArtifactPatchError(
                    f"Field '{'/'.join(owned)}' target by pointer '{ptr}' is Core-owned and immutable",
                    code="core_owned_field",
                    path=ptr,
                )
            if owned and owned[: len(tokens)] == tokens:
                guarded_ancestors.append(owned)

    updated_meta = copy.deepcopy(metadata)
    applied_count = 0

    # Apply set operations
    for item in set_ops:
        if not isinstance(item, dict) or "path" not in item or "value" not in item:
            raise ArtifactPatchError("Set patch operation must contain 'path' and 'value'", code="invalid_set_operation")
        ptr = item["path"]
        val = item["value"]
        tokens = _parse_pointer(ptr)

        curr = updated_meta
        for token in tokens[:-1]:
            if token not in curr or not isinstance(curr[token], dict):
                curr[token] = {}
            curr = curr[token]

        target_key = tokens[-1]
        curr[target_key] = copy.deepcopy(val)
        applied_count += 1

    # Apply remove operations
    for ptr in remove_ops:
        tokens = _parse_pointer(ptr)
        curr = updated_meta
        found = True
        for token in tokens[:-1]:
            if isinstance(curr, dict) and token in curr:
                curr = curr[token]
            else:
                found = False
                break

        target_key = tokens[-1]
        if found and isinstance(curr, dict) and target_key in curr:
            del curr[target_key]
            applied_count += 1
        else:
            raise ArtifactPatchError(f"Target key '{target_key}' in pointer '{ptr}' does not exist", code="remove_target_missing", path=ptr)

    for owned in guarded_ancestors:
        if _value_at(metadata, owned) != _value_at(updated_meta, owned):
            name = "/".join(owned)
            raise ArtifactPatchError(
                f"Field '{name}' is Core-owned and immutable; a patch of '/{owned[0]}' must keep it "
                f"(set the fields beside it by their own pointers)",
                code="core_owned_field",
                path="/" + name,
            )

    # Post-patch storage schema validation
    val_res = registry.validate_storage_schema(kind, updated_meta)
    if not val_res.valid:
        first_diag = val_res.diagnostics[0]
        raise ArtifactPatchError(
            f"Post-patch storage schema validation failed: {first_diag.message}",
            code=first_diag.code,
            path=first_diag.path,
        )

    updated_body = body_replacement if body_replacement is not None else body
    changed = (updated_meta != metadata) or (updated_body != body)

    return PatchOutcome(
        updated_metadata=updated_meta,
        updated_body=updated_body,
        changed=changed,
        applied_ops_count=applied_count,
    )
