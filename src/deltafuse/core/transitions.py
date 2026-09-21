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
    # analyzed: bug path, spec unchanged. specification-proposed: the Human
    # Gate path from docs/state-machine.md; check_gate still requires the
    # spec receipt that only `decide --spec` records.
    "specified": {"analyzed", "specification-proposed"},
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


def _gate_reachable(current: str | None, target: str) -> bool:
    """A gate closes from a resting status over the in-flight one between.

    No command writes 'declaring', 'implementing' or 'verifying' to a Change,
    so the gate from 'decomposed' to 'declared' has to step over 'declaring'
    (GATE_ALLOWED_FROM already lists 'decomposed'). q0 run 20260921T111852Z:
    `advance --gate declaring` failed on 'decomposed' -> 'declared' with every
    task declared and the gate passing - no Worker could get past it.
    """
    if can_transition(current, target):
        return True
    return any(
        can_transition(current, mid) and can_transition(mid, target)
        for mid in _INFLIGHT_STATUSES
    )


def _artifact_file(folder: Path, artifact_id: str, kind: str) -> tuple[Path, str]:
    """The task or slice file for `artifact_id`, and its canonical id.

    The decompose skill allows `TASK-NNN-<slug>.md` with frontmatter id
    `TASK-NNN`, and `deltafuse next` names tasks by that id. q0 run
    20260921T111852Z: `state --task TASK-002` was refused for
    `TASK-002-penalty-window.md` because only `<id>.md` was looked up.
    """
    from deltafuse.core.frontmatter import parse_frontmatter

    known: dict[str, list[Path]] = {}
    for candidate in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        try:
            meta, _ = parse_frontmatter(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta_id = meta.get("id") if isinstance(meta, dict) else None
        if isinstance(meta_id, str):
            known.setdefault(meta_id, []).append(candidate)
    exact = folder / f"{artifact_id}.md"
    if exact.is_file():
        canonical = next((i for i, files in known.items() if exact in files), artifact_id)
        return exact, canonical
    matches = known.get(artifact_id, [])
    if len(matches) == 1:
        return matches[0], artifact_id
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise TransitionError(f"{kind} id {artifact_id} is declared by several files: {names}")
    raise TransitionError(
        f"{kind} file not found for id {artifact_id} in {folder}; "
        f"known {kind} ids: {', '.join(sorted(known)) or 'none'}"
    )


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
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace
    data["status"] = status
    change_file = change_path / "change.yaml"
    content_bytes = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8")
    if change_file.is_file():
        atomic_replace(change_file, content_bytes)
    else:
        atomic_create(change_file, content_bytes)



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
        if target != current and not _gate_reachable(current, target):
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
# A task status belongs to a phase of its Change: it may not run ahead of the
# gates the Change has passed. Task target status -> (Change statuses that own
# that phase, the gate that opens the next one). q0 run 20260921T081038Z: both
# tasks reached 'implemented' while the Change sat at 'decomposed', and the
# queue, reading task statuses, sent the Worker to verify.
TASK_PHASE_CHANGE_STATUSES: dict[str, tuple[set[str], str]] = {
    "declaring": ({"decomposed", "declaring"}, "decomposed"),
    "declared": ({"decomposed", "declaring"}, "decomposed"),
    "implementing": ({"declared", "implementing"}, "declaring"),
    "implemented": ({"declared", "implementing"}, "declaring"),
    "verified": ({"implemented", "verifying"}, "implemented"),
}

# Rank of every forward Change status, in-flight ones between their neighbours.
_STATUS_RANK: dict[str, float] = {
    "normalized": 0,
    "analyzing": 1,
    "analyzed": 2,
    "specification-proposed": 2.5,
    "specified": 3,
    "decomposed": 4,
    "declaring": 4.5,
    "declared": 5,
    "implementing": 5.5,
    "implemented": 6,
    "verifying": 6.5,
    "converged": 7,
}


def gate_order_errors(change_path: Path | str, gate: str) -> list[str]:
    """Whether `gate` is the Change's turn, or one it already passed.

    check_gate proves a gate's content, not its turn; advance enforces the
    turn. In q0 run 20260921T081038Z the Worker ran `check-gate implemented` on
    a Change still at 'decomposed', read "passed", and advance refused it a
    second later. Statuses outside the forward chain are left to their own
    contracts.
    """
    gate = (gate or "").strip().lower()
    if gate not in GATE_TARGETS:
        return []
    try:
        current = _load_change_yaml(Path(change_path)).get("status")
    except TransitionError:
        return []
    if current in GATE_ALLOWED_FROM[gate]:
        return []
    rank_current = _STATUS_RANK.get(str(current))
    rank_target = _STATUS_RANK.get(GATE_TARGETS[gate])
    if rank_current is None or rank_target is None or rank_current >= rank_target:
        return []  # not a forward status, or the gate is already passed
    return [
        f"Gate {gate}: not this Change's turn - status is '{current}', and this gate "
        f"applies from {sorted(GATE_ALLOWED_FROM[gate])}"
    ]
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
            file, task_id = _artifact_file(change_path / "tasks", task_id, "task")
        elif slice_id:
            allowed = SLICE_STATUS_TRANSITIONS
            file, slice_id = _artifact_file(change_path / "slices", slice_id, "slice")
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
            if status == "specification-proposed":
                # Proposing hands the spec to the Human Gate. A spec delta that
                # fails the machine checks is the Worker's to fix: letting it
                # through put a format error in front of the human, who can
                # neither accept it (the gate still fails) nor fix it, and the
                # run died on specify. Everything but the human receipt must
                # pass first; the errors go back to the Worker.
                from deltafuse.core.fsm import check_gate

                gate_errors = check_gate(
                    change_path, "specified", assume_status=status, human=False
                )
                if gate_errors:
                    raise TransitionError(
                        "spec delta is not ready for the Human Gate; fix and propose again: "
                        + "; ".join(gate_errors)
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
            if task_id and status in TASK_PHASE_CHANGE_STATUSES:
                owners, gate = TASK_PHASE_CHANGE_STATUSES[status]
                change_status_now = data.get("status")
                if change_status_now not in owners:
                    raise TransitionError(
                        f"task {task_id} cannot become '{status}' while the Change is "
                        f"'{change_status_now}': a task may not run ahead of its Change "
                        f"(needs the Change in {sorted(owners)}; pass the '{gate}' gate "
                        f"first with deltafuse advance)"
                    )
            meta["status"] = status
            content_bytes = f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}".encode("utf-8")
            from deltafuse.core.artifact_storage import atomic_create, atomic_replace
            if file.is_file():
                atomic_replace(file, content_bytes)
            else:
                atomic_create(file, content_bytes)


        entry: dict[str, Any] = {
            "kind": "artifact-status",
            "change": change_id,
            "artifact": "change" if change_status else ("task" if task_id else "slice"),
            "artifact_id": task_id or slice_id,
            "from": current,
            "to": status,
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if file.name != "change.yaml":
            # The file name need not be the id (TASK-NNN-<slug>.md): the leash
            # reads the rewritten file from here, not from the id.
            entry["path"] = file.relative_to(product_root).as_posix()
        entry["receipt"] = _receipt(entry)
        path = transitions_path(product_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"ok": True, "artifact": entry["artifact"], "from": current, "to": status, "receipt": entry["receipt"]}
