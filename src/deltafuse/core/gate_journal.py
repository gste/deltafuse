"""Human Gate click log written only by `deltafuse decide` (kernel, no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TERMINAL_STATUSES = frozenset({"accepted", "rejected"})
JOURNAL_REL = ".deltafuse/gate-journal.jsonl"


def journal_path(product_root: Path) -> Path:
    return Path(product_root) / JOURNAL_REL


def append_click(
    product_root: Path,
    *,
    kind: str,
    status: str,
    rel_path: str,
    artifact_id: str,
    change: str | None,
) -> None:
    """Append one recorded Human Gate click. Never git push."""
    if kind not in {"decision", "spec"}:
        raise ValueError(f"unknown gate click kind: {kind!r}")
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"unknown gate click status: {status!r}")
    path = journal_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "kind": kind,
        "status": status,
        "id": artifact_id,
        "path": rel_path.replace("\\", "/"),
        "change": change,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_clicks(product_root: Path) -> list[dict[str, Any]]:
    path = journal_path(product_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def has_click(
    product_root: Path,
    *,
    kind: str,
    status: str,
    artifact_id: str | None = None,
    rel_path: str | None = None,
) -> bool:
    """True when decide recorded this terminal status for the artifact."""
    want_path = rel_path.replace("\\", "/") if rel_path else None
    for event in reversed(load_clicks(product_root)):
        if event.get("kind") != kind or event.get("status") != status:
            continue
        if artifact_id and event.get("id") == artifact_id:
            return True
        if want_path and event.get("path") == want_path:
            return True
    return False
