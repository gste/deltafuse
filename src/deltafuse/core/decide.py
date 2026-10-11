"""Apply an explicit Human Gate choice (kernel, no LLM, no auto-accept)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from deltafuse.core.artifact_lock import ProductMutationLock
from deltafuse.core.artifact_storage import atomic_create, atomic_replace
from deltafuse.core.frontmatter import FrontmatterParseError, parse_frontmatter, replace_frontmatter

from deltafuse.core.fsm import check_gate, find_repo_root
from deltafuse.core import gate_password, gate_receipts
from deltafuse.core.gate_receipts import ReceiptError, TERMINAL_STATUSES
from deltafuse.core.integrity import list_proposed_decisions_for_change
from deltafuse.core.queue import load_product_root
from deltafuse.core.transitions import TransitionError, _artifact_file, advance_change, set_artifact_status

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
    from deltafuse.core.transitions import record_change_status

    # V3-FIX-009: decide is a Core command, so its unblock transition is
    # journaled like any other Core status write - receipt first.
    record_change_status(change_dir, status="analyzing", kind="unblock", gate="decide")
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


def _check_password(product_root: Path, password_prompt: Callable[[], str] | None) -> str:
    """Ask for the Human Gate password when the product has one; before any write."""
    if not gate_password.is_enabled(product_root):
        return "none"
    if password_prompt is None:
        raise DecideError(
            "this product guards the Human Gate with a password; run `deltafuse decide` "
            "yourself in an interactive terminal"
        )
    try:
        password = password_prompt()
    except gate_password.GatePasswordError as ex:
        raise DecideError(str(ex)) from ex
    try:
        ok = gate_password.verify_password(product_root, password)
    except gate_password.GatePasswordError as ex:
        raise DecideError(str(ex)) from ex
    if not ok:
        raise DecideError("wrong Human Gate password; nothing was written")
    return "password"


def _write_with_receipt(
    product_root: Path,
    artifact: Path,
    text: str,
    **receipt: Any,
) -> None:
    """Write the verdict and its receipt together, or neither.

    The receipt hashes the written artifact, so the artifact goes first; if the
    receipt cannot be recorded, the artifact is restored. An `accepted` status
    with no receipt read as a verdict no human gave (roadmap item 1 audit).
    """
    before = artifact.read_bytes()
    atomic_replace(artifact, text.encode("utf-8"))
    try:
        gate_receipts.record_receipt(product_root, artifact=artifact, **receipt)
    except (ReceiptError, OSError) as ex:
        atomic_replace(artifact, before)
        raise DecideError(f"Human Gate receipt was not recorded, verdict undone: {ex}") from ex


def cancel_task(
    change_dir: Path,
    task: str,
    *,
    password_prompt: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """The human cancels a task: what it promised is dropped from the Change.

    The Worker cannot (`deltafuse state` refuses `cancelled`); a task it cannot do it marks
    `blocked`, and this is one of the human's answers to that halt.
    """
    if not (change_dir / "change.yaml").is_file():
        raise DecideError("--task requires a Change directory (path to change.yaml)")
    product_root = find_repo_root(change_dir)
    human_check = _check_password(product_root, password_prompt)
    try:
        moved = set_artifact_status(change_dir, status="cancelled", task_id=task, human=True)
    except TransitionError as ex:
        raise DecideError(str(ex)) from ex
    task_file, task_id = _artifact_file(change_dir / "tasks", task, "task")
    rel = _rel(product_root, task_file)
    if not moved.get("unchanged"):
        with ProductMutationLock(product_root):
            try:
                gate_receipts.record_receipt(
                    product_root,
                    kind="task",
                    status="cancelled",
                    rel_path=rel,
                    artifact_id=task_id,
                    change=_change_id_from_dir(change_dir),
                    artifact=task_file,
                    human_check=human_check,
                )
            except (ReceiptError, OSError) as ex:
                raise DecideError(f"task cancelled, but its Human Gate receipt was not recorded: {ex}") from ex
    return {
        "ok": True,
        "gate": "task",
        "status": "cancelled",
        "human_check": human_check,
        "task": task_id,
        "from": moved.get("from"),
        "written": [rel],
        "change_status": None,
        "gate_errors": [],
    }


REOPEN_NOTE_MAX = 4000
EVIDENCE_PHASES = ("red", "green", "regression")


def reopened_dir(change_dir: Path) -> Path:
    """Where reopening archives a task's evidence: outside `evidence/`, which holds live records."""
    return change_dir / "reopened"


