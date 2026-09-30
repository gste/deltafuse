"""One run of the write leash: the diff since a base against the covering envelopes.

`deltafuse leash` and `deltafuse advance` share it. The leash used to be a
command the Worker chose to run (or a git hook that only fires on commit), and no
gate asked whether it had run, so an unwatched write envelope was the default
(audit F7). `advance` now runs the same check itself, before it writes the
receipt, so the answer does not depend on the Worker's habits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from deltafuse.core.leash import (
    LeashError,
    check_paths,
    collect_chain_envelopes,
    collect_ready_envelopes,
    git_dirty_paths,
    load_baseline,
    load_leash_mode,
)
from deltafuse.core.queue import (
    QueueError,
    build_work_queue,
    load_product_root,
    queue_snapshot,
    select_next,
)


def run_leash(
    target: Path | str,
    *,
    base: str | None = None,
    head: str | None = None,
    files: Sequence[str] | None = None,
) -> dict[str, Any]:
    """The leash payload for `target` (a product root, or one Change directory).

    Raises `LeashError` (git could not answer) or `QueueError` (the queue could
    not be built), as the command always did.
    """
    target = Path(target)
    only = target.resolve() if (target.resolve() / "change.yaml").is_file() else None
    root = load_product_root(target if only is None else only)
    queue = build_work_queue(target, only_change=only)
    selected = select_next(queue)
    snapshot = queue_snapshot(queue, selected=selected, product_root=root)
    envelope = snapshot.get("envelope")
    halt = snapshot.get("halt")
    dirty = list(files) if files else git_dirty_paths(root, base=base, head=head)
    # Ready envelopes name only the next step; the receipt chain adds the
    # steps already worked since the base, so a finished step's writes
    # are not judged against the step after it. A halt stops new work,
    # not the record of work done, so the chain applies either way.
    covering = collect_ready_envelopes(queue, root, halt) + collect_chain_envelopes(
        root, base=base, dirty=dirty
    )
    errors = check_paths(
        dirty,
        covering,
        baseline=load_baseline(root),
        product_root=root,
        base=base,
        head=head,
    )
    return {
        "ok": not errors,
        "skipped": envelope is None and not errors,
        "mode": load_leash_mode(root),
        "envelope": envelope,
        "paths": dirty,
        "violations": errors,
    }


def leash_at_advance(change_path: Path, product_root: Path) -> dict[str, Any] | None:
    """What `advance` records about the write envelope; None when the leash is off.

    A product with no git, or no commit yet, cannot be judged: that is reported
    as `checked: false` with the reason rather than blocking a transition for
    something the Core cannot see (the git hook has the same limit).
    """
    mode = load_leash_mode(product_root, missing="off")
    if mode == "off":
        return None
    try:
        payload = run_leash(change_path)
    except (LeashError, QueueError, OSError) as ex:
        return {"mode": mode, "checked": False, "reason": str(ex), "violations": []}
    return {"mode": mode, "checked": True, "violations": list(payload["violations"])}
