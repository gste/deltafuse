"""Core-owned lifecycle transitions (DF3-004).

The Worker writes Change artifacts but never confirms its own progress by
hand-editing status fields. ``advance`` is the single Core command that
validates a gate, applies the formal transition table atomically and records a
verifiable receipt. ``next`` and ``check-gate`` stay read-only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.fsm import check_gate, can_transition, find_repo_root

# Gate -> target status. Human Gates (intake via decide, specified via decide
# spec) are journaled by check_gate's own human-gate replay.
GATE_TARGETS: dict[str, str] = {
    "intake": "analyzing",
    "analyzed": "analyzed",
    "specified": "specified",
    "decomposed": "decomposed",
    "targeting": "target-confirmed",
    "implemented": "implemented",
    "converged": "converged",
}

# Gate -> statuses the transition may start from. The Worker-held states in
# between (implementing, verifying) are moved by advance too: the gate proves
# the outcome, the table proves the order.
GATE_ALLOWED_FROM: dict[str, set[str]] = {
    "intake": {"normalized"},
    "analyzed": {"normalized", "analyzing"},
    "specified": {"analyzed"},
    "decomposed": {"analyzed", "specified", "decomposed"},
    "targeting": {"decomposed", "targeting"},
    "implemented": {"target-confirmed", "implementing"},
    "converged": {"implemented", "verifying"},
}

TRANSITION_JOURNAL = "transitions.jsonl"


class TransitionError(Exception):
    """Rejected or inconsistent lifecycle transition."""


def transitions_path(product_root: Path) -> Path:
    return product_root / ".deltafuse" / TRANSITION_JOURNAL


def _load_change_yaml(change_path: Path) -> dict[str, Any]:
    file = change_path / "change.yaml"
    if not file.is_file():
        raise TransitionError(f"change.yaml missing in {change_path}")
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except Exception as ex:
        raise TransitionError(f"failed to read change.yaml: {ex}") from ex
    if not isinstance(data, dict):
        raise TransitionError("change.yaml must be a mapping")
    return data


def _write_change_status(change_path: Path, data: dict[str, Any], status: str) -> None:
    data["status"] = status
    (change_path / "change.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _receipt(entry: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_receipts(product_root: Path, change_id: str) -> list[dict[str, Any]]:
    """All recorded receipts for one Change, oldest first."""
    path = transitions_path(product_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("change") == change_id:
            out.append(row)
    return out


def last_receipt(product_root: Path, change_id: str) -> dict[str, Any] | None:
    rows = load_receipts(product_root, change_id)
    return rows[-1] if rows else None


def receipt_mismatch(product_root: Path, change_path: Path) -> str | None:
    """Non-None when change.yaml disagrees with the last recorded receipt.

    A hand-edited status without a receipt (or a crash between journal append
    and change.yaml write) shows up here.
    """
    data = _load_change_yaml(change_path)
    change_id = data.get("id") or change_path.name
    last = last_receipt(product_root, change_id)
    if last is None:
        return None
    if data.get("status") != last.get("to"):
        return (
            f"status '{data.get('status')}' does not match the last transition "
            f"receipt '{last.get('to')}' ({last.get('receipt', '')[:12]}); "
            "re-run: deltafuse advance"
        )
    return None


def resume_incomplete(product_root: Path, change_path: Path) -> dict[str, Any] | None:
    """Finish a transition whose receipt was recorded but whose change.yaml
    write never landed (crash between validation and write). Returns the
    resumed receipt entry, or None when there is nothing to resume."""
    data = _load_change_yaml(change_path)
    change_id = data.get("id") or change_path.name
    last = last_receipt(product_root, change_id)
    if last is None:
        return None
    if data.get("status") == last.get("to"):
        return None
    if data.get("status") != last.get("from"):
        return None  # hand-edited status, not a crash residue
    _write_change_status(change_path, data, last["to"])
    return last


def advance_change(
    start: Path | str,
    gate: str,
    *,
    registry: Any | None = None,
) -> dict[str, Any]:
    """Validate a gate and apply its transition atomically (Core, no LLM).

    1. Journal entry (with receipt digest) is appended first.
    2. change.yaml status is updated second; a crash in between leaves the
       receipt as the source of truth and the next ``advance`` (or
       ``resume_incomplete``) completes the write.
    """
    gate = (gate or "").strip().lower()
    if gate not in GATE_TARGETS:
        raise TransitionError(
            f"unknown gate '{gate}'; expected one of {sorted(GATE_TARGETS)}"
        )
    change_path = Path(start).resolve()
    if not change_path.is_dir():
        raise TransitionError(f"Change directory not found: {change_path}")
    product_root = find_repo_root(change_path)

    # Crash residue from a previous advance: the receipt is authoritative,
    # so finishing the pending write completes the transition.
    resumed = resume_incomplete(product_root, change_path)
    if resumed is not None:
        return {
            "ok": True,
            "gate": resumed["gate"],
            "from": resumed["from"],
            "to": resumed["to"],
            "receipt": resumed["receipt"],
            "resumed": True,
        }

    data = _load_change_yaml(change_path)
    change_id = data.get("id") or change_path.name
    current = data.get("status")
    target = GATE_TARGETS[gate]
    allowed_from = GATE_ALLOWED_FROM[gate]

    errors = check_gate(change_path, gate, registry=registry)
    if errors:
        raise TransitionError(
            f"gate '{gate}' failed: {'; '.join(errors)}"
        )
    if current not in allowed_from:
        raise TransitionError(
            f"cannot apply gate '{gate}' from status '{current}'; "
            f"allowed: {sorted(allowed_from)}"
        )
    if not can_transition(current, target) and target != current:
        raise TransitionError(
            f"transition table rejects '{current}' -> '{target}'"
        )

    entry: dict[str, Any] = {
        "kind": "transition",
        "change": change_id,
        "gate": gate,
        "from": current,
        "to": target,
        "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    entry["receipt"] = _receipt(entry)

    path = transitions_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _write_change_status(change_path, data, target)

    return {
        "ok": True,
        "gate": gate,
        "from": current,
        "to": target,
        "receipt": entry["receipt"],
        "resumed": resumed is not None,
    }
