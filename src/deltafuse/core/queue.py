"""Derived work queue: next ready lifecycle step (kernel, no LLM, no extra SSOT)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.analyze import PassCursor, next_analyze_pass
from deltafuse.core.specify import next_specify_pass
from deltafuse.core.config import config_section
from deltafuse.core.frontmatter import iter_frontmatter
from deltafuse.core.fsm import check_gate, find_repo_root
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.integrity import find_unresolved_decisions_for_change, list_proposed_decisions_for_change
from deltafuse.core.transitions import receipt_mismatch, red_result, supersede_errors
from deltafuse.core.context import PHASE_CONTRACTS, posix_relpath
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


def _declare_reason(change_path: Path, rel: str, tid: str, tstatus: str) -> str:
    """Why declare is next; for a task the human reopened, what was wrong with its last oracle."""
    from deltafuse.core.decide import latest_reopen

    reopen = latest_reopen(change_path, tid)
    if reopen is None or tstatus != "pending":
        return f"Task {tid} status '{tstatus}'"
    note = str(reopen.get("note") or "").strip()
    restored = [str(p) for p in reopen.get("restored") or []]
    return (
        f"Task {tid} was blocked and the human reopened it: its declared oracle was wrong. "
        f"Its earlier evidence is archived in {rel}/{reopen['path']}/ (red.yaml names the "
        "tests Red froze)"
        + (
            f"; its product files are back as the declaring gate found them ({', '.join(restored)})"
            if restored
            else ""
        )
        + ". Declare it again: fix the oracle so the accepted specification can "
        "pass it, record Red, then set it declared"
        + (f". The human's note: {note}" if note else "")
    )
IMPLEMENT_PHASE = frozenset({"declared", "implementing"})
# Change statuses before the decomposed gate: task files may already be on
# disk, but they are Decompose's output and do not pick the step yet.
BEFORE_DECOMPOSED = frozenset({"normalized", "analyzing", "analyzed", "specified"})


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
    # Where this step's skill is installed. Named, not guessed: a Worker that
    # had only the skill's name read `docs/skills` and counted a hallucinated
    # path against itself (M01 on gemma-4-26b-a4b, 2026-09-22).
    skill_path: str | None = None

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


def _item_for_pass(step: str, *, change_id: str, path: str, cursor: PassCursor) -> WorkItem:
    """The analyze or specify step on the pass the cursor names."""
    return _item_for_step(
        step,
        change_id=change_id,
        path=path,
        reason=cursor.reason,
        **{f"{step}_pass": cursor.pass_name},
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
    rel = config_section(product_root, "paths").get("changes")
    return product_root / (rel if isinstance(rel, str) else "docs/changes")


def _consumed_intake_refs(product_root: Path) -> set[str]:
    """Intake sources some Change - active or archived - already took in."""
    roots = [changes_dir(product_root), product_root / "docs" / "archive" / "changes"]
    consumed: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for change_file in root.glob("*/change.yaml"):
            try:
                data = yaml.safe_load(change_file.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            source = data.get("source") if isinstance(data, dict) else None
            refs = source.get("intake_refs") if isinstance(source, dict) else None
            for ref in refs or []:
                if isinstance(ref, str):
                    consumed.add(posix_relpath(ref))
    return consumed


def intake_sources_pending(product_root: Path) -> bool:
    """True when docs/intake has a source no Change has taken in yet.

    README / .gitkeep never count, and neither does a source named in some
    Change's `source.intake_refs`, archived ones included. q0 run M03
    20260921T215701Z: after CHG-001 converged and was archived, its intake
    note still counted as pending, and the Worker opened CHG-002 from the same
    request - a loop only the budget would have stopped.
    """
    intake = product_root / "docs" / "intake"
    if not intake.is_dir():
        return False
    skip = {"readme.md", ".gitkeep"}
    consumed = _consumed_intake_refs(product_root)
    for path in intake.iterdir():
        if path.name.lower() in skip:
            continue
        rel = path.relative_to(product_root).as_posix()
        if rel in consumed or any(ref.startswith(rel + "/") for ref in consumed):
            continue
        if path.is_file() or path.is_dir():
            return True
    return False


def _load_tasks(change_path: Path) -> list[tuple[str, str, Path, dict[str, Any]]]:
    """(id, status, file, frontmatter) of each readable task, in task-number order."""
    found = [
        (meta["id"], meta["status"], task_file, meta)
        for task_file, meta in iter_frontmatter(change_path / "tasks")
        if isinstance(meta.get("id"), str) and isinstance(meta.get("status"), str)
    ]
    found.sort(key=lambda row: _task_sort_key(row[0]))
    return found


def _stale_task_evidence(
    product_root: Path, change_path: Path, task_ids: list[str]
) -> list[tuple[str, list[str]]]:
    """Tasks whose green/regression evidence was stamped on an older tree."""
    current = compute_product_baseline_revision(product_root)
    out: list[tuple[str, list[str]]] = []
    for tid in task_ids:
        phases: list[str] = []
        for phase in ("green", "regression"):
            ev = change_path / "evidence" / phase / f"{tid}.yaml"
            if not ev.is_file():
                continue
            try:
                data = yaml.safe_load(ev.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            recorded = data.get("base_revision") if isinstance(data, dict) else None
            if recorded and recorded != current:
                phases.append(phase)
        if phases:
            out.append((tid, phases))
    return out


def _read_change(change_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """change.yaml as a mapping with a valid id, or None and why it cannot be read as one.

    (None, None) when there is no change.yaml. Gemma 31B shakedown cls-g31s-m02
    (2026-10-04): the Worker rewrote change.yaml with write_file (front-matter
    delimiters, no `id`). The queue skipped the unreadable package, `deltafuse
    next` answered "No ready work" with nothing blocked, and the run ended as if
    the Change were done.
    """
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        return None, None
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any parse failure is the same halt
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return None, f"it is not valid YAML ({first})"
    if not isinstance(data, dict):
        return None, "it is not a YAML mapping"
    # cls-g31s3-m02: rewritten by hand as `change: <id>` with no `id` - valid YAML, so
    # the queue went on selecting analyze while every artifact write was refused.
    from deltafuse.core.artifact_write import CHANGE_ID

    cid = data.get("id")
    if not isinstance(cid, str) or not CHANGE_ID.match(cid):
        return None, f"it has no valid Change id (id: {cid!r})"
    return data, None



def _halt(
    change_id: str | None,
    path: str | None,
    reason: str,
    *,
    task: str | None = None,
    task_path: str | None = None,
    halt_kind: str = "blocked",
) -> tuple[list["WorkItem"], list["WorkItem"]]:
    """A Change that halts for the human: no ready step, one blocked item saying why."""
    return [], [
        WorkItem(
            kind="blocked", step=None, skill=None, gate=None, change_id=change_id, path=path,
            task=task, task_path=task_path, reason=reason, halt_kind=halt_kind,
        )
    ]


def _scan_change(product_root: Path, change_path: Path) -> tuple[list[WorkItem], list[WorkItem]]:
    data, problem = _read_change(change_path)
    if problem:
        rel = _rel(product_root, change_path)
        return _halt(
            change_path.name,
            rel,
            f"{rel}/change.yaml is broken: {problem}. Only the Core writes "
            "change.yaml; it was written by hand. The human restores it from "
            "version control, then `deltafuse next` resumes.",
        )
    if data is None:
        return [], []
    change_id = data["id"]
    status = data.get("status")
    if not isinstance(status, str) or status in TERMINAL_CHANGE:
        return [], []
    rel = _rel(product_root, change_path)
    mismatch = receipt_mismatch(product_root, change_path)
    if mismatch:
        # DF3-004: change.yaml must agree with the last Core receipt; a
        # hand-edited status without a receipt halts the Change.
        return _halt(change_id, rel, mismatch)
    intent = data.get("intent") if isinstance(data.get("intent"), str) else "unknown"
    unresolved = find_unresolved_decisions_for_change(change_id, product_root)
    if unresolved:
        return _halt(change_id, rel, "; ".join(unresolved), halt_kind="decision")
    if status == "specification-proposed":
        return _halt(
            change_id,
            rel,
            "Human specification gate (status specification-proposed)",
            halt_kind="spec",
        )

    tasks = _load_tasks(change_path)
    from deltafuse.core.leash import task_envelope_errors

    envelope_faults = task_envelope_errors(change_path)
    # Tasks pick the step only once the decomposed gate has passed. q0 run
    # 20260921T121031Z: task files that failed that gate (missing `change`,
    # `slice`, a bad `kind`) sent the Worker to declare, where it could not
    # fix them, and the run looped for twenty minutes.
    phase_tasks = [] if status in BEFORE_DECOMPOSED else tasks

    for tid, tstatus, tfile, meta in phase_tasks:
        if tstatus == "blocked":
            return _halt(
                change_id,
                rel,
                f"Task {tid} is blocked: it waits for the human (the Worker's reply "
                "that blocked it says why - for example a declared oracle it showed "
                "no code can pass). The human cancels it with `deltafuse decide "
                f"{rel} --task {tid} --status cancelled`, or reopens it for Declare "
                f"with `deltafuse decide {rel} --task {tid} --status reopened --note "
                '"<why>"`',
                task=tid,
                task_path=_rel(product_root, tfile),
            )
        faults = [e for e in envelope_faults if e.startswith(f"Task {tid}:")]
        if faults:
            return _halt(
                change_id,
                rel,
                "; ".join(faults),
                task=tid,
                task_path=_rel(product_root, tfile),
            )
        if tstatus in TASK_DECLARE | TASK_IMPLEMENT and red_result(change_path, tid) == "already-green":
            # The oracle passed on unchanged code: nothing to implement, and the
            # implemented gate refuses such a Red. Without this the task was selected
            # for declare again and again, and a new step's conversation no longer
            # had the evidence command's advice (cls-g31g-m02b, 2026-10-04).
            red_rel = f"{rel}/evidence/red/{tid}.yaml"
            if not supersede_errors(change_path, tid, meta):
                return [
                    _item_for_step(
                        "declare",
                        change_id=change_id,
                        path=rel,
                        task=tid,
                        task_path=_rel(product_root, tfile),
                        reason=(
                            f"Task {tid}: its Red is already-green and it changes no "
                            "requirement, so earlier work already meets it; close it with "
                            f"deltafuse state {rel} --task {tid} --status superseded "
                            "(its test stays as regression)"
                        ),
                    )
                ], []
            return _halt(
                change_id,
                rel,
                f"Task {tid}: its Red is already-green, yet it promises "
                f"requirement_delta '{meta.get('requirement_delta')}'. "
                "The human decides: cancel it (deltafuse decide "
                f"{rel} --task {tid} --status cancelled) if the behavior already "
                f"exists, or delete {red_rel} and have it declared again",
                task=tid,
                task_path=_rel(product_root, tfile),
            )
        if tstatus in TASK_DECLARE:
            return [
                _item_for_step(
                    "declare",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason=_declare_reason(change_path, rel, tid, tstatus),
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
        ahead = [(tid, s) for tid, s, *_ in tasks if s in TASK_DONE - {"cancelled", "superseded"}]
        if ahead:
            tid, tstatus = ahead[0]
            return _halt(
                change_id,
                rel,
                f"Task {tid} is '{tstatus}' while the Change is '{status}': "
                "the task ran ahead of the declaring gate",
                task=tid,
            )
        declared = [(tid, tfile) for tid, s, tfile, _ in tasks if s in TASK_IMPLEMENT]
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
                    "with advance --gate declaring",
                )
            ], []
    if tasks and status in IMPLEMENT_PHASE:
        implemented = [(tid, tfile) for tid, s, tfile, _ in tasks if s == "implemented"]
        if implemented and all(s in TASK_DONE for _, s, *_ in tasks):
            stale = _stale_task_evidence(product_root, change_path, [tid for tid, _ in implemented])
            if stale:
                # Green and regression are stamped with the spec/src tree. A
                # later task moves it, so an earlier task's evidence no longer
                # proves its oracle on the code the gate closes over.
                tid, phases = stale[0]
                tfile = dict(implemented)[tid]
                return [
                    _item_for_step(
                        "implement",
                        change_id=change_id,
                        path=rel,
                        task=tid,
                        task_path=_rel(product_root, tfile),
                        reason=(
                            f"{' and '.join(phases)} evidence of {tid} predates later changes "
                            f"to docs/spec/** or src/**; re-run it on the current tree "
                            f"(deltafuse evidence --phase {phases[0]} --task {tid}), then "
                            "close the implemented gate"
                        ),
                    )
                ], []
            tid, tfile = implemented[-1]
            return [
                _item_for_step(
                    "implement",
                    change_id=change_id,
                    path=rel,
                    task=tid,
                    task_path=_rel(product_root, tfile),
                    reason="Every task is implemented; close the implemented gate "
                    "with advance --gate implemented",
                )
            ], []

    if status in {"implemented", "verifying"}:
        from deltafuse.core.fsm import verification_gap

        gap = verification_gap(change_path)
        if gap is not None:
            # Verify recorded a gap: Verify again would only record it again (ref-m04-365-2
            # chose Verify seven times). The human answers it.
            route = (
                f"The human reopens it for Analyze with `deltafuse decide {rel} --gap {gap} "
                '--status reopened --note "<what the gap names>"`'
                if gap == "spec-gap"
                else "The Core has no route back for this gap yet; the human settles it"
            )
            return _halt(
                change_id,
                rel,
                f"Change {change_id}: Verify recorded the gap '{gap}' in verification.md, "
                f"so it does not converge and is not repaired silently. {route}",
            )

    if phase_tasks and all(tstatus in TASK_DONE for _, tstatus, *_ in phase_tasks) and status not in (
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
        return [_item_for_pass("analyze", change_id=change_id, path=rel, cursor=cursor)], []

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
        return [_item_for_pass("specify", change_id=change_id, path=rel, cursor=cursor)], []

    if status == "specified":
        return [
            _item_for_step(
                "decompose",
                change_id=change_id,
                path=rel,
                reason=(
                    "Task files are on disk but the decomposed gate has not passed; fix what "
                    "advance --gate decomposed reports, then run it again"
                    if tasks
                    else "Change is specified; next is Decompose"
                ),
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


DEFAULT_ADAPTER_ROOTS = (".agents/skills", ".cursor/skills", ".gemini/skills")


def adapter_skill_roots(product_root: Path) -> list[str]:
    """Where installed skills live, from `adapters.roots` in the product config."""
    roots = config_section(product_root, "adapters", tolerate=(OSError, yaml.YAMLError)).get("roots")
    if isinstance(roots, list) and roots:
        return [str(r) for r in roots if isinstance(r, str) and r.strip()]
    return list(DEFAULT_ADAPTER_ROOTS)


def skill_file(product_root: Path, skill: str | None) -> str | None:
    """Installed `SKILL.md` of a step, relative to the product root."""
    if not skill:
        return None
    for root in adapter_skill_roots(product_root):
        candidate = product_root / root / skill / "SKILL.md"
        if candidate.is_file():
            return candidate.relative_to(product_root).as_posix()
    return None


def _name_skill_files(queue: "WorkQueue", product_root: Path) -> None:
    cache: dict[str, str | None] = {}
    for item in [*queue.ready, *queue.blocked]:
        if item.skill and item.skill not in cache:
            cache[item.skill] = skill_file(product_root, item.skill)
        if item.skill:
            item.skill_path = cache[item.skill]


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
    _name_skill_files(queue, product_root)
    return queue


def select_next(queue: WorkQueue, step: str | None = None) -> WorkItem | None:
    ready = queue.ready
    if step:
        ready = [item for item in ready if item.step == step]
    return ready[0] if ready else None


def _choice(choice_id: str, label: str, command: str | None) -> dict[str, Any]:
    return {"id": choice_id, "label": label, "command": command}


def _human_gate_halt(
    kind: str, prompt: str, choices: list[dict[str, Any]], product_root: Path
) -> dict[str, Any]:
    """A Human Gate halt that says how the human answers it.

    Without a Human Gate password a click in the chat runs `decide`, so the halt
    is buttons. With one, `decide` reads the password only from an interactive
    terminal and refuses anything else (core/gate_password.py): a button would
    fail, so the halt says the human types the command in a terminal, marks the
    choices, and puts the commands in the prompt to copy. Optional properties of
    contract v1: a host that ignores them still runs `command` as-is and gets
    `decide`'s own refusal, which names the same thing.
    """
    from deltafuse.core import gate_password

    halt: dict[str, Any] = {"kind": kind, "prompt": prompt, "choices": choices}
    if not gate_password.is_enabled(product_root):
        halt["human_check"] = "none"
        halt["prompt"] = f"{prompt} Show them as buttons in the chat; a click runs the command."
        return halt
    runnable = [row for row in choices if row["command"]]
    for row in runnable:
        row["interactive_only"] = True
    halt["human_check"] = "password"
    halt["terminal_required"] = True
    commands = "\n".join(f"  {row['label']}: {row['command']}" for row in runnable)
    halt["prompt"] = (
        f"{prompt} This product guards the Human Gate with a password, so a button cannot answer it. "
        "Do not run these commands and do not pick one: tell the human to open a terminal at the "
        "product root, run the command of their choice and type the password there.\n" + commands
    )
    return halt


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
        return _human_gate_halt(
            "decision",
            "A Decision is a Human Gate. Present these choices and wait. Do not pick.",
            choices,
            product_root,
        )
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
        return _human_gate_halt(
            "spec",
            "Specification accept is a Human Gate. Present these choices and wait. Do not pick.",
            choices,
            product_root,
        )
    if queue.blocked:
        return {
            "kind": "blocked",
            "prompt": "Work is blocked. Stop and inspect. Do not auto-accept Decisions or merge.",
            "choices": [_choice("inspect", "Stop and inspect", None)],
        }
    return {
        "kind": "done",
        "prompt": (
            "No ready work and no new intake file is waiting. Do not start a Change unless the "
            "human already stated one in this chat. Merge/push is a Human Gate. Do not git push."
        ),
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


def _pass_lines(item: WorkItem, *, spec_refs: bool) -> list[str]:
    """The Analyze or Specify pass a step is on, and what it names."""
    name, value = ("analyze_pass", item.analyze_pass) if item.analyze_pass else ("specify_pass", item.specify_pass)
    if not value:
        return []
    out = [f"{name}: {value}"]
    if item.capability:
        out.append(f"capability: {item.capability}")
    if item.slice_id:
        out.append(f"slice_id: {item.slice_id}")
    if spec_refs and item.spec_refs:
        out.append("spec_refs: " + ", ".join(item.spec_refs))
    return out


def format_item(item: WorkItem) -> str:
    lines = [
        f"next: /{item.skill}" if item.skill else "next: (blocked)",
        f"step: {item.step or '-'}",
        f"gate: {item.gate or '-'}",
        f"change: {item.change_id or '-'}",
        f"path: {item.path or '-'}",
        f"task: {item.task or '-'}",
        f"task_path: {item.task_path or '-'}",
        f"skill_path: {item.skill_path or '-'}",
    ]
    lines += _pass_lines(item, spec_refs=True)
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


def format_human_guide(item: WorkItem, product_root: Path | None = None) -> str:
    """Checklist from the step contract. Same Change files as llm/script; not a second process."""
    if item.kind != "ready" or not item.step or item.step not in PHASE_CONTRACTS:
        return format_human_blocked_item(item)
    from deltafuse.core.context import phase_allowed_paths

    phase = {
        "allowed_read": phase_allowed_paths(item.step, "read", product_root),
        "allowed_write": phase_allowed_paths(item.step, "write", product_root),
    }
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
        f"skill_path: {item.skill_path or '-'}",
    ]
    lines += _pass_lines(item, spec_refs=False)
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
            f"Do not run `advance --gate {gate_name}` yet. Write only this pass, then `deltafuse next`."
        )
    elif item.gate:
        close = f"`deltafuse advance {item.path or '<change-dir>'} --gate {item.gate}`"
        if item.task and item.step in {"declare", "implement"}:
            # The gate covers every task; the skill says not to check it after each one.
            close = f"Once `deltafuse next` names no other task of this Change: {close}"
        lines.append(close)
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
