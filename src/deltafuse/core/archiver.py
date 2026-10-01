"""Archival engine for DeltaFuse Change packages."""

from __future__ import annotations
import datetime
import shutil
from pathlib import Path
import yaml
from deltafuse.core.fsm import check_gate


class ArchivalError(Exception):
    """Raised when a Change package cannot be safely archived."""
    pass


def is_change_id_archived(change_id: str, repo_root: Path | str) -> bool:
    """Checks if a Change ID already exists in historical archives."""
    archive_dir = Path(repo_root) / "docs" / "archive" / "changes"
    if not archive_dir.is_dir():
        return False
    for item in archive_dir.iterdir():
        if item.is_dir():
            # Matches YYYY-MM-DD-<change_id> or exactly <change_id>
            if item.name.endswith(f"-{change_id}") or item.name == change_id:
                return True
    return False


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
    3. Updates status in change.yaml to 'archived'.
    4. Moves package to docs/archive/changes/YYYY-MM-DD-<change_id>/.
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
    # is not backed by the full receipt chain.
    from deltafuse.core.transitions import find_repo_root as _find_repo_root
    from deltafuse.core.transitions import receipt_chain_errors as _chain_errors

    chain_errs = _chain_errors(_find_repo_root(cpath), cpath)
    if chain_errs:
        raise ArchivalError(
            f"Cannot archive Change '{cid}': transition chain invalid: {'; '.join(chain_errs)}"
        )

    bypass_gate = {"rejected", "duplicate", "not-reproduced", "superseded"}
    if current_status not in bypass_gate:
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

    # Update status to archived
    from deltafuse.core.transitions import _write_change_status

    _write_change_status(cpath, change_data, "archived")  # atomic, like every status write

    # Move directory safely
    shutil.move(str(cpath), str(dest_dir))

    return dest_dir
