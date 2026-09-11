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


_PRIVATE_ATTR = re.compile(r"\._[A-Za-z_]")


def test_source_uses_private_symbols(source: str) -> bool:
    """True if test source pokes product internals (._attr or _-prefixed imports)."""
    if _PRIVATE_ATTR.search(source):
        return True
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("from ") and " import " in line:
            imported = line.split(" import ", 1)[1].strip("() ")
            names = imported.split(",")
        elif line.startswith("import "):
            names = line[len("import "):].split(",")
        else:
            continue
        for part in names:
            name = part.strip().split(" as ")[0].strip()
            last = name.split(".")[-1]
            if last.startswith("_") and not last.startswith("__"):
                return True
    return False


def scan_changed_paths_for_private_test_access(
    repo_root: Path,
    changed_paths: list[str],
) -> list[str]:
    """Return errors for test files in *changed_paths* that access private symbols."""
    errors: list[str] = []
    for rel in changed_paths:
        if not isinstance(rel, str):
            continue
        normalized = rel.replace("\\", "/")
        name = Path(normalized).name
        if not (
            normalized.startswith("tests/")
            or name.startswith("test_")
            or name.endswith("_test.py")
        ):
            continue
        if not name.endswith(".py"):
            continue
        path = (repo_root / rel).resolve()
        if not path_is_inside_repo(path, repo_root) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if test_source_uses_private_symbols(text):
            errors.append(
                f"Red test '{rel}' accesses private symbols; "
                "use the public oracle or record already-green"
            )
    return errors


_CR_CLAIM = re.compile(r"\b(CR-[0-9]{3,})\b")
_BULLET_CLAIM = re.compile(
    r"(?m)^[ \t]*[-*][ \t]+(CR-[0-9]{3,}|[A-Z]{1,3}[0-9]{1,3})\b"
)


def extract_claims_from_request(request_md_content: str) -> list[str]:
    """Extract stable claim IDs from request.md (CR-* and S02-style O1/E1 bullets)."""
    found: list[str] = []
    seen: set[str] = set()

    def add(cid: str) -> None:
        if cid not in seen:
            seen.add(cid)
            found.append(cid)

    for match in _BULLET_CLAIM.finditer(request_md_content):
        add(match.group(1))
    for match in _CR_CLAIM.finditer(request_md_content):
        add(match.group(1))
    return found


def path_is_inside_repo(path: Path, repo_root: Path) -> bool:
    """True if resolved *path* is the repository root or a descendant of it."""
    repo = repo_root.resolve()
    resolved = path.resolve()
    return resolved == repo or resolved.is_relative_to(repo)


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
    if not path_is_inside_repo(file_path, repo_root):
        return f"Path traversal forbidden: '{file_part}' is outside repository root"
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
    if not path_is_inside_repo(dec_path, repo_root):
        return [f"Path traversal forbidden: '{design_ref}' is outside repository root"]
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


def spec_ref_is_under_docs_spec(spec_ref: str, repo_root: Path) -> bool:
    """True if the resolved spec_ref file lives under docs/spec/ inside repo_root."""
    file_part = spec_ref.split("#", 1)[0]
    resolved = (repo_root / file_part).resolve()
    if not path_is_inside_repo(resolved, repo_root):
        return False
    try:
        rel = resolved.relative_to(repo_root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 2 and parts[0] == "docs" and parts[1] == "spec"


def load_capability_catalog(repo_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load docs/spec/_capabilities.yaml. Schema validation is the caller's job."""
    catalog_path = repo_root / "docs" / "spec" / "_capabilities.yaml"
    if not catalog_path.is_file():
        return None, ["Capability catalog 'docs/spec/_capabilities.yaml' is missing"]
    try:
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except Exception as ex:
        return None, [f"Failed to parse docs/spec/_capabilities.yaml: {ex}"]
    if not isinstance(data, dict):
        return None, ["Capability catalog 'docs/spec/_capabilities.yaml' must be a mapping"]
    return data, []


def lookup_capability(catalog: dict[str, Any], primary: str) -> dict[str, Any] | None:
    """Resolve a slice primary_capability to a catalog capability object."""
    if not primary or not isinstance(catalog, dict):
        return None
    domains = catalog.get("domains") or {}
    if not isinstance(domains, dict):
        return None
    if "." in primary:
        domain, cap = primary.split(".", 1)
        node = domains.get(domain)
        if not isinstance(node, dict):
            return None
        caps = node.get("capabilities") or {}
        found = caps.get(cap) if isinstance(caps, dict) else None
        return found if isinstance(found, dict) else None
    matches: list[dict[str, Any]] = []
    for dobj in domains.values():
        if not isinstance(dobj, dict):
            continue
        caps = dobj.get("capabilities") or {}
        if isinstance(caps, dict) and isinstance(caps.get(primary), dict):
            matches.append(caps[primary])
    if len(matches) == 1:
        return matches[0]
    domain = domains.get(primary)
    if isinstance(domain, dict):
        caps = domain.get("capabilities") or {}
        live = [c for c in caps.values() if isinstance(c, dict)] if isinstance(caps, dict) else []
        if len(live) == 1:
            return live[0]
    return None


def validate_catalog_capability_specs(
    catalog: dict[str, Any],
    repo_root: Path,
    primary_capabilities: list[str],
) -> list[str]:
    """Each named capability must exist in the catalog with at least one live spec file."""
    errors: list[str] = []
    seen: set[str] = set()
    for name in primary_capabilities:
        if not name or name in seen:
            continue
        seen.add(name)
        cap = lookup_capability(catalog, name)
        if cap is None:
            errors.append(
                f"Capability '{name}' is not present in docs/spec/_capabilities.yaml"
            )
            continue
        spec_paths = cap.get("spec") or []
        if not isinstance(spec_paths, list) or not spec_paths:
            errors.append(f"Capability '{name}' has no live spec files in the catalog")
            continue
        for sp in spec_paths:
            if not isinstance(sp, str):
                errors.append(f"Capability '{name}' has a non-string spec path")
                continue
            if not spec_ref_is_under_docs_spec(sp, repo_root):
                errors.append(
                    f"Capability '{name}' spec path '{sp}' must be under docs/spec/"
                )
                continue
            s_err = validate_spec_ref(sp, repo_root)
            if s_err:
                errors.append(f"Capability '{name}': {s_err}")
    return errors


def list_proposed_decisions_for_change(change_id: str, repo_root: Path) -> list[dict[str, str]]:
    """Proposed DEC-* records for a Change: id, path (relative), title, filename."""
    dec_dir = repo_root / "docs" / "decisions"
    if not dec_dir.is_dir():
        return []
    found: list[dict[str, str]] = []
    for dec_file in sorted(dec_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(dec_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("change") != change_id or meta.get("status") != "proposed":
            continue
        dec_id = meta.get("id")
        title = meta.get("title")
        found.append(
            {
                "id": dec_id if isinstance(dec_id, str) else dec_file.stem,
                "path": dec_file.relative_to(repo_root).as_posix(),
                "filename": dec_file.name,
                "title": title if isinstance(title, str) and title.strip() else dec_file.stem,
            }
        )
    return found


def find_unresolved_decisions_for_change(change_id: str, repo_root: Path) -> list[str]:
    """Finds any decision records in docs/decisions/ associated with change_id that are in 'proposed' status."""
    return [
        f"Decision '{row['filename']}' for Change '{change_id}' is in 'proposed' status"
        for row in list_proposed_decisions_for_change(change_id, repo_root)
    ]


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
