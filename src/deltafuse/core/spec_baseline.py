"""What Specify wrote, as the `specified` gate accepted it.

Fuse-Back, shopkit (2026-10-08): Specify changed `docs/spec/shared/general_utilities.md` and
nobody committed between steps. Red's Core-computed `changed_paths` (the git dirty set) took the
spec file along with the test, `deltafuse evidence` said "authentic", and the `declaring` gate
refused the record as outside the Declare contract - a step later, with no way back but the
human. The bench never saw it: its runner commits after every step.

The `specified` gate records, in its transition receipt, the digest of every uncommitted
specification file it accepts. Evidence leaves a file out of a Change's `changed_paths` while its
bytes still match: Specify's output is not Declare's or Implement's change. A file changed after
acceptance no longer matches and still counts. The receipt sits in the journal the leash guards,
so the snapshot is not the Worker's to rewrite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from deltafuse.core.context import posix_relpath

SPEC_PREFIX = "docs/spec/"
DELETED = "deleted"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else DELETED


def spec_snapshot(product_root: Path) -> dict[str, str]:
    """Digests of the uncommitted files under `docs/spec/` (`deleted` for a removed one)."""
    from deltafuse.core.leash import LeashError, git_dirty_paths

    try:
        dirty = git_dirty_paths(product_root)
    except LeashError:
        return {}  # no git: nothing is uncommitted, nothing to leave out later
    out: dict[str, str] = {}
    for raw in dirty:
        rel = posix_relpath(raw)
        if rel.startswith(SPEC_PREFIX):
            out[rel] = _digest(product_root / rel)
    return dict(sorted(out.items()))


def accepted_spec_snapshot(product_root: Path, change_id: str) -> dict[str, str]:
    """The snapshot of the Change's latest `specified` transition, or nothing."""
    from deltafuse.core.transitions import latest_transition_field

    snapshot = latest_transition_field(product_root, change_id, "specified", "spec_snapshot")
    return dict(snapshot) if isinstance(snapshot, dict) else {}


def unchanged_since_specified(product_root: Path, change_id: str) -> set[str]:
    """Specification files Specify left uncommitted and nobody has touched since acceptance."""
    out: set[str] = set()
    for rel, digest in accepted_spec_snapshot(product_root, change_id).items():
        if isinstance(rel, str) and _digest(product_root / rel) == digest:
            out.add(posix_relpath(rel))
    return out
