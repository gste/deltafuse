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

from deltafuse.core.artifact_lock import ProductMutationLock
from deltafuse.core.fsm import (
    ALLOWED_CHANGE_TRANSITIONS,
    check_gate,
    can_transition,
    find_repo_root,
)

# Gate -> target status. Human Gates (intake via decide, specified via decide
# spec) are journaled by check_gate's own human-gate replay.
GATE_TARGETS: dict[str, str] = {
    "intake": "analyzing",
    "analyzed": "analyzed",
    "specified": "specified",
    "decomposed": "decomposed",
    "declaring": "declared",
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
    "declaring": {"decomposed", "declaring"},
    "implemented": {"declared", "implementing"},
    "converged": {"implemented", "verifying"},
}

TRANSITION_JOURNAL = "transitions.jsonl"

# The only status a Change may hold without a Core receipt: the scaffolded
# entry state written by `deltafuse init` / scaffold_change.
INITIAL_STATUS = "normalized"

# Canonical chain of Core receipted transitions, in order (V3-FIX-009). A
# Change past the initial state must carry the full receipt prefix for its
# status; hand-edited statuses are never evidence.
RECEIPT_CHAIN: list[tuple[str, str]] = [
    ("intake", "analyzing"),
    ("analyzed", "analyzed"),
    ("specified", "specified"),
    ("decomposed", "decomposed"),
    ("declaring", "declared"),
    ("implemented", "implemented"),
    ("converged", "converged"),
]

# Statuses the journal must confirm explicitly: the gate targets themselves.
RECEIPTED_TARGETS = {target for _, target in RECEIPT_CHAIN}

# Statuses a Change may hold between receipts (Worker-held in-flight states);
# each must be one legal fsm step away from the last receipted status.
_INFLIGHT_STATUSES = {
    "specification-proposed",
    "declaring",
    "implementing",
    "verifying",
}

# Forward-lifecycle statuses a hand may never hold without journal coverage.
VALID_CHAIN_STATUSES = RECEIPTED_TARGETS | _INFLIGHT_STATUSES


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


def receipt_chain_errors(product_root: Path, change_path: Path) -> list[str]:
    """V3-FIX-009: fail-closed receipt chain validation.

    Replays the recorded Core transitions against the gate table starting from
    the initial state. Any status past the initial state must be reachable
    through the journal: a missing receipt, an out-of-order gate, or a status
    the journal does not reach is an error. Hand-edited statuses are never
    evidence.
    """
    if not (change_path / "change.yaml").is_file():
        return []  # package validation reports the missing change.yaml
    try:
        data = _load_change_yaml(change_path)
    except TransitionError:
        return []
    change_id = data.get("id") or change_path.name
    status = data.get("status")
    if status == INITIAL_STATUS:
        return []
    if status not in VALID_CHAIN_STATUSES:
        # Terminal and other statuses (rejected, archived, ...) are governed
        # by their own contracts, not the forward transition chain.
        return []

    all_receipts = load_receipts(product_root, change_id)
    # Auxiliary Core receipts (decide unblock) confirm the status but are not
    # part of the forward gate chain.
    receipts = [r for r in all_receipts if r.get("kind") == "transition"]
    if not all_receipts:
        return [
            f"status '{status}' requires a Core transition chain, but "
            f"transitions.jsonl has no receipts for this Change; a hand-edited "
            "status is not evidence - rewind change.yaml to 'normalized' and "
            "re-run the gates via deltafuse advance"
        ]
    if not receipts:
        return [
            f"status '{status}' requires a Core transition chain, but the "
            "journal only holds auxiliary receipts; re-run the gates via "
            "deltafuse advance"
        ]

    errors: list[str] = []
    # Replay: each receipt must apply a known gate from a status the chain
    # has actually reached (the bugfix path legally skips 'specified').
    current = INITIAL_STATUS
    for i, row in enumerate(receipts):
        gate = row.get("gate")
        target = GATE_TARGETS.get(gate or "")
        if target is None or row.get("to") != target:
            errors.append(
                f"transition {i + 1} in the journal is not a known Core gate "
                f"outcome: gate '{gate}' -> '{row.get('to')}'"
            )
            break
        allowed_from = GATE_ALLOWED_FROM.get(gate or "", set())
        if row.get("from") != current and current not in allowed_from:
            errors.append(
                f"Core transition chain is out of order at step {i + 1}: "
                f"gate '{gate}' cannot apply from the chain state "
                f"'{current}' (receipt says '{row.get('from')}')"
            )
        current = target

    if errors:
        return errors

    if status in RECEIPTED_TARGETS:
        if current != status:
            errors.append(
                f"status '{status}' does not match the Core transition chain, "
                f"which ends at '{current}'; re-run: deltafuse advance"
            )
    elif status in _INFLIGHT_STATUSES:
        if status not in ALLOWED_CHANGE_TRANSITIONS.get(current, set()) and current != status:
            errors.append(
                f"status '{status}' is not reachable from the Core transition "
                f"chain, which ends at '{current}'"
            )
    else:
        errors.append(
            f"status '{status}' is not a receipted or in-flight state and must "
            "not be set by hand"
        )
    status_receipts = [r for r in all_receipts if r.get("kind") in ("transition", "unblock")]
    if status_receipts and status_receipts[-1].get("to") not in (status, current):
        if status in RECEIPTED_TARGETS:
            errors.append(
                f"status '{status}' does not match the last transition "
                f"receipt '{status_receipts[-1].get('to')}' "
                f"({status_receipts[-1].get('receipt', '')[:12]}); re-run: deltafuse advance"
            )
    return errors


