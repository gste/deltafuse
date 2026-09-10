"""Derived work queue: next ready lifecycle step (kernel, no LLM, no extra SSOT)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import find_repo_root, missing_analyze_artifacts
from deltafuse.core.integrity import find_unresolved_decisions_for_change
from deltafuse.core.context import PHASE_CONTRACTS
from deltafuse.core.steps import STEP_CONTRACTS

TERMINAL_CHANGE = {
    "archived",
    "rejected",
    "duplicate",
    "superseded",
    "not-reproduced",
    "converged",
}
TASK_DECLARE = {"pending", "targeting"}
TASK_IMPLEMENT = {"target-confirmed", "implementing"}
TASK_DONE = {"implemented", "verified", "cancelled", "superseded"}


class QueueError(Exception):
    """Product root / lock missing or unreadable."""


@dataclass
class WorkItem:
    kind: str
    step: str | None
    skill: str | None
    gate: str | None
    change_id: str | None
    path: str | None
    task: str | None
    task_path: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkQueue:
    ready: list[WorkItem] = field(default_factory=list)
    blocked: list[WorkItem] = field(default_factory=list)


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _task_sort_key(task_id: str) -> tuple[int, str]:
    digits = "".join(c for c in task_id.split("-", 1)[-1] if c.isdigit())
    return (int(digits) if digits else 0, task_id)


def _item_for_step(
    step: str,
    *,
    change_id: str | None,
    path: str | None,
    reason: str,
    task: str | None = None,
    task_path: str | None = None,
    kind: str = "ready",
) -> WorkItem:
    spec = STEP_CONTRACTS[step]
    return WorkItem(
        kind=kind,
        step=step,
        skill=spec["skill"],
        gate=spec["gate"],
        change_id=change_id,
        path=path,
        task=task,
        task_path=task_path,
        reason=reason,
    )


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
        raise QueueError(f"Not a DeltaFuse product (missing {lock.as_posix()})")
    return root


def changes_dir(product_root: Path) -> Path:
    config_file = product_root / ".deltafuse" / "config.yaml"
    rel = "docs/changes"
    if config_file.is_file():
        try:
            data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except Exception:
            data = None
        if isinstance(data, dict):
            paths = data.get("paths") or {}
            if isinstance(paths, dict) and isinstance(paths.get("changes"), str):
                rel = paths["changes"]
    return product_root / rel


def _load_change(change_path: Path) -> dict[str, Any] | None:
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        return None
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_tasks(change_path: Path) -> list[tuple[str, str, Path]]:
    tasks_dir = change_path / "tasks"
    if not tasks_dir.is_dir():
        return []
    found: list[tuple[str, str, Path]] = []
    for task_file in tasks_dir.glob("*.md"):
        try:
            meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        tid = meta.get("id")
        status = meta.get("status")
        if isinstance(tid, str) and isinstance(status, str):
            found.append((tid, status, task_file))
    found.sort(key=lambda row: _task_sort_key(row[0]))
    return found


def _scan_change(product_root: Path, change_path: Path) -> tuple[list[WorkItem], list[WorkItem]]:
    data = _load_change(change_path)
    if not data:
        return [], []
    change_id = data.get("id")
    if not isinstance(change_id, str):
        change_id = change_path.name
    status = data.get("status")
    if not isinstance(status, str) or status in TERMINAL_CHANGE:
        return [], []
    rel = _rel(product_root, change_path)
    intent = data.get("intent") if isinstance(data.get("intent"), str) else "unknown"
    unresolved = find_unresolved_decisions_for_change(change_id, product_root)
    if status == "blocked-on-decision" or unresolved:
        reason = "; ".join(unresolved) if unresolved else f"Change status is '{status}'"
        return [], [
            WorkItem(
                kind="blocked",
                step=None,
                skill=None,
                gate=None,
                change_id=change_id,
                path=rel,
                task=None,
                task_path=None,
                reason=reason,
            )
        ]
    if status == "specification-proposed":
        return [], [
            WorkItem(
                kind="blocked",
                step=None,
                skill=None,
                gate=None,
                change_id=change_id,
                path=rel,
                task=None,
                task_path=None,
                reason="Human specification gate (status specification-proposed)",
            )
        ]

    tasks = _load_tasks(change_path)
    for tid, tstatus, tfile in tasks:
        if tstatus == "blocked":
            return [], [
                WorkItem(
                    kind="blocked",
                    step=None,
                    skill=None,
                    gate=None,
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason=f"Task {tid} is blocked",
                )
            ]
        if tstatus in TASK_DECLARE:
            return [
                _item_for_step(
                    "declare",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason=f"Task {tid} status '{tstatus}'",
                )
            ], []
        if tstatus in TASK_IMPLEMENT:
            return [
                _item_for_step(
                    "implement",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason=f"Task {tid} status '{tstatus}'",
                )
            ], []

    if tasks and all(tstatus in TASK_DONE for _, tstatus, _ in tasks):
        return [
            _item_for_step(
                "verify",
                change_id=change_id,
                path=rel,
                reason="All tasks are terminal; Verify the Change",
            )
        ], []

    missing = missing_analyze_artifacts(change_path)
    if status in {"normalized", "analyzing"} or missing:
        return [
            _item_for_step(
                "analyze",
                change_id=change_id,
                path=rel,
                reason="Analyze artifacts incomplete" if missing else f"Change status is '{status}'",
            )
        ], []

    if status == "analyzed":
        if intent == "bugfix":
            return [
                _item_for_step(
                    "decompose",
                    change_id=change_id,
                    path=rel,
                    reason="Bugfix may skip Specify; Decompose from accepted spec",
                )
            ], []
        return [
            _item_for_step(
                "specify",
                change_id=change_id,
                path=rel,
                reason="Change is analyzed; next is Specify",
            )
        ], []

    if status == "specified":
        return [
            _item_for_step(
                "decompose",
                change_id=change_id,
                path=rel,
                reason="Change is specified; next is Decompose",
            )
        ], []

    if status == "decomposed" and not tasks:
        return [
            _item_for_step(
                "decompose",
                change_id=change_id,
                path=rel,
                reason="Status is decomposed but no task files are on disk",
            )
        ], []

    if status in {"implemented", "verifying"}:
        return [
            _item_for_step(
                "verify",
                change_id=change_id,
                path=rel,
                reason=f"Change status is '{status}'",
            )
        ], []

    return [], []


def build_work_queue(
    start: Path | str,
    *,
    only_change: Path | None = None,
) -> WorkQueue:
    product_root = load_product_root(start)
    queue = WorkQueue()
    if only_change is not None:
        change_path = Path(only_change).resolve()
        ready, blocked = _scan_change(product_root, change_path)
        queue.ready.extend(ready)
        queue.blocked.extend(blocked)
    else:
        root_changes = changes_dir(product_root)
        packages: list[Path] = []
        if root_changes.is_dir():
            packages = sorted(
                p.parent for p in root_changes.glob("*/change.yaml")
            )
        for change_path in packages:
            ready, blocked = _scan_change(product_root, change_path)
            queue.ready.extend(ready)
            queue.blocked.extend(blocked)
        queue.ready.sort(key=lambda item: (item.change_id or "", item.task or ""))
        queue.blocked.sort(key=lambda item: (item.change_id or "", item.task or ""))
        if not queue.ready and not packages:
            queue.ready.append(
                _item_for_step(
                    "intake",
                    change_id=None,
                    path=None,
                    reason="No active Change; start /intake",
                )
            )
    return queue


def select_next(queue: WorkQueue, step: str | None = None) -> WorkItem | None:
    ready = queue.ready
    if step:
        ready = [item for item in ready if item.step == step]
    return ready[0] if ready else None


def queue_snapshot(
    queue: WorkQueue,
    *,
    selected: WorkItem | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "selected": selected.as_dict() if selected else None,
        "ready": [item.as_dict() for item in queue.ready],
        "blocked": [item.as_dict() for item in queue.blocked],
    }


def format_item(item: WorkItem) -> str:
    lines = [
        f"next: /{item.skill}" if item.skill else "next: (blocked)",
        f"step: {item.step or '-'}",
        f"gate: {item.gate or '-'}",
        f"change: {item.change_id or '-'}",
        f"path: {item.path or '-'}",
        f"task: {item.task or '-'}",
        f"task_path: {item.task_path or '-'}",
        f"reason: {item.reason}",
    ]
    return "\n".join(lines)


def format_queue(queue: WorkQueue) -> str:
    lines: list[str] = ["Ready:"]
    if not queue.ready:
        lines.append("  (none)")
    for item in queue.ready:
        extra = f"  {item.task}" if item.task else ""
        loc = item.path or "-"
        lines.append(f"  /{item.skill}  {item.change_id or '-'}{extra}  {loc}  gate={item.gate}")
    lines.append("Blocked:")
    if not queue.blocked:
        lines.append("  (none)")
    for item in queue.blocked:
        extra = f"  {item.task}" if item.task else ""
        lines.append(f"  {item.change_id or '-'}{extra}  {item.path or '-'}  {item.reason}")
    return "\n".join(lines)


_EVIDENCE_HINTS: dict[str, list[tuple[str, str]]] = {
    "declare": [("red", "Red oracle against unchanged production code")],
    "implement": [
        ("green", "target command until Green"),
        ("regression", "scoped regression for unchanged behavior"),
    ],
}


def format_human_guide(item: WorkItem) -> str:
    """Checklist from the step contract. Same Change files as llm/script; not a second process."""
    if item.kind != "ready" or not item.step or item.step not in PHASE_CONTRACTS:
        return format_human_blocked_item(item)
    phase = PHASE_CONTRACTS[item.step]
    change_dir = item.path or "<change-dir>"
    lines = [
        f"# {item.step}  {item.change_id or ''}  {item.task or ''}".rstrip(),
        "",
        "You are the Worker (human). Fill the same Change files an LLM Worker would. This is not a second process.",
        "Do not auto-accept Decisions or merge.",
        "",
        f"skill: /{item.skill}",
        f"gate: {item.gate}",
        f"change: {item.change_id or '-'}",
        f"path: {item.path or '-'}",
        f"task: {item.task or '-'}",
        f"task_path: {item.task_path or '-'}",
        f"reason: {item.reason}",
        "",
        "## Read",
    ]
    for glob in phase.get("allowed_read") or []:
        lines.append(f"- {glob}")
    lines.append("")
    lines.append("## Write")
    for glob in phase.get("allowed_write") or []:
        lines.append(f"- {glob}")
    if item.step in _EVIDENCE_HINTS:
        lines.append("")
        lines.append("## Record proof (kernel, do not hand-write YAML)")
        for ev_phase, label in _EVIDENCE_HINTS[item.step]:
            task_flag = f"--task {item.task} " if item.task else "--task <TASK-NNN> "
            lines.append(
                f"- {label}: `deltafuse evidence {change_dir} --phase {ev_phase} "
                f"{task_flag}--changed-path <rel> -- <command>`"
            )
    lines.append("")
    lines.append("## Close the gate")
    if item.path and item.gate:
        lines.append(f"`deltafuse check-gate {item.path} --gate {item.gate}`")
    elif item.gate:
        lines.append(f"`deltafuse check-gate <change-dir> --gate {item.gate}`")
    lines.append("")
    lines.append("Then: `deltafuse next`")
    return "\n".join(lines)


def format_human_blocked_item(item: WorkItem) -> str:
    loc = item.path or "-"
    return "\n".join(
        [
            f"# Human gate  {item.change_id or ''}".rstrip(),
            "",
            "No Worker step is ready. Do not run an LLM skill.",
            "Do not auto-accept Decisions.",
            "",
            f"change: {item.change_id or '-'}",
            f"path: {loc}",
            f"task: {item.task or '-'}",
            f"reason: {item.reason}",
            "",
            "Open docs/decisions/** and/or spec-delta for this Change, decide, then `deltafuse next`.",
        ]
    )


def format_human_blocked_queue(queue: WorkQueue) -> str:
    if not queue.blocked:
        return (
            "No ready work and nothing blocked.\n"
            "To start a new Change: /intake\n"
            "Then: `deltafuse next`"
        )
    parts = [
        "# Human gate",
        "",
        "No Worker step is ready. Do not run an LLM skill.",
        "Do not auto-accept Decisions.",
        "",
    ]
    for item in queue.blocked:
        extra = f"  {item.task}" if item.task else ""
        parts.append(f"- {item.change_id or '-'}{extra}  {item.path or '-'}  {item.reason}")
    parts.extend(
        [
            "",
            "Open docs/decisions/** and/or spec-delta, decide, then `deltafuse next`.",
            "To start a new Change instead: /intake",
        ]
    )
    return "\n".join(parts)
