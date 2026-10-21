"""The product files of a Change's tasks as the `declaring` gate found them.

ref-m04-363-2 (2026-10-11): in Implement the reference wrote TASK-002 to the accepted spec, proved
four of its own frozen tests contradictory and blocked the task, leaving its code in
`src/ratelimit/limiter.py`. The human reopened it; the Core archived the Red but left the code,
so the corrected oracle passed on it - Red `already-green` for a task promising a delta - and the
run ended. A reopened task is declared again against the product as it was before Implement.

The `declaring` gate - every Red taken, no product code written for the tasks yet - copies each
task's product files (its `allowed_paths` outside Declare's test globs, stubs included) to
`.deltafuse/snapshots/<change>/` and records their digests in its transition receipt. Reopening a
task restores that task's files to the copies. A sibling that changed the same file loses that
change too; its evidence goes stale and the queue sends it back to Implement (owner decision
2026-10-11: honest, though it costs).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from deltafuse.core.context import matches_contract_globs, phase_write_globs, posix_relpath

ABSENT = "absent"
_CLOSED = frozenset({"cancelled", "superseded"})


def snapshot_dir(product_root: Path, change_id: str) -> Path:
    return Path(product_root) / ".deltafuse" / "snapshots" / change_id


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def task_product_paths(meta: dict[str, Any]) -> list[str]:
    """A task's product files: listed `allowed_paths` (no globs) outside Declare's test globs."""
    tests = [g for g in phase_write_globs("declare", "code") if not g.startswith("docs/")]
    out: list[str] = []
    for raw in meta.get("allowed_paths") or []:
        if not isinstance(raw, str) or any(ch in raw for ch in "*?["):
            continue
        rel = posix_relpath(raw)
        if rel and not matches_contract_globs(rel, tests):
            out.append(rel)
    return out


def _tasks(change_path: Path) -> list[dict[str, Any]]:
    from deltafuse.core.frontmatter import parse_frontmatter

    out: list[dict[str, Any]] = []
    for tf in sorted((change_path / "tasks").glob("*.md")):
        try:
            meta, _ = parse_frontmatter(tf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - an unreadable task is reported by the gate itself
            continue
        if isinstance(meta, dict) and meta.get("status") not in _CLOSED:
            out.append(meta)
    return out


def record_declaring_snapshot(product_root: Path, change_path: Path, change_id: str) -> dict[str, str]:
    """Copy every live task's product files; return {path: sha256 | 'absent'}."""
    root = Path(product_root)
    base = snapshot_dir(root, change_id)
    snapshot: dict[str, str] = {}
    for meta in _tasks(Path(change_path)):
        for rel in task_product_paths(meta):
            if rel in snapshot:
                continue
            source = root / rel
            if not source.is_file():
                snapshot[rel] = ABSENT
                continue
            data = source.read_bytes()
            copy = base / rel
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(data)
            snapshot[rel] = _digest(data)
    return dict(sorted(snapshot.items()))


def declaring_snapshot(product_root: Path, change_id: str) -> dict[str, str] | None:
    """The digests the Change's latest `declaring` transition recorded, or None."""
    from deltafuse.core.transitions import latest_transition_field

    snap = latest_transition_field(product_root, change_id, "declaring", "product_snapshot")
    return dict(snap) if isinstance(snap, dict) else None


def restore_plan(product_root: Path, change_id: str, meta: dict[str, Any]) -> tuple[list[tuple[str, bytes | None]], list[str]]:
    """What restoring a task's files would write: [(path, bytes or None to delete)], and why not.

    A copy whose bytes no longer match the receipt's digest is refused: the receipt, in the journal
    the leash guards, is the record of what the gate saw.
    """
    snap = declaring_snapshot(product_root, change_id)
    if snap is None:
        return [], []
    base = snapshot_dir(Path(product_root), change_id)
    plan: list[tuple[str, bytes | None]] = []
    problems: list[str] = []
    for rel in task_product_paths(meta):
        digest = snap.get(rel)
        if digest is None:
            continue  # not a product file at the gate (added to the task later): left as it is
        if digest == ABSENT:
            plan.append((rel, None))
            continue
        copy = base / rel
        data = copy.read_bytes() if copy.is_file() else None
        if data is None or _digest(data) != digest:
            problems.append(f"the copy of {rel} taken at the declaring gate is missing or altered ({copy})")
            continue
        plan.append((rel, data))
    return plan, problems


def apply_restore(product_root: Path, plan: list[tuple[str, bytes | None]]) -> list[str]:
    """Write the plan; return the paths whose content changed."""
    changed: list[str] = []
    for rel, data in plan:
        target = Path(product_root) / rel
        if data is None:
            if target.exists():
                target.unlink()
                changed.append(rel)
            continue
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            changed.append(rel)
    return changed