def receipt_mismatch(product_root: Path, change_path: Path) -> str | None:
    """Non-None when change.yaml disagrees with the recorded Core receipts.

    V3-FIX-009: a missing journal is only acceptable for the initial state;
    any advanced status must be backed by the full receipt chain.
    """
    errors = receipt_chain_errors(product_root, change_path)
    return "; ".join(errors) if errors else None


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

    with ProductMutationLock(product_root):
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

        # V3-FIX-009: the existing receipt chain must be intact before this gate
        # may append to it — a hand-rewound or hand-advanced status halts here.
        chain_errors = receipt_chain_errors(product_root, change_path)
        if chain_errors:
            raise TransitionError(
                f"transition chain invalid: {'; '.join(chain_errors)}"
            )

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


# V3-FIX-010: Core-owned artifact status transitions. The Worker asks the Core
# (`deltafuse state`) instead of hand-editing task/slice/Change frontmatter.
TASK_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"declaring", "declared", "blocked", "cancelled"},
    "declaring": {"declared", "blocked"},
    "declared": {"implementing", "implemented", "blocked", "cancelled"},
    "implementing": {"implemented", "blocked"},
    "implemented": {"verified", "blocked"},
}
SLICE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"specified"},
}
# Change-level in-flight statuses the Worker may request through the Core.
CHANGE_INFLIGHT_STATUSES = {"specification-proposed"}


def set_artifact_status(
    start: Path | str,
    *,
    status: str,
    task_id: str | None = None,
    slice_id: str | None = None,
    change_status: bool = False,
) -> dict[str, Any]:
    """Core-owned write of one artifact status (V3-FIX-010).

    Exactly one of task_id / slice_id / change_status selects the artifact.
    The transition must be allowed, the Change receipt chain must be intact,
    and the write is journaled like every other Core status write.
    """
    if sum(bool(x) for x in (task_id, slice_id, change_status)) != 1:
        raise TransitionError("choose exactly one of --task, --slice, or --change")
    change_path = Path(start).resolve()
    if not change_path.is_dir():
        raise TransitionError(f"Change directory not found: {change_path}")
    product_root = find_repo_root(change_path)

    with ProductMutationLock(product_root):
        chain_errors = receipt_chain_errors(product_root, change_path)
        if chain_errors:
            raise TransitionError(f"transition chain invalid: {'; '.join(chain_errors)}")

        if task_id:
            allowed = TASK_STATUS_TRANSITIONS
            file = change_path / "tasks" / f"{task_id}.md"
            if not file.is_file():
                raise TransitionError(f"task file not found: {file}")
        elif slice_id:
            allowed = SLICE_STATUS_TRANSITIONS
            file = change_path / "slices" / f"{slice_id}.md"
            if not file.is_file():
                raise TransitionError(f"slice file not found: {file}")
        else:
            allowed = None  # change-level, handled below
            file = change_path / "change.yaml"

        if file.name == "change.yaml":
            data = _load_change_yaml(change_path)
            change_id = data.get("id") or change_path.name
            current = data.get("status")
            if status not in CHANGE_INFLIGHT_STATUSES:
                raise TransitionError(
                    f"Change status '{status}' is Core-gated; use deltafuse advance"
                )
            if current not in ALLOWED_CHANGE_TRANSITIONS.get(status, set()):
                raise TransitionError(
                    f"cannot set Change status '{status}' from '{current}'"
                )
            _write_change_status(change_path, data, status)
        else:
            data = _load_change_yaml(change_path)
            change_id = data.get("id") or change_path.name
            from deltafuse.core.frontmatter import parse_frontmatter

            meta, body = parse_frontmatter(file.read_text(encoding="utf-8"))
            current = meta.get("status")
            if current not in allowed or status not in allowed[current]:
                raise TransitionError(
                    f"cannot set status '{status}' from '{current}' for {file.name}"
                )
            meta["status"] = status
            file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

        entry: dict[str, Any] = {
            "kind": "artifact-status",
            "change": change_id,
            "artifact": "change" if change_status else ("task" if task_id else "slice"),
            "artifact_id": task_id or slice_id,
            "from": current,
            "to": status,
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        entry["receipt"] = _receipt(entry)
        path = transitions_path(product_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"ok": True, "artifact": entry["artifact"], "from": current, "to": status, "receipt": entry["receipt"]}
