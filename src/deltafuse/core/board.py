"""Read-only board snapshot for fuse-map (FM-001). No product writes, no check-gate."""

from __future__ import annotations

import copy
import datetime
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import VALID_CHANGE_STATUSES, find_repo_root
from deltafuse.core.lock import DEFAULT_CALL_WIDTH, normalize_call_width

BOARD_SCHEMA_VERSION = 1

# Happy-path geometry for the pinned lifecycle. Independent of which Changes exist.
# Terminals (archived, rejected, duplicate, superseded, not-reproduced) are omitted.
BOARD_LAYOUT: dict[str, Any] = {
    "columns": [
        {"id": "normalized", "statuses": ["normalized"]},
        {"id": "analyzed", "statuses": ["analyzing", "blocked-on-decision", "analyzed"]},
        {"id": "specified", "statuses": ["specification-proposed", "specified"]},
        {"id": "decomposed", "statuses": ["decomposed"]},
        {"id": "declared", "statuses": ["declaring", "declared"]},
        {"id": "implemented", "statuses": ["implementing", "implemented"]},
        {"id": "converged", "statuses": ["verifying", "converged"]},
    ],
    "steps": [
        {"id": "intake", "to": "normalized"},
        {"id": "analyze", "from": "normalized", "to": "analyzed"},
        {"id": "specify", "from": "analyzed", "to": "specified"},
        {"id": "decompose", "from": "specified", "to": "decomposed"},
        {"id": "declare", "from": "decomposed", "to": "declared"},
        {"id": "implement", "from": "declared", "to": "implemented"},
        {"id": "verify", "from": "implemented", "to": "converged"},
        {"id": "archive", "from": "converged"},
    ],
}

BOARD_TERMINAL_STATUSES = frozenset(
    {
        "archived",
        "rejected",
        "duplicate",
        "superseded",
        "not-reproduced",
    }
)

_CARD_ID_PREFIX = "CHG-"


class BoardError(Exception):
    """Product root / lock / config missing or unreadable."""


def board_layout() -> dict[str, Any]:
    return copy.deepcopy(BOARD_LAYOUT)


def layout_status_index(layout: dict[str, Any] | None = None) -> dict[str, str]:
    """Map change.yaml status -> column id. Raises BoardError on duplicates."""
    columns = (layout or BOARD_LAYOUT).get("columns") or []
    index: dict[str, str] = {}
    for column in columns:
        if not isinstance(column, dict):
            continue
        col_id = column.get("id")
        statuses = column.get("statuses") or []
        if not isinstance(col_id, str) or not isinstance(statuses, list):
            continue
        for status in statuses:
            if not isinstance(status, str):
                continue
            if status in index:
                raise BoardError(
                    f"Layout lists status {status!r} in both {index[status]!r} and {col_id!r}"
                )
            index[status] = col_id
    return index


