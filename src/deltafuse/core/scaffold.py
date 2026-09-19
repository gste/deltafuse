"""Deterministic Change scaffolding and derived child indexing (AW-14).

``deltafuse new <change-id>`` creates a minimal, schema-valid Change package.
``update_change_child_index`` updates change.yaml child lists (tasks, slices,
decisions, deltas) from actual child artifacts on disk under ProductMutationLock.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.artifact_codec import strict_encode_yaml
from deltafuse.core.artifact_lock import ProductMutationLock
from deltafuse.core.artifact_reader import strict_read_artifact, strict_parse_yaml
from deltafuse.core.artifact_registry import ArtifactRegistry
from deltafuse.core.artifact_storage import atomic_replace
from deltafuse.core.fsm import find_repo_root
from deltafuse.core.frontmatter import parse_frontmatter

VALID_ROUTES = ("code", "docs", "ops")
CHANGE_ID_PATTERN = r"^CHG-[0-9]{3,}(-[a-z0-9-]+)?$"


class ScaffoldError(Exception):
    """Invalid or conflicting scaffolding request."""


def _get_framework_info(product_root: Path) -> dict[str, str]:
    lock = product_root / ".deltafuse" / "lock.yaml"
    if lock.is_file():
        try:
            data = yaml.safe_load(lock.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("framework"), dict):
                fw = data["framework"]
                return {
                    "version": str(fw.get("version", "3.1.0")),
                    "content_hash": str(fw.get("content_hash", "sha256:" + ("0" * 64))),
                }
        except Exception:
            pass
    return {
        "version": "3.1.0",
        "content_hash": "sha256:" + ("0" * 64),
    }


def _change_yaml(change_id: str, title: str, framework_info: dict[str, str], route: str = "code") -> dict[str, Any]:
    return {
        "schema_version": 3,
        "id": change_id,
        "title": title or change_id,
        "status": "normalized",
        "framework": framework_info,
        "route": route,
        "intent": "feature",
        "risk": "low",
        "source": {
            "request": "request.md",
            "intake_refs": [],
        },
        "analysis": {
            "routing": None,
            "summary": None,
        },
        "deltas": [],
        "slices": [],
        "decisions": [],
        "tasks": [],
        "verification": None,
    }


def scaffold_change(
    product_root: Path | str,
    change_id: str,
    *,
    route: str = "code",
    title: str = "",
) -> Path:
    """Create ``docs/changes/<change-id>/`` with minimal schema-valid artifacts."""
    change_id = (change_id or "").strip()
    if not _valid_change_id(change_id):
        raise ScaffoldError(
            f"Change id '{change_id}' must match CHG-<digits>[-slug], e.g. CHG-101-auth"
        )
    if route not in VALID_ROUTES:
        raise ScaffoldError(f"route must be one of {list(VALID_ROUTES)}")

    root = Path(product_root).resolve()
    change_dir = root / "docs" / "changes" / change_id
    if change_dir.exists():
        raise ScaffoldError(f"Change directory already exists: {change_dir}")
    archive = root / "docs" / "archive" / "changes"
    if archive.is_dir() and any(p.name.endswith(f"-{change_id}") for p in archive.iterdir() if p.is_dir()):
        raise ScaffoldError(f"Change id '{change_id}' was already archived")

    fw_info = _get_framework_info(root)
    data = _change_yaml(change_id, title, fw_info, route=route)

    # Validate scaffolded change.yaml against storage schema
    registry = ArtifactRegistry()
    val_res = registry.validate_storage_schema("change", data)
    if not val_res.valid:
        diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
        raise ScaffoldError(f"Scaffolded change.yaml schema validation failed: {'; '.join(diag_msgs)}")

    (change_dir / "slices").mkdir(parents=True)
    (change_dir / "tasks").mkdir()
    (change_dir / "evidence").mkdir()

    from deltafuse.core.artifact_storage import atomic_create
    content_str = strict_encode_yaml(data, kind="change")
    atomic_create(change_dir / "change.yaml", content_str.encode("utf-8"))

    req_str = (
        f"---\nchange: {change_id}\nstatus: drafted\nslices: []\n---\n\n"
        f"# {title or change_id}\n\n"
        "<!-- Raw intent. Claims stay unverified; Intake is not closed by scaffolding. -->\n"
    )
    atomic_create(change_dir / "request.md", req_str.encode("utf-8"))
    return change_dir



def update_change_child_index(change_dir: Path | str, child_kind: str, child_id: str) -> None:
    """Update change.yaml child lists (tasks, slices, decisions, deltas) from actual disk artifact."""
    change_path = Path(change_dir).resolve()
    if not change_path.is_dir():
        raise ScaffoldError(f"Change directory not found: {change_path}")

    product_root = find_repo_root(change_path)
    child_kind = child_kind.strip().lower()

    if child_kind == "task":
        child_file = change_path / "tasks" / f"{child_id}.md"
    elif child_kind == "slice":
        child_file = change_path / "slices" / f"{child_id}.md"
    elif child_kind == "spec-delta":
        child_file = change_path / "spec-delta.md"
    elif child_kind == "decision":
        from deltafuse.core.decide import find_decision_file
        child_file = find_decision_file(product_root, child_id)
    else:
        raise ScaffoldError(f"Unsupported child index kind: {child_kind}")

    if not child_file.is_file():
        raise ScaffoldError(f"Child artifact '{child_file}' does not exist on disk")

    child_bytes = child_file.read_bytes()
    parse_res = strict_read_artifact(child_bytes, has_frontmatter_delimiters=True)
    real_meta = parse_res.metadata
    real_id = str(real_meta.get("id") or child_id)
    real_status = str(real_meta.get("status") or "pending")

    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        raise ScaffoldError(f"change.yaml missing in {change_path}")

    with ProductMutationLock(product_root):
        change_bytes = change_file.read_bytes()
        change_sha256 = hashlib.sha256(change_bytes).hexdigest()
        change_meta = strict_parse_yaml(change_bytes.decode("utf-8"))

        field_key = "tasks" if child_kind == "task" else "slices" if child_kind == "slice" else "deltas" if child_kind == "spec-delta" else "decisions"
        items = change_meta.get(field_key) or []
        if not isinstance(items, list):
            items = []

        if child_kind in ("task", "decision"):
            if real_id not in items:
                items.append(real_id)
        elif child_kind == "slice":
            found = False
            new_items = []
            for item in items:
                if isinstance(item, dict) and item.get("id") == real_id:
                    new_items.append({"id": real_id, "status": real_status, "file": f"slices/{real_id}.md"})
                    found = True
                else:
                    new_items.append(item)
            if not found:
                new_items.append({"id": real_id, "status": real_status, "file": f"slices/{real_id}.md"})
            items = new_items
        elif child_kind == "spec-delta":
            delta_id = str(real_meta.get("id") or "DELTA-01")
            slice_id = str(real_meta.get("slice") or "SLICE-01")
            delta_kind = str(real_meta.get("kind") or "requirements")
            delta_summary = str(real_meta.get("summary") or "Spec delta")
            empty_proj = {"operation": "none", "refs": []}
            delta_obj = {
                "id": delta_id,
                "slice": slice_id,
                "kind": delta_kind,
                "summary": delta_summary,
                "specification": real_meta.get("specification") or empty_proj,
                "catalog": real_meta.get("catalog") or empty_proj,
                "decisions": real_meta.get("decisions") or empty_proj,
                "tasks": real_meta.get("tasks") or empty_proj,
                "tests": real_meta.get("tests") or empty_proj,
                "implementation": real_meta.get("implementation") or empty_proj,
                "evidence": real_meta.get("evidence") or empty_proj,
            }
            found = False
            new_items = []
            for item in items:
                if isinstance(item, dict) and item.get("id") == delta_id:
                    new_items.append(delta_obj)
                    found = True
                else:
                    new_items.append(item)
            if not found:
                new_items.append(delta_obj)
            items = new_items

        change_meta[field_key] = items

        registry = ArtifactRegistry()
        val_res = registry.validate_storage_schema("change", change_meta)
        if not val_res.valid:
            diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
            raise ScaffoldError(f"Updated change.yaml schema validation failed: {'; '.join(diag_msgs)}")

        candidate_str = strict_encode_yaml(change_meta, kind="change")
        candidate_bytes = candidate_str.encode("utf-8")

        atomic_replace(change_file, candidate_bytes, expected_sha256=change_sha256)


def _valid_change_id(change_id: str) -> bool:
    import re
    return re.match(CHANGE_ID_PATTERN, change_id) is not None