def latest_reopen(change_dir: Path, task_id: str) -> dict[str, Any] | None:
    """The newest archive of a reopened task, with its `path` relative to the Change, or None."""
    root = reopened_dir(change_dir)
    if not root.is_dir():
        return None
    runs = []
    for entry in root.glob(f"{task_id}.*"):
        suffix = entry.name[len(task_id) + 1 :]
        if entry.is_dir() and suffix.isdigit():
            runs.append((int(suffix), entry))
    if not runs:
        return None
    _, newest = max(runs)
    try:
        data = yaml.safe_load((newest / "reopen.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        data = None
    info = dict(data) if isinstance(data, dict) else {}
    info["path"] = newest.relative_to(change_dir).as_posix()
    return info


def reopen_task(
    change_dir: Path,
    task: str,
    *,
    note: str | None = None,
    password_prompt: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """The human reopens a blocked task: its declared oracle was wrong, Declare runs again.

    ref-m01-352 (2026-10-08): the Worker declared a Red test no code could pass, found it in
    Implement and marked the task blocked, as the skill says. Cancelling was the only answer,
    and it dropped the task's whole promise. Reopening archives the task's evidence under
    `reopened/<task>.<n>/` (the frozen oracle goes with its Red record), returns the task to
    `pending`, and records a `reopened` receipt; the Core then lets that task, and only it,
    be declared again while its Change is past Declare. `note` is what the human passes on.
    """
    if not (change_dir / "change.yaml").is_file():
        raise DecideError("--task requires a Change directory (path to change.yaml)")
    if note is not None and len(note) > REOPEN_NOTE_MAX:
        raise DecideError(f"--note is longer than {REOPEN_NOTE_MAX} characters")
    product_root = find_repo_root(change_dir)
    task_file, task_id = _artifact_file(change_dir / "tasks", task, "task")
    meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or meta.get("status") != "blocked":
        raise DecideError(
            f"only a blocked task is reopened; {task_id} is "
            f"'{meta.get('status') if isinstance(meta, dict) else None}'"
        )
    from deltafuse.core.task_snapshot import apply_restore, restore_plan

    change_id = _change_id_from_dir(change_dir) or change_dir.name
    plan, problems = restore_plan(product_root, change_id, meta)
    if problems:
        raise DecideError("cannot reopen: " + "; ".join(problems) + "; nothing was written")
    human_check = _check_password(product_root, password_prompt)
    try:
        moved = set_artifact_status(change_dir, status="pending", task_id=task_id, human=True)
    except TransitionError as ex:
        raise DecideError(str(ex)) from ex
    rel = _rel(product_root, task_file)
    with ProductMutationLock(product_root):
        previous = latest_reopen(change_dir, task_id)
        number = 1
        if previous is not None:
            number = int(str(previous["path"]).rsplit(".", 1)[-1]) + 1
        archive = reopened_dir(change_dir) / f"{task_id}.{number}"
        archive.mkdir(parents=True, exist_ok=False)
        archived: list[str] = []
        for phase in EVIDENCE_PHASES:
            record = change_dir / "evidence" / phase / f"{task_id}.yaml"
            if record.is_file():
                record.replace(archive / f"{phase}.yaml")
                archived.append(f"{phase}.yaml")
        # The task's product files go back to the declaring gate's copies: the corrected oracle
        # must fail on code this task has not yet changed (ref-m04-363-2).
        restored = apply_restore(product_root, plan)
        info = {
            "task": task_id,
            "change": _change_id_from_dir(change_dir),
            "reopened": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "archived": archived,
            "restored": restored,
            "note": note or None,
        }
        atomic_create(
            archive / "reopen.yaml",
            yaml.safe_dump(info, sort_keys=False, allow_unicode=True).encode("utf-8"),
        )
        try:
            gate_receipts.record_receipt(
                product_root,
                kind="task",
                status="reopened",
                rel_path=rel,
                artifact_id=task_id,
                change=info["change"],
                artifact=task_file,
                human_check=human_check,
            )
        except (ReceiptError, OSError) as ex:
            raise DecideError(f"task reopened, but its Human Gate receipt was not recorded: {ex}") from ex
    return {
        "ok": True,
        "gate": "task",
        "status": "reopened",
        "human_check": human_check,
        "task": task_id,
        "from": moved.get("from"),
        "written": [rel, _rel(product_root, archive), *restored],
        "change_status": None,
        "gate_errors": [],
    }


def apply_decision(
    start: Path | str,
    *,
    status: str,
    decision: str | None = None,
    spec: bool = False,
    task: str | None = None,
    note: str | None = None,
    password_prompt: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Write the human's recorded choice. Does not run from `next`.

    `password_prompt` is called only when the product has a Human Gate password;
    it is asked before the mutation lock, so a human typing holds nothing.
    """
    if task:
        if decision or spec:
            raise DecideError("Pass exactly one of --decision, --spec or --task")
        if status == "reopened":
            return reopen_task(Path(start).resolve(), task, note=note, password_prompt=password_prompt)
        if note is not None:
            raise DecideError("--note goes only with --status reopened")
        if status != "cancelled":
            raise DecideError(f"--task takes only --status cancelled or reopened, got {status!r}")
        return cancel_task(Path(start).resolve(), task, password_prompt=password_prompt)
    if note is not None:
        raise DecideError("--note goes only with --task and --status reopened")
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
        human_check = _check_password(product_root, password_prompt)
        with ProductMutationLock(product_root):
            delta = change_dir / "spec-delta.md"
            if not delta.is_file():
                raise DecideError(f"spec-delta.md is missing in {change_dir.as_posix()}")
            change_file = change_dir / "change.yaml"
            proposed = _load_yaml_mapping(change_file).get("status") == "specification-proposed"
            if not proposed and status == "accepted":
                # Proposing is what runs the machine checks on a spec delta
                # (transitions.set_artifact_status). A Change that never proposed
                # has had nothing checked, and recording the verdict first while
                # reporting the errors afterwards wrote an `accepted` receipt and
                # exited 0 - the same case that check was added for: a format
                # error in front of the human, who can neither accept it nor fix
                # it. Rejection is deliberately not guarded: a human must always
                # be able to say no.
                pre_errors = check_gate(
                    change_dir,
                    "specified",
                    assume_status="specification-proposed",
                    human=False,
                )
                raise DecideError(
                    "this Change never reached 'specification-proposed', so there is no "
                    "proposal for the Human Gate to answer; nothing was written - the Worker "
                    "proposes with `deltafuse state <change-dir> --change --status "
                    "specification-proposed`"
                    + (
                        "; the proposal will be refused until these are fixed: "
                        + "; ".join(pre_errors)
                        if pre_errors
                        else ""
                    )
                )
            try:
                text = replace_frontmatter(delta.read_text(encoding="utf-8"), {"status": status})
            except FrontmatterParseError as ex:
                raise DecideError(f"spec-delta.md: {ex}") from ex

            written = [_rel(product_root, delta)]
            change_id = _change_id_from_dir(change_dir)
            _write_with_receipt(
                product_root,
                delta,
                text,
                kind="spec",
                status=status,
                rel_path=written[0],
                artifact_id=change_id or change_dir.name,
                change=change_id,
                human_check=human_check,
            )
            change_status = None
            if status == "rejected" and proposed:
                from deltafuse.core.transitions import record_change_status

                # The rejected proposal returns to analyzed with a receipt, like
                # every other Core status write (roadmap item 1: it was a bare
                # write of change.yaml).
                record_change_status(
                    change_dir,
                    status="analyzed",
                    kind="artifact-status",
                    gate="decide",
                    artifact="change",
                    reason="spec rejected",
                )
                change_status = "analyzed"
                written.append(_rel(product_root, change_file))

        # The accepted verdict moves the Change through advance_change, which
        # journals the transition receipt the chain replay requires. Writing
        # 'specified' into change.yaml directly left a status with no receipt:
        # every later Core command then refused the chain, and no step existed
        # to repair it. advance_change takes the mutation lock itself, and the
        # lock is not reentrant, so this runs after the block above.
        gate_errors: list[str] = []
        transition_failed = False
        if status == "accepted":
            if proposed:
                try:
                    advance_change(change_dir, "specified")
                except TransitionError as ex:
                    # The acceptance is recorded, but the Change did not move.
                    # Reporting success here left the same Human Gate showing
                    # forever; the caller must see that the click did not land.
                    gate_errors = [str(ex)]
                    transition_failed = True
                else:
                    change_status = "specified"
                    written.append(_rel(product_root, change_file))
            else:
                gate_errors = check_gate(change_dir, "specified")
        return {
            "ok": not transition_failed,
            "gate": "spec",
            "status": status,
            "human_check": human_check,
            "written": written,
            "change_status": change_status,
            "gate_errors": gate_errors,
        }

    product_root = load_product_root(start_path)
    human_check = _check_password(product_root, password_prompt)
    with ProductMutationLock(product_root):
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
        new_text = replace_frontmatter(dec_path.read_text(encoding="utf-8"), {"status": status})

        written = [_rel(product_root, dec_path)]
        dec_id = meta.get("id") if isinstance(meta.get("id"), str) else dec_path.stem
        _write_with_receipt(
            product_root,
            dec_path,
            new_text,
            kind="decision",
            status=status,
            rel_path=written[0],
            artifact_id=dec_id,
            change=change_id,
            human_check=human_check,
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
            "human_check": human_check,
            "decision": dec_id,
            "written": written,
            "change_status": change_status,
            "gate_errors": [],
        }