def validate_board_layout(layout: dict[str, Any] | None = None) -> list[str]:
    """Return layout errors. Empty list means the snapshot geometry is emit-safe."""
    errors: list[str] = []
    try:
        index = layout_status_index(layout)
    except BoardError as ex:
        return [str(ex)]
    happy = VALID_CHANGE_STATUSES - BOARD_TERMINAL_STATUSES
    missing = sorted(happy - set(index))
    if missing:
        errors.append(f"Layout is missing happy-path statuses: {missing}")
    leaked = sorted(set(index) & BOARD_TERMINAL_STATUSES)
    if leaked:
        errors.append(f"Layout must not list terminal statuses: {leaked}")
    return errors


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_mapping(path: Path, *, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise BoardError(f"Not a DeltaFuse product (missing {path.as_posix()})")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as ex:
        raise BoardError(f"Unreadable {what}: {ex}") from ex
    if not isinstance(data, dict):
        raise BoardError(f"Unreadable {what}: expected a mapping")
    return data


def _posix(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.replace("\\", "/").rstrip("/")
    return default


def _product_paths(config: dict[str, Any]) -> dict[str, str]:
    paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
    archive_root = _posix(paths.get("archive"), "docs/archive")
    return {
        "changes": _posix(paths.get("changes"), "docs/changes"),
        "archive": f"{archive_root}/changes",
        "decisions": _posix(paths.get("decisions"), "docs/decisions"),
    }


def load_product_root(start: Path | str) -> Path:
    path = Path(start).resolve()
    if path.is_file():
        path = path.parent
    if (path / "change.yaml").is_file():
        root = find_repo_root(path)
    else:
        root = path if (path / ".deltafuse").is_dir() else find_repo_root(path)
    lock = root / ".deltafuse" / "lock.yaml"
    if not lock.is_file():
        raise BoardError(f"Not a DeltaFuse product (missing {lock.as_posix()})")
    return root


def _packages(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p.parent for p in root.glob("*/change.yaml"))


def _count_files(directory: Path, pattern: str) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.glob(pattern))


def _has_yaml(directory: Path) -> bool:
    return _count_files(directory, "*.yaml") > 0 or _count_files(directory, "*.yml") > 0


def _proposed_decision_ids(change_id: str, decisions_dir: Path) -> list[str]:
    if not decisions_dir.is_dir():
        return []
    found: list[str] = []
    for dec_file in sorted(decisions_dir.glob("*.md")):
        try:
            meta, _ = parse_frontmatter(dec_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        if meta.get("change") != change_id or meta.get("status") != "proposed":
            continue
        dec_id = meta.get("id")
        if isinstance(dec_id, str) and dec_id.startswith("DEC-"):
            found.append(dec_id)
    return found


def _card_from_package(
    product_root: Path,
    change_path: Path,
    *,
    decisions_dir: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    change_file = change_path / "change.yaml"
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
    except Exception as ex:
        return None, f"Skipped unreadable package {change_path.name}: {ex}"
    if not isinstance(data, dict):
        return None, f"Skipped unreadable package {change_path.name}: change.yaml is not a mapping"
    change_id = data.get("id")
    if not isinstance(change_id, str) or not change_id.startswith(_CARD_ID_PREFIX):
        return None, f"Skipped package {change_path.name}: missing CHG-* id"
    title = data.get("title")
    if not isinstance(title, str):
        title = change_id
    status = data.get("status")
    if not isinstance(status, str) or not status:
        return None, f"Skipped package {change_id}: missing status"
    route = data.get("route")
    if route not in {"code", "docs", "ops"}:
        route = "code"
    return {
        "id": change_id,
        "title": title,
        "status": status,
        "route": route,
        "path": _rel(product_root, change_path),
        "blocked_decisions": _proposed_decision_ids(change_id, decisions_dir),
        "slice_count": _count_files(change_path / "slices", "*.md"),
        "task_count": _count_files(change_path / "tasks", "*.md"),
        "has_red": _has_yaml(change_path / "evidence" / "red"),
        "has_green": _has_yaml(change_path / "evidence" / "green"),
    }, None


def _product_block(
    product_root: Path,
    config: dict[str, Any],
    lock: dict[str, Any],
    paths: dict[str, str],
) -> dict[str, Any]:
    project = config.get("project") if isinstance(config.get("project"), dict) else {}
    baseline = project.get("baseline")
    if baseline not in {"draft", "accepted"}:
        raise BoardError("project.baseline must be 'draft' or 'accepted'")
    fw = lock.get("framework") if isinstance(lock.get("framework"), dict) else {}
    version = fw.get("version")
    content_hash = fw.get("content_hash")
    lock_workflow = lock.get("workflow") if isinstance(lock.get("workflow"), dict) else {}
    cfg_workflow = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    width = normalize_call_width(lock_workflow.get("call_width")) or normalize_call_width(
        cfg_workflow.get("call_width")
    )
    product: dict[str, Any] = {
        "baseline": baseline,
        "call_width": width or DEFAULT_CALL_WIDTH,
        "changes_path": paths["changes"],
        "archive_changes_path": paths["archive"],
    }
    if isinstance(version, str) and version:
        product["framework_version"] = version
    if isinstance(content_hash, str) and content_hash:
        product["framework_content_hash"] = content_hash
    return product


def build_board_snapshot(
    start: Path | str,
    *,
    include_archive: bool = False,
) -> dict[str, Any]:
    """Read-only projection. Does not write product files or run check-gate."""
    layout_errors = validate_board_layout()
    if layout_errors:
        raise BoardError("; ".join(layout_errors))
    product_root = load_product_root(start)
    config = _load_mapping(product_root / ".deltafuse" / "config.yaml", what="config")
    lock = _load_mapping(product_root / ".deltafuse" / "lock.yaml", what="lock")
    paths = _product_paths(config)
    warnings: list[str] = []
    decisions_dir = product_root / paths["decisions"]

    changes: list[dict[str, Any]] = []
    for package in _packages(product_root / paths["changes"]):
        card, warning = _card_from_package(
            product_root, package, decisions_dir=decisions_dir
        )
        if warning:
            warnings.append(warning)
        if card is not None:
            changes.append(card)
    changes.sort(key=lambda card: card["id"])

    snapshot: dict[str, Any] = {
        "schema_version": BOARD_SCHEMA_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "product": _product_block(product_root, config, lock, paths),
        "layout": board_layout(),
        "changes": changes,
        "warnings": warnings,
    }
    if include_archive:
        archive_cards: list[dict[str, Any]] = []
        for package in _packages(product_root / paths["archive"]):
            card, warning = _card_from_package(
                product_root, package, decisions_dir=decisions_dir
            )
            if warning:
                warnings.append(warning)
            if card is not None:
                archive_cards.append(card)
        archive_cards.sort(key=lambda card: card["id"])
        snapshot["archive"] = archive_cards
    return snapshot
