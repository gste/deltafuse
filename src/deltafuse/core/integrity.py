"""Integrity and traceability validation engine for DeltaFuse Change packages."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.frontmatter import parse_frontmatter


class IntegrityViolation(Exception):
    """Raised when link integrity or coverage traceability invariants are violated."""
    pass


def extract_claims_from_request(request_md_content: str) -> list[str]:
    """Extracts claim IDs defined in request.md."""
    pattern = re.compile(r"\b(CR-[0-9]{3,})\b")
    found = pattern.findall(request_md_content)
    return list(dict.fromkeys(found))


def find_spec_anchors(spec_file_path: Path) -> set[str]:
    """Extracts anchor tags and headers from a specification markdown file."""
    if not spec_file_path.is_file():
        return set()
    text = spec_file_path.read_text(encoding="utf-8")
    html_anchors = re.findall(r"<(?:a|span)[^>]*(?:id|name)=['\"]([^'\"]+)['\"]", text, re.IGNORECASE)
    header_anchors = re.findall(r"\b((?:REQ|SC|POL)-[A-Z0-9_-]+)\b", text)
    return set(html_anchors) | set(header_anchors)


def validate_spec_ref(spec_ref: str, repo_root: Path) -> str | None:
    """Validates that a spec reference (e.g. 'docs/spec/core.md#REQ-01' or 'docs/spec/core.md')
    points to an existing file and anchor. Returns an error message if invalid, or None if valid.
    """
    if not spec_ref:
        return None

    if "#" in spec_ref:
        file_part, anchor = spec_ref.split("#", 1)
    else:
        file_part, anchor = spec_ref, None

    file_path = (repo_root / file_part).resolve()
    if not file_path.is_file():
        return f"Referenced specification file does not exist: '{file_part}'"

    if anchor:
        anchors = find_spec_anchors(file_path)
        if anchor not in anchors:
            return f"Anchor '#{anchor}' not found in specification file '{file_part}'"

    return None


def validate_decision_ref(design_ref: str | None, repo_root: Path) -> list[str]:
    """Validates that a design_ref points to an existing accepted DEC-* decision file."""
    if not design_ref:
        return []

    errors: list[str] = []
    dec_path = (repo_root / design_ref).resolve()
    if not dec_path.is_file():
        return [f"Referenced decision record does not exist: '{design_ref}'"]

    try:
        meta, _ = parse_frontmatter(dec_path.read_text(encoding="utf-8"))
        status = meta.get("status")
        if status != "accepted":
            errors.append(
                f"Referenced decision '{dec_path.name}' has status '{status}', "
                f"must be 'accepted' (Change is blocked-on-decision)"
            )
    except Exception as ex:
        errors.append(f"Failed to parse decision record '{dec_path.name}': {ex}")

    return errors


def find_unresolved_decisions_for_change(change_id: str, repo_root: Path) -> list[str]:
    """Finds any decision records in docs/decisions/ associated with change_id that are in 'proposed' status."""
    dec_dir = repo_root / "docs" / "decisions"
    if not dec_dir.is_dir():
        return []

    unresolved: list[str] = []
    for dec_file in dec_dir.glob("*.md"):
        try:
            meta, _ = parse_frontmatter(dec_file.read_text(encoding="utf-8"))
            if meta.get("change") == change_id and meta.get("status") == "proposed":
                unresolved.append(
                    f"Decision '{dec_file.name}' for Change '{change_id}' is in 'proposed' status"
                )
        except Exception:
            pass
    return unresolved


def validate_coverage_completeness(
    request_claims: list[str],
    coverage_data: dict[str, Any]
) -> list[str]:
    """Verifies that all normalized claims in request.md are mapped in coverage.yaml and no orphan claims exist."""
    errors: list[str] = []
    covered_claims = coverage_data.get("claims", {})
    if not isinstance(covered_claims, dict):
        return ["coverage.yaml has invalid or missing 'claims' mapping"]

    for claim in request_claims:
        if claim not in covered_claims:
            errors.append(f"Claim '{claim}' from request.md is not mapped in coverage.yaml")

    for claim, details in covered_claims.items():
        if claim not in request_claims:
            errors.append(f"Claim '{claim}' in coverage.yaml is an orphan (not found in request.md)")
        if isinstance(details, dict):
            if not details.get("slice"):
                errors.append(f"Claim '{claim}' has no primary slice assigned")

    return errors
