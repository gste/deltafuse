"""One run of the write leash: the diff since a base against the covering envelopes.

`deltafuse leash` and `deltafuse advance` share it. The leash used to be a
command the Worker chose to run (or a git hook that only fires on commit), and no
gate asked whether it had run, so an unwatched write envelope was the default
(audit F7). `advance` now runs the same check itself, before it writes the
receipt, so the answer does not depend on the Worker's habits.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Sequence

from deltafuse.core.config import config_as_of
from deltafuse.core.layout import PathRefused, product_relpath
from deltafuse.core.leash import (
    CONFIG_REL,
    ENVELOPE_BASE,
    INDEX,
    INDEX_ENV,
    LeashError,
    check_paths,
    collect_chain_envelopes,
    collect_ready_envelopes,
    config_at,
    config_guard_errors,
    git_dirty_paths,
    load_baseline,
    merge_base,
    step_base,
    verdict_leash_mode,
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
    staged: bool | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """The leash payload for `target` (a product root, or one Change directory).

    ``staged`` judges the index against HEAD - what a commit records - instead of
    the working tree; it defaults to whether the pre-commit hook set INDEX_ENV.
    ``since`` (`advance`): judge the working tree and every commit after that one
    on this line, from that commit's config (see git_dirty_paths).

    Raises `LeashError` (git could not answer) or `QueueError` (the queue could
    not be built), as the command always did.
    """
    if staged is None:
        staged = os.environ.get(INDEX_ENV) == "1"
    if staged and not base and not files:
        head = INDEX
    target = Path(target)
    only = target.resolve() if (target.resolve() / "change.yaml").is_file() else None
    root = load_product_root(target if only is None else only)
    if since and not files:
        head = None
        dirty = git_dirty_paths(root, since=since)
        base = since
    elif files:
        # FW-1: an absolute path, or one with `..`, matched no glob and so was never product code.
        try:
            dirty = list(dict.fromkeys(product_relpath(raw, root, resolve=True) for raw in files))
        except PathRefused as ex:
            raise LeashError(f"--file: {ex}") from None
    else:
        dirty = git_dirty_paths(root, base=base, head=head)
    if base and not files and not since:
        # The range is base...head: journals and records are compared with where head branched.
        base = merge_base(root, base, head)
    # df-leash #3: the tree is judged with its base's config - the mode and the code roots it
    # may not change for itself. No config at the base (no commit yet): the working tree's.
    base_config = config_at(root, base or "HEAD")
    envelope_base = ENVELOPE_BASE.set(base or "HEAD")
    try:
        with config_as_of(root, base_config) if base_config is not None else contextlib.nullcontext():
            queue = build_work_queue(target, only_change=only)
            selected = select_next(queue)
            snapshot = queue_snapshot(queue, selected=selected, product_root=root)
            envelope = snapshot.get("envelope")
            halt = snapshot.get("halt")
            # Ready envelopes name only the next step; the receipt chain adds the
            # steps already worked since the base, so a finished step's writes
            # are not judged against the step after it. A halt stops new work,
            # not the record of work done, so the chain applies either way.
            covering = collect_ready_envelopes(queue, root, halt) + collect_chain_envelopes(
                root, base=base, dirty=dirty, head=head
            )
            errors = check_paths(
                dirty,
                covering,
                baseline=load_baseline(root),
                product_root=root,
                base=base,
                head=head,
            )
    finally:
        ENVELOPE_BASE.reset(envelope_base)
    mode = verdict_leash_mode(root, base=base or "HEAD", head=head)
    if base_config is not None and CONFIG_REL in dirty:
        # Within a step a committed change of the config is the human's (the hook judged it);
        # `advance` judges the step in its starting mode and flags only an uncommitted one.
        guard_base = "HEAD" if since else (base or "HEAD")
        errors = config_guard_errors(root, base=guard_base, head=head) + errors
    return {
        "ok": not errors,
        "skipped": envelope is None and not errors,
        "mode": mode,
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
    try:
        since = step_base(product_root, change_path)
    except OSError:  # no git at all: run_leash says so below
        since = None
    mode = verdict_leash_mode(product_root, base=since or "HEAD", head=None, missing="off")
    if mode == "off":
        return None
    try:
        # df-leash #2: the whole step, its commits included - not only what is uncommitted.
        payload = run_leash(change_path, staged=False, since=since)
    except (LeashError, QueueError, OSError) as ex:
        return {"mode": mode, "checked": False, "reason": str(ex), "violations": []}
    return {"mode": mode, "checked": True, "violations": list(payload["violations"])}
