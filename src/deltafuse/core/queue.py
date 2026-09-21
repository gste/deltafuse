"""Derived work queue: next ready lifecycle step (kernel, no LLM, no extra SSOT)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.analyze import AnalyzeCursor, next_analyze_pass
from deltafuse.core.specify import SpecifyCursor, next_specify_pass
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import check_gate, find_repo_root
from deltafuse.core.integrity import find_unresolved_decisions_for_change, list_proposed_decisions_for_change
from deltafuse.core.transitions import receipt_mismatch
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
TASK_DECLARE = {"pending", "declaring"}
TASK_IMPLEMENT = {"declared", "implementing"}
TASK_DONE = {"implemented", "verified", "cancelled", "superseded"}
# Change statuses that own the declare / implement phase of their tasks.
DECLARE_PHASE = frozenset({"decomposed", "declaring"})
IMPLEMENT_PHASE = frozenset({"declared", "implementing"})


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
    analyze_pass: str | None = None
    specify_pass: str | None = None
    capability: str | None = None
    slice_id: str | None = None
    spec_refs: list[str] = field(default_factory=list)
    allowed_read: list[str] = field(default_factory=list)
    allowed_write: list[str] = field(default_factory=list)
    halt_kind: str | None = None
    intake_pending: bool | None = None

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
    analyze_pass: str | None = None,
    specify_pass: str | None = None,
    capability: str | None = None,
    slice_id: str | None = None,
    spec_refs: list[str] | None = None,
    allowed_read: list[str] | None = None,
    allowed_write: list[str] | None = None,
    halt_kind: str | None = None,
    intake_pending: bool | None = None,
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
        analyze_pass=analyze_pass,
        specify_pass=specify_pass,
        capability=capability,
        slice_id=slice_id,
        spec_refs=list(spec_refs or []),
        allowed_read=list(allowed_read or []),
        allowed_write=list(allowed_write or []),
        halt_kind=halt_kind,
        intake_pending=intake_pending,
    )


def _item_for_analyze(
    *,
    change_id: str,
    path: str,
    cursor: AnalyzeCursor,
) -> WorkItem:
    return _item_for_step(
        "analyze",
        change_id=change_id,
        path=path,
        reason=cursor.reason,
        analyze_pass=cursor.pass_name,
        capability=cursor.capability,
        slice_id=cursor.slice_id,
        spec_refs=cursor.spec_refs,
        allowed_read=cursor.allowed_read,
        allowed_write=cursor.allowed_write,
    )


def _item_for_specify(
    *,
    change_id: str,
    path: str,
    cursor: SpecifyCursor,
) -> WorkItem:
    return _item_for_step(
        "specify",
        change_id=change_id,
        path=path,
        reason=cursor.reason,
        specify_pass=cursor.pass_name,
        capability=cursor.capability,
        slice_id=cursor.slice_id,
        spec_refs=cursor.spec_refs,
        allowed_read=cursor.allowed_read,
        allowed_write=cursor.allowed_write,
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


def intake_sources_pending(product_root: Path) -> bool:
    """True when docs/intake has a source other than README / .gitkeep."""
    intake = product_root / "docs" / "intake"
    if not intake.is_dir():
        return False
    skip = {"readme.md", ".gitkeep"}
    for path in intake.iterdir():
        if path.name.lower() in skip:
            continue
        if path.is_file() or path.is_dir():
            return True
    return False


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
    mismatch = receipt_mismatch(product_root, change_path)
    if mismatch:
        # DF3-004: change.yaml must agree with the last Core receipt; a
        # hand-edited status without a receipt halts the Change.
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
                reason=mismatch,
                halt_kind="blocked",
            )
        ]
    intent = data.get("intent") if isinstance(data.get("intent"), str) else "unknown"
    unresolved = find_unresolved_decisions_for_change(change_id, product_root)
    if unresolved:
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
                reason="; ".join(unresolved),
                halt_kind="decision",
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
                halt_kind="spec",
            )
        ]

    tasks = _load_tasks(change_path)
    from deltafuse.core.leash import task_envelope_errors

    envelope_faults = task_envelope_errors(change_path)

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
                    halt_kind="blocked",
                )
            ]
        faults = [e for e in envelope_faults if e.startswith(f"Task {tid}:")]
        if faults:
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
                    reason="; ".join(faults),
                    halt_kind="blocked",
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
        if tstatus in TASK_IMPLEMENT and status not in DECLARE_PHASE:
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

    # The phase of the Change, not only the statuses of its tasks, picks the
    # step. Reading task statuses alone sent the Worker to implement while the
    # declaring gate was still closed, and to verify with the Change at
    # 'decomposed' (q0 run 20260921T081038Z).
    if tasks and status in DECLARE_PHASE:
        ahead = [(tid, s) for tid, s, _ in tasks if s in TASK_DONE - {"cancelled", "superseded"}]
        if ahead:
            tid, tstatus = ahead[0]
            return [], [
                WorkItem(
                    kind="blocked",
                    step=None,
                    skill=None,
                    gate=None,
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=None,
                    reason=(
                        f"Task {tid} is '{tstatus}' while the Change is '{status}': "
                        "the task ran ahead of the declaring gate"
                    ),
                    halt_kind="blocked",
                )
            ]
        declared = [(tid, tfile) for tid, s, tfile in tasks if s in TASK_IMPLEMENT]
        if declared:
            tid, tfile = declared[-1]
            return [
                _item_for_step(
                    "declare",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason="Every task is declared; close the declaring gate "
                    "(check-gate, then advance --gate declaring)",
                )
            ], []
    if tasks and status in IMPLEMENT_PHASE:
        implemented = [(tid, tfile) for tid, s, tfile in tasks if s == "implemented"]
        if implemented and all(s in TASK_DONE for _, s, _ in tasks):
            tid, tfile = implemented[-1]
            return [
                _item_for_step(
                    "implement",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason="Every task is implemented; close the implemented gate "
                    "(check-gate, then advance --gate implemented)",
                )
            ], []

    if tasks and all(tstatus in TASK_DONE for _, tstatus, _ in tasks) and status not in (
        DECLARE_PHASE | IMPLEMENT_PHASE
    ):
        return [
            _item_for_step(
                "verify",
                change_id=change_id,
                path=rel,
                reason="All tasks are terminal; Verify the Change",
            )
        ], []

    cursor = next_analyze_pass(change_path, product_root)
    if cursor is not None:
        return [_item_for_analyze(change_id=change_id, path=rel, cursor=cursor)], []

    if status in {"normalized", "analyzing"} and not check_gate(change_path, "analyzed"):
        # DF3-004: artifacts prove the gate, but only Core may stamp the
        # transition; point the Worker at the advance command.
        return [
            _item_for_step(
                "analyze",
                change_id=change_id,
                path=rel,
                reason="Gate 'analyzed' passes; confirm with: deltafuse advance <change> --gate analyzed",
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
        cursor = next_specify_pass(change_path, product_root)
        return [_item_for_specify(change_id=change_id, path=rel, cursor=cursor)], []

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
            pending = intake_sources_pending(product_root)
            queue.ready.append(
                _item_for_step(
                    "intake",
                    change_id=None,
                    path=None,
                    reason="No active Change; start /intake",
                    intake_pending=pending,
                )
            )
    return queue


def select_next(queue: WorkQueue, step: str | None = None) -> WorkItem | None:
    ready = queue.ready
    if step:
        ready = [item for item in ready if item.step == step]
    return ready[0] if ready else None


def _choice(choice_id: str, label: str, command: str | None) -> dict[str, Any]:
    return {"id": choice_id, "label": label, "command": command}


def build_halt(
    queue: WorkQueue,
    selected: WorkItem | None,
    product_root: Path,
) -> dict[str, Any] | None:
    """Structured stop for through-mode. None when the Worker should execute `selected`."""
    if selected is not None and selected.step != "intake":
        return None
    if selected is not None and selected.step == "intake":
        pending = selected.intake_pending
        if pending is None:
            pending = intake_sources_pending(product_root)
        if pending:
            return None
        return {
            "kind": "done",
            "prompt": (
                "No Worker step is ready and no new intake file is waiting. "
                "Do not start a Change unless the human already stated one in this chat. "
                "Merge/push is a Human Gate. Do not git push."
            ),
            "choices": [
                _choice("inspect", "Stop", None),
            ],
        }
    kinds = {item.halt_kind for item in queue.blocked if item.halt_kind}
    if "decision" in kinds:
        choices: list[dict[str, Any]] = []
        for item in queue.blocked:
            if item.halt_kind != "decision" or not item.change_id:
                continue
            for row in list_proposed_decisions_for_change(item.change_id, product_root):
                loc = item.path or "."
                choices.append(
                    _choice(
                        f"accept:{row['id']}",
                        f"Accept {row['id']}: {row['title']}",
                        f"deltafuse decide {loc} --decision {row['id']} --status accepted",
                    )
                )
                choices.append(
                    _choice(
                        f"reject:{row['id']}",
                        f"Reject {row['id']}: {row['title']}",
                        f"deltafuse decide {loc} --decision {row['id']} --status rejected",
                    )
                )
        choices.append(_choice("inspect", "Stop and inspect", None))
        return {
            "kind": "decision",
            "prompt": "A Decision is a Human Gate. Present these choices and wait. Do not pick.",
            "choices": choices,
        }
    if "spec" in kinds:
        choices = []
        for item in queue.blocked:
            if item.halt_kind != "spec" or not item.path:
                continue
            choices.append(
                _choice(
                    f"accept-spec:{item.change_id}",
                    f"Accept specification for {item.change_id}",
                    f"deltafuse decide {item.path} --spec --status accepted",
                )
            )
            choices.append(
                _choice(
                    f"reject-spec:{item.change_id}",
                    f"Reject specification for {item.change_id}",
                    f"deltafuse decide {item.path} --spec --status rejected",
                )
            )
        choices.append(_choice("inspect", "Stop and inspect", None))
        return {
            "kind": "spec",
            "prompt": "Specification accept is a Human Gate. Present these choices and wait. Do not pick.",
            "choices": choices,
        }
    if queue.blocked:
        return {
            "kind": "blocked",
            "prompt": "Work is blocked. Stop and inspect. Do not auto-accept Decisions or merge.",
            "choices": [_choice("inspect", "Stop and inspect", None)],
        }
    return {
        "kind": "done",
        "prompt": "No ready work. Merge/push is a Human Gate. Do not git push.",
        "choices": [_choice("inspect", "Stop", None)],
    }


def queue_snapshot(
    queue: WorkQueue,
    *,
    selected: WorkItem | None,
    product_root: Path | None = None,
) -> dict[str, Any]:
    halt = None
    envelope = None
    if product_root is not None:
        halt = build_halt(queue, selected, product_root)
        if halt is None and selected is not None:
            from deltafuse.core.leash import build_envelope

            envelope = build_envelope(selected, product_root)
    return {
        "schema_version": 1,
        "selected": selected.as_dict() if selected else None,
        "ready": [item.as_dict() for item in queue.ready],
        "blocked": [item.as_dict() for item in queue.blocked],
        "halt": halt,
        "envelope": envelope,
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
    ]
    if item.analyze_pass:
        lines.append(f"analyze_pass: {item.analyze_pass}")
        if item.capability:
            lines.append(f"capability: {item.capability}")
        if item.slice_id:
            lines.append(f"slice_id: {item.slice_id}")
        if item.spec_refs:
            lines.append("spec_refs: " + ", ".join(item.spec_refs))
    elif item.specify_pass:
        lines.append(f"specify_pass: {item.specify_pass}")
        if item.capability:
            lines.append(f"capability: {item.capability}")
        if item.slice_id:
            lines.append(f"slice_id: {item.slice_id}")
        if item.spec_refs:
            lines.append("spec_refs: " + ", ".join(item.spec_refs))
    lines.append(f"reason: {item.reason}")
    return "\n".join(lines)


def format_queue(queue: WorkQueue) -> str:
    lines: list[str] = ["Ready:"]
    if not queue.ready:
        lines.append("  (none)")
    for item in queue.ready:
        extra = f"  {item.task}" if item.task else ""
        if item.analyze_pass:
            extra += f"  {item.analyze_pass}"
            if item.capability:
                extra += f" {item.capability}"
        elif item.specify_pass:
            extra += f"  {item.specify_pass}"
            if item.slice_id:
                extra += f" {item.slice_id}"
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
    ]
    if item.analyze_pass:
        lines.append(f"analyze_pass: {item.analyze_pass}")
        if item.capability:
            lines.append(f"capability: {item.capability}")
        if item.slice_id:
            lines.append(f"slice_id: {item.slice_id}")
    elif item.specify_pass:
        lines.append(f"specify_pass: {item.specify_pass}")
        if item.capability:
            lines.append(f"capability: {item.capability}")
        if item.slice_id:
            lines.append(f"slice_id: {item.slice_id}")
    lines.extend(
        [
            f"reason: {item.reason}",
            "",
            "## Read",
        ]
    )
    read_globs = item.allowed_read or phase.get("allowed_read") or []
    for glob in read_globs:
        lines.append(f"- {glob}")
    if item.spec_refs:
        lines.append("")
        lines.append("## Spec refs (this slice)")
        for ref in item.spec_refs:
            lines.append(f"- {ref}")
    lines.append("")
    lines.append("## Write")
    write_globs = item.allowed_write or phase.get("allowed_write") or []
    for glob in write_globs:
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
    if item.analyze_pass == "coverage":
        lines.append("")
        lines.append("## Record coverage (kernel, do not hand-write YAML)")
        lines.append(f"- `deltafuse coverage {change_dir}`")
    lines.append("")
    lines.append("## Close the gate")
    if item.analyze_pass in {"routing", "slice"} or item.specify_pass == "slice":
        gate_name = "analyzed" if item.analyze_pass else "specified"
        lines.append(
            f"Do not run `check-gate --gate {gate_name}` yet. Write only this pass, then `deltafuse next`."
        )
    elif item.path and item.gate:
        lines.append(f"`deltafuse check-gate {item.path} --gate {item.gate}`")
    elif item.gate:
        lines.append(f"`deltafuse check-gate <change-dir> --gate {item.gate}`")
    lines.append("")
    lines.append("Then: `deltafuse next`")
    return "\n".join(lines)


def format_human_blocked_item(item: WorkItem) -> str:
    loc = item.path or "-"
    lines = [
        f"# Human gate  {item.change_id or ''}".rstrip(),
        "",
        "No Worker step is ready. Do not run an LLM skill.",
        "Do not auto-accept Decisions.",
        "",
        f"change: {item.change_id or '-'}",
        f"path: {loc}",
        f"task: {item.task or '-'}",
        f"kind: {item.halt_kind or 'blocked'}",
        f"reason: {item.reason}",
        "",
        "Present halt.choices from `deltafuse next --json` in the host multiple-choice UI and wait.",
        "After the human answers, run the matching `deltafuse decide` command, then `deltafuse next`.",
        "If they choose inspect, stop.",
    ]
    return "\n".join(lines)


def format_human_blocked_queue(queue: WorkQueue) -> str:
    if not queue.blocked:
        return (
            "No ready work and nothing blocked.\n"
            "Merge/push is a Human Gate. Do not git push.\n"
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
        kind = item.halt_kind or "blocked"
        parts.append(f"- {kind}  {item.change_id or '-'}{extra}  {item.path or '-'}  {item.reason}")
    parts.extend(
        [
            "",
            "Present halt.choices from `deltafuse next --json` in the host multiple-choice UI and wait.",
            "After the human answers, run `deltafuse decide`, then `deltafuse next`.",
            "If they choose inspect, stop.",
            "To start a new Change instead: /intake",
        ]
    )
    return "\n".join(parts)
