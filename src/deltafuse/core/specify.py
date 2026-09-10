"""Specify pass cursor: Core names one slice (or the specified close)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deltafuse.core.analyze import catalog_spec_refs, load_slice_records
from deltafuse.core.frontmatter import parse_frontmatter

SPECIFIED_SLICE_STATUSES = {"specified", "decomposed", "verified"}
_CATALOG_FILE = "docs/spec/_capabilities.yaml"

_SLICE_READ = [
    "docs/changes/*/request.md",
    "docs/changes/*/routing.yaml",
    "docs/changes/*/change.yaml",
    "docs/changes/*/slices/**",
    "docs/changes/*/spec-delta.md",
    "docs/decisions/**",
]
_SLICE_WRITE = [
    "docs/changes/*/spec-delta.md",
    "docs/changes/*/change.yaml",
    "docs/changes/*/slices/**",
    _CATALOG_FILE,
]
_CLOSE_READ = [
    "docs/changes/*/change.yaml",
    "docs/changes/*/slices/**",
    "docs/changes/*/spec-delta.md",
]
_CLOSE_WRITE = [
    "docs/changes/*/change.yaml",
    "docs/changes/*/spec-delta.md",
]


@dataclass
class SpecifyCursor:
    pass_name: str
    reason: str
    slice_id: str | None = None
    capability: str | None = None
    spec_refs: list[str] = field(default_factory=list)
    allowed_read: list[str] = field(default_factory=list)
    allowed_write: list[str] = field(default_factory=list)


def spec_ref_file(ref: str) -> str:
    return ref.split("#", 1)[0].strip().replace("\\", "/")


def _unique_files(refs: list[str]) -> list[str]:
    files: list[str] = []
    for ref in refs:
        path = spec_ref_file(ref)
        if path and path not in files:
            files.append(path)
    return files


def slice_spec_refs(record: Any, product_root: Path | str) -> list[str]:
    refs = list(record.spec_refs)
    if not refs:
        refs = list(catalog_spec_refs(product_root, record.primary_capability))
    return refs


def allowed_live_spec_files(change_path: Path | str, product_root: Path | str) -> set[str]:
    allowed = {_CATALOG_FILE}
    for record in load_slice_records(change_path):
        for path in _unique_files(slice_spec_refs(record, product_root)):
            allowed.add(path)
    return allowed


def spec_delta_outside_slice_files(
    change_path: Path | str,
    product_root: Path | str,
) -> list[str]:
    """Return errors if spec-delta added/modified files are not in slice spec_refs."""
    delta_file = Path(change_path) / "spec-delta.md"
    if not delta_file.is_file():
        return []
    try:
        meta, _ = parse_frontmatter(delta_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(meta, dict):
        return []
    allow = allowed_live_spec_files(change_path, product_root)
    errors: list[str] = []
    for kind in ("added", "modified"):
        raw = meta.get(kind) or []
        if not isinstance(raw, list):
            continue
        for sref in raw:
            if not isinstance(sref, str):
                continue
            path = spec_ref_file(sref)
            if path and path not in allow:
                errors.append(
                    f"Gate specified: spec-delta {kind} '{sref}' is outside slice spec_refs"
                )
    return errors


def unspecified_slices(change_path: Path | str) -> list[Any]:
    pending = [
        row
        for row in load_slice_records(change_path)
        if row.status not in SPECIFIED_SLICE_STATUSES
    ]
    pending.sort(key=lambda row: row.slice_id)
    return pending


def next_specify_pass(
    change_path: Path | str,
    product_root: Path | str,
) -> SpecifyCursor | None:
    """Next Specify write for an analyzed Change."""
    pending = unspecified_slices(change_path)
    if pending:
        record = pending[0]
        spec_refs = slice_spec_refs(record, product_root)
        spec_files = _unique_files(spec_refs)
        return SpecifyCursor(
            pass_name="slice",
            reason=f"Specify slices/{record.slice_id}.md ({record.primary_capability})",
            slice_id=record.slice_id,
            capability=record.primary_capability,
            spec_refs=spec_refs,
            allowed_read=[*_SLICE_READ, *spec_files],
            allowed_write=[*_SLICE_WRITE, *spec_files],
        )
    return SpecifyCursor(
        pass_name="close",
        reason="All slices specified; check-gate specified and set Change status",
        allowed_read=list(_CLOSE_READ),
        allowed_write=list(_CLOSE_WRITE),
    )
