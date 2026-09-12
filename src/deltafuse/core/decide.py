"""Apply an explicit Human Gate choice (kernel, no LLM, no auto-accept)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.frontmatter import FrontmatterParseError, parse_frontmatter, replace_frontmatter
from deltafuse.core.fsm import check_gate, find_repo_root
from deltafuse.core.gate_journal import TERMINAL_STATUSES
from deltafuse.core import receipts
from deltafuse.core.integrity import list_proposed_decisions_for_change
from deltafuse.core.queue import load_product_root

DECIDE_STATUSES = ("accepted", "rejected")


class DecideError(Exception):
    """Invalid Human Gate apply (missing artifact, bad id, mixed flags)."""


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as ex:
        raise DecideError(f"Failed to parse '{path.as_posix()}': {ex}") from ex
    if not isinstance(data, dict):
        raise DecideError(f"'{path.as_posix()}' must be a YAML mapping")
    return data


def _write_yaml_mapping(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def find_decision_file(product_root: Path, decision: str) -> Path:
    raw = decision.strip()
    if not raw:
        raise DecideError("Decision id is empty")
    candidate = Path(raw)
    if candidate.suffix == ".md" or "/" in raw or "\\" in raw:
        path = (product_root / raw).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            path.relative_to(product_root.resolve())
        except ValueError as ex:
            raise DecideError(f"Decision path is outside the product: {raw}") from ex
        if not path.is_file():
            raise DecideError(f"Decision file not found: {raw}")
        return path
    dec_dir = product_root / "docs" / "decisions"
    if not dec_dir.is_dir():
        raise DecideError("docs/decisions/ is missing")
    matches = sorted(dec_dir.glob(f"{raw}*.md"))
    if not matches:
        raise DecideError(f"No decision file matches '{raw}'")
    if len(matches) > 1 and not any(p.stem == raw or p.name == f"{raw}.md" for p in matches):
        names = ", ".join(p.name for p in matches)
        raise DecideError(f"Decision id '{raw}' is ambiguous: {names}")
    exact = [p for p in matches if p.stem == raw or p.name.startswith(f"{raw}-") or p.stem.startswith(raw)]
    return exact[0] if exact else matches[0]


def _unblock_change_if_decisions_resolved(product_root: Path, change_id: str, change_dir: Path) -> str | None:
    leftover = list_proposed_decisions_for_change(change_id, product_root)
    change_file = change_dir / "change.yaml"
    if not change_file.is_file():
        return None
    data = _load_yaml_mapping(change_file)
    if leftover:
        return None
    if data.get("status") != "blocked-on-decision":
        return None
    from deltafuse.core.transitions import _receipt, transitions_path

    import json as _json
    from datetime import datetime, timezone

    data["status"] = "analyzing"
    _write_yaml_mapping(change_file, data)
    # V3-FIX-009: decide is a Core command, so its unblock transition is
    # journaled like any other Core status write.
    entry = {
        "kind": "unblock",
        "change": data.get("id") or change_dir.name,
        "gate": "decide",
        "from": "blocked-on-decision",
        "to": "analyzing",
        "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    entry["receipt"] = _receipt(entry)
    path = transitions_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline=chr(10)) as handle:
        handle.write(_json.dumps(entry, ensure_ascii=False) + chr(10))
    return "analyzing"


def _change_id_from_dir(change_dir: Path) -> str | None:
    change_file = change_dir / "change.yaml"
    if not change_file.is_file():
        return None
    try:
        data = _load_yaml_mapping(change_file)
    except DecideError:
        return None
    raw = data.get("id")
    return raw if isinstance(raw, str) and raw.strip() else None


def _optional_change_id(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise DecideError("change: must be a Change id or null")


def apply_decision(
    start: Path | str,
    *,
    status: str,
    decision: str | None = None,
    spec: bool = False,
) -> dict[str, Any]:
    """Write the human's recorded choice. Does not run from `next`."""
    if status not in DECIDE_STATUSES:
        raise DecideError(f"status must be accepted or rejected, got {status!r}")
    if bool(decision) == bool(spec):
        raise DecideError("Pass exactly one of --decision or --spec")
    start_path = Path(start).resolve()
    if spec:
        if (start_path / "change.yaml").is_file():
            change_dir = start_path
            product_root = find_repo_root(change_dir)
        else:
            raise DecideError("--spec requires a Change directory (path to change.yaml)")
        delta = change_dir / "spec-delta.md"
        if not delta.is_file():
            raise DecideError(f"spec-delta.md is missing in {change_dir.as_posix()}")
        try:
            text = replace_frontmatter(delta.read_text(encoding="utf-8"), {"status": status})
        except FrontmatterParseError as ex:
            raise DecideError(f"spec-delta.md: {ex}") from ex
        delta.write_text(text, encoding="utf-8")
        written = [_rel(product_root, delta)]
        change_id = _change_id_from_dir(change_dir)
        receipts.record_receipt(
            product_root,
            kind="spec",
            status=status,
            rel_path=written[0],
            artifact_id=change_id or change_dir.name,
            change=change_id,
            artifact=delta,
        )
        change_status = None
        if status == "accepted":
            change_file = change_dir / "change.yaml"
            data = _load_yaml_mapping(change_file)
            if data.get("status") == "specification-proposed":
                gate_errors = check_gate(change_dir, "specified")
                if not gate_errors:
                    data["status"] = "specified"
                    _write_yaml_mapping(change_file, data)
                    change_status = "specified"
                    written.append(_rel(product_root, change_file))
        else:
            # DF3-004: rejection loops the Change back to `analyzed` so the
            # Worker gets Specify work again; the rejected proposal stays on
            # disk (spec-delta.md status 'rejected') for the record.
            change_file = change_dir / "change.yaml"
            data = _load_yaml_mapping(change_file)
            if data.get("status") == "specification-proposed":
                data["status"] = "analyzed"
                _write_yaml_mapping(change_file, data)
                change_status = "analyzed"
                written.append(_rel(product_root, change_file))
        return {
            "ok": True,
            "gate": "spec",
            "status": status,
            "written": written,
            "change_status": change_status,
            "gate_errors": check_gate(change_dir, "specified") if status == "accepted" else [],
        }

    product_root = load_product_root(start_path)
    dec_path = find_decision_file(product_root, str(decision))
    try:
        meta, _ = parse_frontmatter(dec_path.read_text(encoding="utf-8"))
    except FrontmatterParseError as ex:
        raise DecideError(f"{dec_path.name}: {ex}") from ex
    if meta.get("status") != "proposed":
        raise DecideError(
            f"{dec_path.name} status is '{meta.get('status')}', expected proposed"
        )
    change_id = _optional_change_id(meta.get("change"))
    dec_path.write_text(
        replace_frontmatter(dec_path.read_text(encoding="utf-8"), {"status": status}),
        encoding="utf-8",
    )
    written = [_rel(product_root, dec_path)]
    dec_id = meta.get("id") if isinstance(meta.get("id"), str) else dec_path.stem
    receipts.record_receipt(
        product_root,
        kind="decision",
        status=status,
        rel_path=written[0],
        artifact_id=dec_id,
        change=change_id,
        artifact=dec_path,
    )
    change_dir = None
    if change_id and (start_path / "change.yaml").is_file():
        change_dir = start_path
    elif change_id:
        changes = product_root / "docs" / "changes"
        if changes.is_dir():
            for pkg in sorted(p.parent for p in changes.glob("*/change.yaml")):
                data = _load_yaml_mapping(pkg / "change.yaml")
                if data.get("id") == change_id:
                    change_dir = pkg
                    break
    change_status = None
    if change_dir is not None and change_id:
        change_status = _unblock_change_if_decisions_resolved(product_root, change_id, change_dir)
        if change_status:
            written.append(_rel(product_root, change_dir / "change.yaml"))
    return {
        "ok": True,
        "gate": "decision",
        "status": status,
        "decision": dec_id,
        "written": written,
        "change_status": change_status,
        "gate_errors": [],
    }
