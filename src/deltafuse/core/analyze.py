"""Analyze pass cursor: Core names one write (routing | one slice | coverage)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.integrity import (
    extract_claims_from_request,
    load_capability_catalog,
    lookup_capability,
)

ANALYZE_PASSES = ("routing", "slice", "coverage")

_COVERAGE_STATUSES = {
    "pending",
    "analyzing",
    "analyzed",
    "specified",
    "decomposed",
    "targeting",
    "target-confirmed",
    "implementing",
    "implemented",
    "verified",
    "rejected",
    "not-reproduced",
}


class CoverageError(Exception):
    """Cannot derive coverage.yaml from routing and slices."""

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


@dataclass(frozen=True)
class SliceRecord:
    slice_id: str
    primary_capability: str
    claims: tuple[str, ...]
    spec_refs: tuple[str, ...]
    status: str | None = None


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
            reason="Run deltafuse coverage, then check-gate analyzed",
            allowed_read=analyze_allowed_read("coverage"),
            allowed_write=analyze_allowed_write("coverage"),
        )
    status = _change_status(path)
    if status in {"normalized", "analyzing"}:
        return AnalyzeCursor(
            pass_name="coverage",
            reason="Run deltafuse coverage if needed, then check-gate analyzed",
            allowed_read=analyze_allowed_read("coverage"),
            allowed_write=analyze_allowed_write("coverage"),
        )
    return None


def routing_claim_capabilities(change_path: Path | str) -> dict[str, str]:
    data = _load_yaml_mapping(Path(change_path) / "routing.yaml")
    if not data:
        return {}
    claims = data.get("claims")
    if not isinstance(claims, dict):
        return {}
    caps: dict[str, str] = {}
    for cid, row in claims.items():
        if not isinstance(cid, str) or not isinstance(row, dict):
            continue
        cap = row.get("primary_capability")
        if isinstance(cap, str) and cap:
            caps[cid] = cap
    return caps


def load_slice_records(change_path: Path | str) -> list[SliceRecord]:
    records: list[SliceRecord] = []
    slices_dir = Path(change_path) / "slices"
    if not slices_dir.is_dir():
        return records
    for slice_file in sorted(slices_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        slice_id = meta.get("id")
        cap = meta.get("primary_capability")
        if not isinstance(slice_id, str) or not isinstance(cap, str) or not cap:
            continue
        raw_claims = meta.get("claims") or []
        claims = tuple(c for c in raw_claims if isinstance(c, str)) if isinstance(raw_claims, list) else ()
        raw_refs = meta.get("spec_refs") or []
        refs = tuple(r for r in raw_refs if isinstance(r, str)) if isinstance(raw_refs, list) else ()
        status = meta.get("status")
        records.append(
            SliceRecord(
                slice_id=slice_id,
                primary_capability=cap,
                claims=claims,
                spec_refs=refs,
                status=status if isinstance(status, str) else None,
            )
        )
    records.sort(key=lambda row: row.slice_id)
    return records


def _assign_slice(
    claim_id: str,
    routing_cap: str | None,
    slices: list[SliceRecord],
) -> SliceRecord | None:
    listed = [row for row in slices if claim_id in row.claims]
    if listed:
        return min(listed, key=lambda row: row.slice_id)
    if routing_cap:
        same = [row for row in slices if row.primary_capability == routing_cap]
        if same:
            return min(same, key=lambda row: row.slice_id)
    return None


def _change_id(change_path: Path) -> str:
    data = _load_yaml_mapping(change_path / "change.yaml")
    if data:
        cid = data.get("id")
        if isinstance(cid, str) and cid:
            return cid
    return change_path.name


def build_coverage_document(change_path: Path | str) -> dict[str, Any]:
    """Derive coverage.yaml from request claims, routing, and slice frontmatter."""
    path = Path(change_path)
    if not (path / "routing.yaml").is_file():
        raise CoverageError("routing.yaml is missing")
    uncovered = uncovered_primary_capabilities(path)
    if uncovered:
        raise CoverageError(
            "routing capability has no slice: " + ", ".join(uncovered)
        )
    request = path / "request.md"
    if not request.is_file():
        raise CoverageError("request.md is missing")
    req_claims = extract_claims_from_request(request.read_text(encoding="utf-8"))
    if not req_claims:
        raise CoverageError("request.md has no claims")

    slices = load_slice_records(path)
    caps = routing_claim_capabilities(path)
    existing = _load_yaml_mapping(path / "coverage.yaml") or {}
    existing_claims = existing.get("claims") if isinstance(existing.get("claims"), dict) else {}
    slice_ids = {row.slice_id for row in slices}

    claims_out: dict[str, Any] = {}
    unmapped: list[str] = []
    for cid in req_claims:
        prev = existing_claims.get(cid) if isinstance(existing_claims.get(cid), dict) else {}
        record: SliceRecord | None = None
        prev_slice = prev.get("slice") if isinstance(prev, dict) else None
        if isinstance(prev_slice, str) and prev_slice in slice_ids:
            record = next(row for row in slices if row.slice_id == prev_slice)
        else:
            record = _assign_slice(cid, caps.get(cid), slices)
        if record is None:
            unmapped.append(cid)
            continue
        prev_refs = prev.get("spec_refs") if isinstance(prev, dict) else None
        if isinstance(prev_refs, list) and any(isinstance(item, str) for item in prev_refs):
            spec_refs = [item for item in prev_refs if isinstance(item, str)]
        else:
            spec_refs = list(record.spec_refs)
        prev_tasks = prev.get("tasks") if isinstance(prev, dict) else None
        tasks = [item for item in prev_tasks if isinstance(item, str)] if isinstance(prev_tasks, list) else []
        prev_evidence = prev.get("evidence") if isinstance(prev, dict) else None
        evidence: dict[str, str] = {}
        if isinstance(prev_evidence, dict):
            for key in ("red", "green", "regression", "verification"):
                value = prev_evidence.get(key)
                if isinstance(value, str) and value:
                    evidence[key] = value
        status = prev.get("status") if isinstance(prev, dict) else None
        if not isinstance(status, str) or status not in _COVERAGE_STATUSES:
            status = "pending"
        claims_out[cid] = {
            "slice": record.slice_id,
            "tasks": tasks,
            "spec_refs": spec_refs,
            "evidence": evidence,
            "status": status,
        }
    if unmapped:
        raise CoverageError("no slice for claims: " + ", ".join(unmapped))
    return {"change": _change_id(path), "claims": claims_out}


def write_coverage(change_path: Path | str) -> Path:
    """Write coverage.yaml. Does not set Change status or touch spec/code."""
    path = Path(change_path)
    dest = path / "coverage.yaml"
    document = build_coverage_document(path)
    dest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return dest
