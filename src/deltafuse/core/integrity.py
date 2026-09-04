"""Integrity and traceability validation engine for DeltaFuse Change packages."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml

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
