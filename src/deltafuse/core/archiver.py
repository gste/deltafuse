"""Archival engine for DeltaFuse Change packages."""

from __future__ import annotations
import datetime
import errno
import os
import shutil
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.fsm import check_gate


class ArchivalError(Exception):
    """Raised when a Change package cannot be safely archived."""
    pass


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _move_package(cpath: Path, dest_dir: Path, product_root: Path) -> None:
    """Move the package in one step, or not at all (FL-15).

    `deltafuse archive .` run from inside the Change directory on Windows exited 2 with
    WinError 32: `shutil.move` could not rename a directory that was a process's working
    directory, fell back to copying it, and then failed to delete the source - the package
    archived, an empty `docs/changes/<id>/` left behind. The Core leaves the directory itself
    first, and renames; a rename that fails moves nothing. Only a different volume is copied.
    """
    try:
        if _inside(Path.cwd().resolve(), cpath):
            os.chdir(product_root)
    except OSError:
        pass
    try:
        os.rename(cpath, dest_dir)
    except OSError as ex:
        if ex.errno == errno.EXDEV:
            shutil.move(str(cpath), str(dest_dir))
            return
        raise ArchivalError(
            f"Cannot move {cpath} to the archive ({ex}); nothing was archived. The directory is in use: "
            "leave it in every shell and editor (a terminal whose current directory is inside it holds "
            "it on Windows) and run `deltafuse archive <change-dir>` again from the product root"
        ) from ex


def _other_active_refs(product_root: Path, archived: Path) -> set[str]:
    """Intake sources a Change still in docs/changes/ cites."""
    from deltafuse.core.context import posix_relpath

    out: set[str] = set()
    for change_file in (product_root / "docs" / "changes").glob("*/change.yaml"):
        if change_file.parent.resolve() == archived.resolve():
            continue
        try:
            data = yaml.safe_load(change_file.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 - an unreadable package cites nothing we can read
            continue
        source = data.get("source") if isinstance(data, dict) else None
        for ref in (source.get("intake_refs") if isinstance(source, dict) else None) or []:
            if isinstance(ref, str):
                out.add(posix_relpath(ref))
    return out


def archive_intake_sources(product_root: Path, change_data: dict[str, Any], archived: Path) -> list[str]:
    """Move the Change's intake sources from docs/intake/ to docs/archive/intake/ (FL-14).

    docs/workflow.md says archiving does this; nothing did, and the intake skill left the move
    to the Worker. Only a file or directory under docs/intake/ that `source.intake_refs` names is
    moved, never over an existing archive entry, and not while another active Change cites it.
    Returns the paths moved, relative to the product root.
    """
    from deltafuse.core.context import posix_relpath

    root = Path(product_root).resolve()
    intake_root = root / "docs" / "intake"
    archive_root = root / "docs" / "archive" / "intake"
    from deltafuse.core.product_layout import FUSEBACK_REPORTS

    fuseback = root / FUSEBACK_REPORTS
    source = change_data.get("source") if isinstance(change_data, dict) else None
    refs = (source.get("intake_refs") if isinstance(source, dict) else None) or []
    still_cited = _other_active_refs(root, archived)
    moved: list[str] = []
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            continue
        rel = posix_relpath(ref)
        try:
            src = (root / rel).resolve()
        except OSError:
            continue
        if src == intake_root or not _inside(src, intake_root) or not src.exists():
            continue
        if _inside(src, fuseback):
            continue  # Fuseback reads its reports where they are, cited or not (A-7)
        if src.name.lower() in {"readme.md", ".gitkeep"} or rel in still_cited:
            continue
        target = archive_root / src.relative_to(intake_root)
        if target.exists():
            continue  # archive entries are never overwritten; the source stays where it is
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(target))
        except OSError:
            continue  # the Change is archived either way; the source is still cited by it
        moved.append(src.relative_to(root).as_posix())
    return moved


