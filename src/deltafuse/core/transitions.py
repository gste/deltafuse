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


def append_receipt(product_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """The single writer of transitions.jsonl: stamp the digest, append a line.

    `advance`, `state` and `decide` each carried their own copy of this; one
    writer keeps the receipt format in one place (roadmap item 1).
    """
    entry = dict(entry)
    entry.setdefault("recorded", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    entry["receipt"] = _receipt(entry)
    path = transitions_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def record_change_status(
    change_path: Path | str, *, status: str, kind: str, gate: str, **extra: Any
) -> dict[str, Any]:
    """A Core status write outside `advance` - decide's unblock, a rejected spec.

    The receipt is appended first and change.yaml written second, the order
    `advance` uses: a crash in between leaves the receipt as the source of
    truth. decide's unblock wrote the status first and the receipt after, so a
    crash there left a status no receipt backed. The caller holds the product
    mutation lock.
    """
    change_path = Path(change_path)
    product_root = find_repo_root(change_path)
    data = _load_change_yaml(change_path)
    entry = append_receipt(
        product_root,
        {
            "kind": kind,
            "change": data.get("id") or change_path.name,
            "gate": gate,
            "from": data.get("status"),
            "to": status,
            **extra,
        },
    )
    _write_change_status(change_path, data, status)
    return entry


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


# The human sends a Change whose Verify recorded a gap back to Analyze (`deltafuse decide
# <change> --gap spec-gap --status reopened`); the chain replays it as a rewind.
GAP_REOPEN_KIND = "gap-reopen"
GAP_REOPEN_FROM = frozenset({"implemented", "verifying"})
GAP_REOPEN_TO = "analyzing"


def open_gap_reopen(product_root: Path, change_id: str, *, until_gate: str) -> dict[str, Any] | None:
    """The Change's latest gap reopen, unless a `until_gate` transition has followed it."""
    rows = load_receipts(product_root, change_id)
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("kind") == GAP_REOPEN_KIND:
            later = rows[index + 1 :]
            if any(r.get("kind") == "transition" and r.get("gate") == until_gate for r in later):
                return None
            return rows[index]
    return None


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
    replay = [r for r in all_receipts if r.get("kind") in ("transition", GAP_REOPEN_KIND)]
    for i, row in enumerate(replay):
        if row.get("kind") == GAP_REOPEN_KIND:
            if current not in GAP_REOPEN_FROM or row.get("to") != GAP_REOPEN_TO:
                errors.append(
                    f"gap reopen at step {i + 1} rewinds from '{current}' to '{row.get('to')}'; "
                    f"only {sorted(GAP_REOPEN_FROM)} -> '{GAP_REOPEN_TO}' is a Core rewind"
                )
                break
            current = GAP_REOPEN_TO
            continue
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
    status_receipts = [
        r for r in all_receipts if r.get("kind") in ("transition", "unblock", GAP_REOPEN_KIND)
    ]
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
    # Only a gate transition can be crash residue of `advance`. q0 run
    # 20260921T130115Z: the last receipt was `state` moving a task from
    # 'declared' to 'implemented' while the Change was 'declared'; the
    # matching 'from' was read as an unfinished advance, the Change was
    # written 'implemented' with no gate, and advance crashed on the missing
    # 'gate' key - the Worker then chased the traceback's source path.
    transitions = [
        row for row in load_receipts(product_root, change_id) if row.get("kind") == "transition"
    ]
    last = transitions[-1] if transitions else None
    if last is None:
        return None
    if data.get("status") == last.get("to"):
        return None
    if data.get("status") != last.get("from"):
        return None  # hand-edited status, not a crash residue
    _write_change_status(change_path, data, last["to"])
    return last


# Gates that read coverage.yaml. The Core derives it from routing, slices,
# tasks and evidence, so it refreshes it itself before judging: a missing or
# stale mapping was a gate the Worker could only fix by running a Core command
# it had to remember (roadmap item 4: box B -> box A).
# `implemented` too: coverage.yaml carries the per-task evidence summary Verify reads.
COVERAGE_GATES = frozenset({"analyzed", "implemented", "converged"})


def _refresh_coverage(change_path: Path) -> None:
    from deltafuse.core.analyze import CoverageError, write_coverage

    if not (change_path / "routing.yaml").is_file():
        return
    try:
        write_coverage(change_path)
    except CoverageError:
        pass  # the gate names what is missing (a slice, a claim)


def _record_trace_warnings(change_path: Path) -> None:
    """P12 (workflow.trace_claims: warn, default off): the Core writes its own advisory
    findings at `converged`, not the Worker - a warning printed to stderr and never
    written anywhere is one the Verify skill can silently walk past. Written (even as an
    empty list) every time the gate closes while `warn` is set, so a claim fixed since the
    last pass does not leave a stale finding on record; not written at all when off."""
    from deltafuse.core.analyze import claim_trace_warnings
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace
    from deltafuse.core.config import load_trace_claims_mode

    if load_trace_claims_mode(find_repo_root(change_path)) != "warn":
        return
    warnings = claim_trace_warnings(change_path)
    dest = change_path / "evidence" / "verification" / "trace_warnings.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump({"warnings": warnings}, sort_keys=False).encode("utf-8")
    if dest.is_file():
        atomic_replace(dest, content)
    else:
        atomic_create(dest, content)


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

    if gate in COVERAGE_GATES:
        _refresh_coverage(change_path)

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

        # The write envelope is checked here, not left to a command the Worker may
        # never run (audit F7): advisory reports, enforce refuses before any receipt.
        from deltafuse.core.leash_run import leash_at_advance

        leash = leash_at_advance(change_path, product_root)
        if leash is not None and leash["mode"] == "enforce" and leash["violations"]:
            raise TransitionError(
                f"gate '{gate}' refused by the write leash (workflow.leash: enforce): "
                + "; ".join(leash["violations"])
            )

        if gate == "converged":
            _record_trace_warnings(change_path)

        entry: dict[str, Any] = {
            "kind": "transition",
            "change": change_id,
            "gate": gate,
            "from": current,
            "to": target,
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if gate == "declaring":
            # The tasks' product files before Implement: a reopened task is declared again
            # against them (core/task_snapshot.py, ref-m04-363-2).
            from deltafuse.core.task_snapshot import record_declaring_snapshot

            snapshot = record_declaring_snapshot(product_root, change_path, change_id)
            if snapshot:
                entry["product_snapshot"] = snapshot
        if gate == "specified":
            # What Specify left uncommitted, as accepted: evidence leaves it out of later
            # changed_paths while its bytes still match (core/spec_baseline.py).
            from deltafuse.core.spec_baseline import spec_snapshot

            snapshot = spec_snapshot(product_root)
            if snapshot:
                entry["spec_snapshot"] = snapshot
        entry = append_receipt(product_root, entry)

        _write_change_status(change_path, data, target)

        result = {
            "ok": True,
            "gate": gate,
            "from": current,
            "to": target,
            "receipt": entry["receipt"],
            "resumed": resumed is not None,
        }
        if leash is not None:
            result["leash"] = leash
        return result


# V3-FIX-010: Core-owned artifact status transitions. The Worker asks the Core
# (`deltafuse state`) instead of hand-editing task/slice/Change frontmatter.
TASK_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"declaring", "declared", "blocked", "cancelled", "superseded"},
    "declaring": {"declared", "blocked", "superseded"},
    "declared": {"implementing", "implemented", "blocked", "cancelled", "superseded"},
    "implementing": {"implemented", "blocked"},
    "implemented": {"verified", "blocked"},
    # Only the human leaves `blocked` (decide --task): cancelling drops the task,
    # reopening (`pending`) sends it back to Declare with its old evidence archived.
    "blocked": {"cancelled", "pending"},
}

# Cancelling drops what a task promised, so it is the human's call: `deltafuse decide
# <change-dir> --task <id> --status cancelled`, behind the Human Gate password when the
# product has one. ref-m02-338 observation (2026-10-04): `deltafuse state` let the Worker
# cancel a pending task with no condition - a hard task could simply be dropped, and only
# the bench's hidden suite would notice.
HUMAN_TASK_STATUSES = frozenset({"cancelled"})


def human_cancel_hint(change_path: Path | str, task_id: str) -> str:
    return (
        f"cancelling a task drops what it promised, which is the human's decision: "
        f"`deltafuse decide {Path(change_path).as_posix()} --task {task_id} --status cancelled`. "
        "If the task cannot be done, mark it blocked with `deltafuse state <change-dir> --task "
        f"{task_id} --status blocked`, say why, and stop"
    )


def human_unblock_hint(change_path: Path | str, task_id: str) -> str:
    where = Path(change_path).as_posix()
    return (
        f"task {task_id} is blocked, and only the human answers that halt: "
        f"`deltafuse decide {where} --task {task_id} --status cancelled` drops it, "
        f"`deltafuse decide {where} --task {task_id} --status reopened` sends it back to "
        "Declare. Stop and report why it is blocked"
    )


def green_attempt_error(change_path: Path, product_root: Path, task_id: str) -> str | None:
    """Why the Worker may not block this task yet: no Green was tried against its Red.

    ref-v338-a-M01 (2026-10-20): the reference, reading the history of a reopened task, ran
    `deltafuse state --status blocked` "as a probe" before writing any code, and the run halted
    for the human with an oracle nobody had tried. Blocked says the declared oracle proved wrong;
    what proves it is a Green the Core recorded against that oracle, and the human reads it.
    """
    where = Path(change_path).as_posix()
    retry = (
        f"implement the product change and record Green with `deltafuse evidence {where} --phase green "
        f"--task {task_id} -- <test command>`; block only if that run shows the declared oracle itself "
        "is wrong - the Core keeps the failed Green record for the human"
    )
    evidence = Path(change_path) / "evidence"
    try:
        red = yaml.safe_load((evidence / "red" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        red = None
    if not isinstance(red, dict):
        return (
            f"task {task_id} cannot be marked blocked: it has no Red record, so there is no declared "
            f"oracle to be wrong. Declare it first; then {retry}"
        )
    try:
        green = yaml.safe_load((evidence / "green" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        green = None
    if isinstance(green, dict):
        from deltafuse.core.evidence import evidence_stamp_error

        if evidence_stamp_error(green, Path(product_root)) is None and str(green.get("timestamp") or "") >= str(
            red.get("timestamp") or ""
        ):
            return None
    return f"task {task_id} cannot be marked blocked before a Green attempt against the oracle Red froze: {retry}"


# Statuses of Declare that a reopened task takes again after its Change has left Declare.
REOPENED_DECLARE_STATUSES = frozenset({"declaring", "declared"})
REOPENED_CHANGE_STATUSES = frozenset({"declared", "implementing"})


def red_result(change_path: Path, task_id: str) -> str | None:
    """The `result` of a task's Red record, or None when it has none."""
    red = Path(change_path) / "evidence" / "red" / f"{task_id}.yaml"
    try:
        data = yaml.safe_load(red.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    result = data.get("result") if isinstance(data, dict) else None
    return str(result) if result else None


def supersede_errors(change_path: Path, task_id: str, meta: dict[str, Any]) -> list[str]:
    """Why a task may not become `superseded`, or nothing when it may.

    An already-green Red proves there is nothing to implement against the task's oracle:
    the implemented gate refuses it, and declare selected the task again and again (Gemma
    31B shakedown cls-g31g-m02b, 2026-10-04: a "verify the constraints" task whose
    constraints earlier tasks had already met, seven declare steps in a row, then the
    Worker hand-edited other tasks' Red records). Closing the whole Change as a no-op would
    have thrown away six tasks' work. A task that changes no requirement and whose oracle
    already passes is superseded by the work around it, and its test stays as regression
    (owner decision 2026-10-04). A task that promises a requirement delta is not: its
    oracle passing on unchanged code is a contradiction the human settles.
    """
    result = red_result(change_path, task_id)
    if result != "already-green":
        return [
            f"task {task_id} can be superseded only when its Red record is already-green "
            f"(found: {result or 'no Red record'}); declare it first"
        ]
    delta = str(meta.get("requirement_delta") or "").strip().lower()
    if delta != "none":
        return [
            f"task {task_id} promises requirement_delta '{delta or 'unset'}', yet its Red "
            "already passes on unchanged code: that is the human's to settle - cancel the "
            "task if the behavior already exists, or delete its Red record and declare it again"
        ]
    return []


def already_green_advice(change_path: Path | str, task_id: str) -> str:
    """What `deltafuse evidence` tells the Worker after recording an already-green Red.

    "Return this outcome upstream" named no command (cls-g31g-m02b, 2026-10-04).
    """
    from deltafuse.core.frontmatter import parse_frontmatter

    change_dir = Path(change_path)
    try:
        meta, _ = parse_frontmatter((change_dir / "tasks" / f"{task_id}.md").read_text(encoding="utf-8"))
    except Exception:  # an unreadable task file only loses the specific advice
        meta = {}
    if not supersede_errors(change_dir, task_id, meta if isinstance(meta, dict) else {}):
        advice = (
            "The task changes no requirement, so earlier work already meets it: close it with "
            f"`deltafuse state {change_path} --task {task_id} --status superseded`; its test "
            "stays as regression."
        )
    else:
        advice = (
            "The task promises a requirement delta, so a passing oracle on unchanged code is "
            "for the human to settle: stop and report it."
        )
    return (
        "Red is already-green: the oracle passed on unchanged product code, so there is "
        f"nothing to implement against it. {advice} Do not proceed to Implement on this Red."
    )
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
    human: bool = False,
) -> dict[str, Any]:
    """Core-owned write of one artifact status (V3-FIX-010).

    Exactly one of task_id / slice_id / change_status selects the artifact.
    The transition must be allowed, the Change receipt chain must be intact,
    and the write is journaled like every other Core status write. `human` is set
    only by `deltafuse decide`, after the Human Gate check: it alone may cancel a task.
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
            # The table maps from -> to. Reading it backwards let a Change
            # go back to `specification-proposed` from `specified`, reopening
            # a Human Gate the human had already answered (found 2026-09-23).
            if status not in ALLOWED_CHANGE_TRANSITIONS.get(str(current), set()):
                raise TransitionError(
                    f"cannot set Change status '{status}' from '{current}'"
                )
            if status == "specification-proposed":
                # Proposing hands the spec to the Human Gate. A spec delta that
                # fails the machine checks is the Worker's to fix: letting it
                # through put a format error in front of the human, who can
                # neither accept it (the gate still fails) nor fix it, and the
                # run died on specify. Everything the Worker can fix must pass
                # first; the errors go back to the Worker. `human=False` also
                # leaves out a capability still in `draft`, which is the human's
                # to accept together with the specification - requiring it here
                # deadlocked specify, because `decide --spec` needs this status.
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
            if current == status:
                # Asking again for the status it already has is not an error:
                # q0 run M03 20260921T215701Z re-sent `verified` and was refused.
                # Nothing is written and no receipt is added.
                return {
                    "ok": True,
                    "artifact": "task" if task_id else "slice",
                    "from": current,
                    "to": status,
                    "receipt": None,
                    "unchanged": True,
                }
            if task_id and current == "blocked" and not human:
                raise TransitionError(human_unblock_hint(change_path, task_id))
            if task_id and status in HUMAN_TASK_STATUSES and not human:
                raise TransitionError(human_cancel_hint(change_path, task_id))
            if current not in allowed or status not in allowed[current]:
                raise TransitionError(
                    f"cannot set status '{status}' from '{current}' for {file.name}"
                )
            if task_id and status == "superseded":
                refusals = supersede_errors(change_path, task_id, meta)
                if refusals:
                    raise TransitionError("; ".join(refusals))
            if task_id and status == "blocked":
                # Gemma 31B shakedown cls-g31-m03 (2026-10-06): the Worker rewrote a frozen
                # test, Green was refused for it, and the task was then marked blocked as an
                # "oracle mismatch" - the halt read to the human as a declared oracle no code
                # can pass. Blocked is judged on the oracle as declared.
                red_file = change_path / "evidence" / "red" / f"{task_id}.yaml"
                if red_file.is_file():
                    from deltafuse.core.fsm import frozen_oracle_errors

                    changed = frozen_oracle_errors(red_file, product_root, f"Red of {task_id}")
                    if changed:
                        raise TransitionError(
                            f"task {task_id} cannot be marked blocked while its declared oracle is "
                            f"changed ({'; '.join(changed)}): restore the tests as Red froze them, "
                            "then block only if that declared oracle itself is wrong"
                        )
            if task_id and status == "blocked" and not human:
                no_attempt = green_attempt_error(change_path, product_root, task_id)
                if no_attempt:
                    raise TransitionError(no_attempt)
            if task_id and status in TASK_PHASE_CHANGE_STATUSES:
                owners, gate = TASK_PHASE_CHANGE_STATUSES[status]
                change_status_now = data.get("status")
                from deltafuse.core import gate_receipts

                if (
                    status in REOPENED_DECLARE_STATUSES
                    and change_status_now in REOPENED_CHANGE_STATUSES
                    and gate_receipts.task_reopened(product_root, change=data.get("id"), task=task_id)
                ):
                    # The human reopened this task after its oracle proved wrong
                    # (ref-m01-352): it is declared again while its siblings implement.
                    owners = owners | REOPENED_CHANGE_STATUSES
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
            # The leash accepts a structural artifact only when its last writer
            # is known: the Artifact Writer or the Core, each by the sha256 of
            # what it wrote (roadmap item 1).
            entry["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
        entry = append_receipt(product_root, entry)
        return {"ok": True, "artifact": entry["artifact"], "from": current, "to": status, "receipt": entry["receipt"]}
