"""Analyze pass cursor: Core names one write (routing | one slice | coverage)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.integrity import load_capability_catalog, lookup_capability

ANALYZE_PASSES = ("routing", "slice", "coverage")

_ROUTING_READ = [
    "docs/changes/*/request.md",
    "docs/changes/*/change.yaml",
    "docs/spec/_capabilities.yaml",
    ".deltafuse/**",
]
_SLICE_READ = [
    "docs/changes/*/request.md",
    "docs/changes/*/routing.yaml",
    "docs/changes/*/change.yaml",
    "docs/changes/*/slices/**",
    "docs/decisions/**",
]
_COVERAGE_READ = [
    "docs/changes/*/request.md",
    "docs/changes/*/routing.yaml",
    "docs/changes/*/change.yaml",
    "docs/changes/*/slices/**",
]
_ROUTING_WRITE = [
    "docs/changes/*/routing.yaml",
    "docs/changes/*/change.yaml",
]
_SLICE_WRITE = [
    "docs/changes/*/slices/**",
    "docs/changes/*/change.yaml",
]
_COVERAGE_WRITE = [
    "docs/changes/*/coverage.yaml",
    "docs/changes/*/change.yaml",
]


@dataclass
class AnalyzeCursor:
    pass_name: str
    reason: str
    capability: str | None = None
    slice_id: str | None = None
    spec_refs: list[str] = field(default_factory=list)
    allowed_read: list[str] = field(default_factory=list)
    allowed_write: list[str] = field(default_factory=list)


def _load_yaml_mapping(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _strip_anchor(ref: str) -> str:
    return ref.split("#", 1)[0].strip()


def routing_primary_capabilities(change_path: Path | str) -> list[str]:
    """Distinct owning capabilities from routing.yaml, stable order."""
    data = _load_yaml_mapping(Path(change_path) / "routing.yaml")
    if not data:
        return []
    claims = data.get("claims")
    if not isinstance(claims, dict):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for row in claims.values():
        if not isinstance(row, dict):
            continue
        cap = row.get("primary_capability")
        if isinstance(cap, str) and cap and cap not in seen:
            seen.add(cap)
            ordered.append(cap)
    ordered.sort()
    return ordered


def slice_primary_capabilities(change_path: Path | str) -> dict[str, str]:
    """Map SLICE-NN -> primary_capability for readable slice files."""
    slices_dir = Path(change_path) / "slices"
    found: dict[str, str] = {}
    if not slices_dir.is_dir():
        return found
    for slice_file in sorted(slices_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        slice_id = meta.get("id")
        cap = meta.get("primary_capability")
        if isinstance(slice_id, str) and isinstance(cap, str) and cap:
            found[slice_id] = cap
    return found


def covered_primary_capabilities(change_path: Path | str) -> set[str]:
    return set(slice_primary_capabilities(change_path).values())


def uncovered_primary_capabilities(change_path: Path | str) -> list[str]:
    covered = covered_primary_capabilities(change_path)
    return [cap for cap in routing_primary_capabilities(change_path) if cap not in covered]


def next_slice_id(change_path: Path | str) -> str:
    existing = set(slice_primary_capabilities(change_path))
    n = 1
    while True:
        candidate = f"SLICE-{n:02d}"
        if candidate not in existing:
            return candidate
        n += 1


def catalog_spec_refs(product_root: Path | str, capability: str) -> list[str]:
    catalog, errors = load_capability_catalog(Path(product_root))
    if errors or catalog is None:
        return []
    cap = lookup_capability(catalog, capability)
    if not cap:
        return []
    raw = cap.get("spec") or []
    if not isinstance(raw, list):
        return []
    refs: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            refs.append(item.strip())
    return refs


def analyze_allowed_write(pass_name: str) -> list[str]:
    if pass_name == "routing":
        return list(_ROUTING_WRITE)
    if pass_name == "slice":
        return list(_SLICE_WRITE)
    if pass_name == "coverage":
        return list(_COVERAGE_WRITE)
    return []


def analyze_allowed_read(pass_name: str, spec_refs: list[str] | None = None) -> list[str]:
    if pass_name == "routing":
        return list(_ROUTING_READ)
    if pass_name == "slice":
        extra: list[str] = []
        for ref in spec_refs or []:
            path = _strip_anchor(ref)
            if path and path not in extra and path not in _SLICE_READ:
                extra.append(path)
        return [*_SLICE_READ, *extra]
    if pass_name == "coverage":
        return list(_COVERAGE_READ)
    return []


def _change_status(change_path: Path) -> str | None:
    data = _load_yaml_mapping(change_path / "change.yaml")
    if not data:
        return None
    status = data.get("status")
    return status if isinstance(status, str) else None


def next_analyze_pass(
    change_path: Path | str,
    product_root: Path | str,
) -> AnalyzeCursor | None:
    """Next Analyze write for this Change, or None when Analyze is complete on disk."""
    path = Path(change_path)
    if not (path / "routing.yaml").is_file():
        return AnalyzeCursor(
            pass_name="routing",
            reason="Write routing.yaml from request.md and the capability catalog",
            allowed_read=analyze_allowed_read("routing"),
            allowed_write=analyze_allowed_write("routing"),
        )
    uncovered = uncovered_primary_capabilities(path)
    if uncovered:
        cap = uncovered[0]
        spec_refs = catalog_spec_refs(product_root, cap)
        slice_id = next_slice_id(path)
        return AnalyzeCursor(
            pass_name="slice",
            reason=f"Write slices/{slice_id}.md for {cap}",
            capability=cap,
            slice_id=slice_id,
            spec_refs=spec_refs,
            allowed_read=analyze_allowed_read("slice", spec_refs),
            allowed_write=analyze_allowed_write("slice"),
        )
    if not (path / "coverage.yaml").is_file():
        return AnalyzeCursor(
            pass_name="coverage",
            reason="Write coverage.yaml from routing and slice frontmatter",
            allowed_read=analyze_allowed_read("coverage"),
            allowed_write=analyze_allowed_write("coverage"),
        )
    status = _change_status(path)
    if status in {"normalized", "analyzing"}:
        return AnalyzeCursor(
            pass_name="coverage",
            reason="Analyze files complete; check-gate analyzed and set status analyzed",
            allowed_read=analyze_allowed_read("coverage"),
            allowed_write=analyze_allowed_write("coverage"),
        )
    return None