def archive_change(
    change_path: Path | str,
    repo_root: Path | str | None = None,
    force: bool = False,
) -> Path:
    """Safely archives a Change package after convergence or terminal status.

    1. Requires the Change to be *at* `converged` - the receipted transition,
       not merely the gate's content - unless it holds an explicit non-converged
       terminal status (DF3-002); `force` never bypasses either check.
    2. Enforces archive immutability: fails if target archive destination already exists.
    3. Moves package to docs/archive/changes/YYYY-MM-DD-<change_id>/ in one rename.
    4. Records the archive receipt and updates status in change.yaml to 'archived'.
    5. Moves the Change's intake sources to docs/archive/intake/.
    """
    cpath = Path(change_path).resolve()
    if not cpath.is_dir():
        raise ArchivalError(f"Change directory does not exist: {cpath}")

    change_yaml_file = cpath / "change.yaml"
    if not change_yaml_file.is_file():
        raise ArchivalError(f"change.yaml missing in {cpath}")

    try:
        change_data = yaml.safe_load(change_yaml_file.read_text(encoding="utf-8"))
    except Exception as ex:
        raise ArchivalError(f"Failed to read change.yaml: {ex}")

    cid = change_data.get("id", cpath.name)
    current_status = change_data.get("status")

    # DF3-002 / F-01: a hand-set terminal status is not evidence. `converged`
    # is always re-verified against the gate; only explicit non-converged
    # terminal outcomes archive without gate replay.
    # V3-FIX-009: archive is a Core action; it refuses a Change whose status
    # is not backed by the full receipt chain - for a non-converged terminal
    # status, by the human's `decide --close` receipt (df-gates #6).
    from deltafuse.core.transitions import ARCHIVE_GATE, ARCHIVED_STATUS
    from deltafuse.core.transitions import find_repo_root as _find_repo_root
    from deltafuse.core.transitions import receipt_chain_errors as _chain_errors

    product_root = _find_repo_root(cpath)
    chain_errs = _chain_errors(product_root, cpath)
    if chain_errs:
        raise ArchivalError(
            f"Cannot archive Change '{cid}': transition chain invalid: {'; '.join(chain_errs)}"
        )

    bypass_gate = {"rejected", "duplicate", "not-reproduced", "superseded"}
    # `archived` with its receipt (the chain check above) is an archive that was interrupted
    # after its status write: only the move is left (FL-12).
    interrupted = current_status == ARCHIVED_STATUS
    if current_status not in bypass_gate and not interrupted:
        # `check_gate` proves a gate's content, not its turn: a Change whose
        # journal stops at `declaring` can still hold every artifact the
        # converged gate reads, and `archived` sits outside VALID_CHAIN_STATUSES,
        # so once the package moved nothing could ever detect the skip.
        from deltafuse.core.transitions import gate_order_errors as _order_errors

        if current_status != "converged":
            order_errs = _order_errors(cpath, "converged") or [
                f"Gate converged: not this Change's turn - status is '{current_status}', "
                "and archive applies only from 'converged' (run deltafuse advance "
                f"<change-dir> --gate converged) or an explicit terminal status "
                f"{sorted(bypass_gate)}"
            ]
            raise ArchivalError(
                f"Cannot archive Change '{cid}': {'; '.join(order_errs)}"
            )
        gate_errs = check_gate(cpath, "converged")
        if gate_errs:
            raise ArchivalError(
                f"Cannot archive Change '{cid}' with status '{current_status}': gate errors: {'; '.join(gate_errs)}"
            )

    # Determine repo_root
    if repo_root is None:
        cur = cpath.parent
        while cur != cur.parent:
            if (cur / "docs").is_dir() or (cur / ".deltafuse").is_dir():
                repo_root = cur
                break
            cur = cur.parent
        if repo_root is None:
            repo_root = cpath.parent.parent

    archive_dir = Path(repo_root) / "docs" / "archive" / "changes"
    archive_dir.mkdir(parents=True, exist_ok=True)

    today_str = datetime.date.today().isoformat()
    dest_name = f"{today_str}-{cid}"
    dest_dir = archive_dir / dest_name

    # Check archive immutability invariant (P2: NO rmtree, refuse to overwrite)
    if dest_dir.exists():
        raise ArchivalError(
            f"Archive directory already exists: '{dest_name}'. "
            "Overwriting historical archive records is strictly prohibited."
        )

    # The move comes first and is one rename: a directory that cannot be moved leaves the
    # Change exactly as it was, status included (FL-15).
    _move_package(cpath, dest_dir, Path(repo_root))

    if not interrupted:
        # Receipt first, like every Core status write, so `archived` can be told from a hand
        # edit (FL-12).
        from deltafuse.core.transitions import _write_change_status, append_receipt

        append_receipt(
            product_root,
            {
                "kind": "artifact-status",
                "change": cid,
                "artifact": "change",
                "gate": ARCHIVE_GATE,
                "from": current_status,
                "to": ARCHIVED_STATUS,
                "archive": dest_dir.relative_to(Path(repo_root).resolve()).as_posix(),
            },
        )
        _write_change_status(dest_dir, change_data, ARCHIVED_STATUS)  # atomic, like every status write

    archive_intake_sources(Path(repo_root), change_data, dest_dir)

    return dest_dir
