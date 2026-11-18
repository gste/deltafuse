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
from deltafuse.core.lock import product_pin_errors
from deltafuse.core.leash import (
    LOCK_REL,
    _bytes_at,
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
    has_commit,
    hook_warning,
    load_baseline,
    load_leash_mode,
    merge_base,
    repository_layout_error,
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

    The payload is the whole answer and nothing is printed here: `warnings` (FW-13) and `note`
    (why a diff was not judged) are for the caller to show - `deltafuse leash` prints them.

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
    layout_error = repository_layout_error(root)
    if layout_error is not None:
        raise LeashError(layout_error)  # FW-2
    pin_errors = product_pin_errors(root)
    if pin_errors:
        # FW-10: the hook and the leash judged by whatever Core was running, pinned or not.
        raise LeashError("this Core is not the one the product pins: " + "; ".join(pin_errors))
    in_hook = bool(staged)
    if in_hook and not base and not files and not has_commit(root):
        # FW-15: the first commit has nothing to be judged against, and it is the commit
        # `deltafuse leash` asks for ("make an initial commit of the installed scaffold");
        # under enforce the hook refused it. Every later commit is judged against its parent.
        return {
            "ok": True, "skipped": True, "mode": load_leash_mode(root), "envelope": None, "paths": [],
            "violations": [], "warnings": [],
            "note": "first commit of this repository: nothing to judge it against",
        }
    if not in_hook and not base and not files and not since and _repository_without_commit(root):
        # O7: the same state from the command line exited 2 ("needs one commit"); there is nothing
        # to judge, and the answer says what is missing.
        return {
            "ok": True, "skipped": True, "mode": load_leash_mode(root), "envelope": None, "paths": [],
            "violations": [], "warnings": [],
            "note": "this repository has no commit yet, so there is nothing to judge a diff against; "
                    "make an initial commit of the installed scaffold (`git add -A` and `git commit`)",
        }
    if since and not files:
        head = None
        dirty = git_dirty_paths(root, since=since, ignored=True)
        base = since
    elif files:
        # FW-1: an absolute path, or one with `..`, matched no glob and so was never product code.
        try:
            dirty = list(dict.fromkeys(product_relpath(raw, root, resolve=True) for raw in files))
        except PathRefused as ex:
            raise LeashError(f"--file: {ex}") from None
    else:
        dirty = git_dirty_paths(root, base=base, head=head, ignored=True)
    if base and not files and not since:
        # The range is base...head: journals and records are compared with where head branched.
        base = merge_base(root, base, head)
    if has_commit(root) and _bytes_at(root, LOCK_REL, head=base or "HEAD") is None:
        # The commit (or range) that installs DeltaFuse: its base is a repository without it, so
        # there is no baseline for the scaffold `init` wrote - README templates, CHANGELOG.md,
        # the CI workflow, .gitignore - which the leash now judges like any file (R5). Removing
        # the pin later is refused by the lock guard, so a judged tree cannot get back here.
        return {
            "ok": True, "skipped": True, "mode": load_leash_mode(root), "envelope": None, "paths": dirty,
            "violations": [], "warnings": [],
            "note": "DeltaFuse is not installed at the base of this diff: nothing to judge it against",
        }
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
            covering = collect_ready_envelopes(queue, root, halt, head=head) + collect_chain_envelopes(
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
    # FW-13: say that commits are not judged here. Not inside the hook (it is running), and not
    # in CI, where there is no hook to install and the leash job is the judge.
    warning = None if in_hook or os.environ.get("CI") else hook_warning(root, mode)
    return {
        "ok": not errors,
        "skipped": envelope is None and not errors,
        "mode": mode,
        "envelope": envelope,
        "paths": dirty,
        "violations": errors,
        "warnings": [warning] if warning is not None else [],
    }


def _repository_without_commit(root: Path) -> bool:
    """A git repository whose HEAD is unborn (no git at all is LeashError's to say)."""
    from deltafuse.core.leash import _git

    return _git(Path(root), "rev-parse", "--git-dir").returncode == 0 and not has_commit(Path(root))


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
    mode = verdict_leash_mode(product_root, base=since or "HEAD", head=None)
    if mode == "off":
        return None
    if _repository_without_commit(product_root):
        # Not judged is not clean: advance records that it could not check.
        return {"mode": mode, "checked": False, "violations": [],
                "reason": "this repository has no commit yet, so there is nothing to judge the step against"}
    try:
        # df-leash #2: the whole step, its commits included - not only what is uncommitted.
        payload = run_leash(change_path, staged=False, since=since)
    except (LeashError, QueueError, OSError) as ex:
        return {"mode": mode, "checked": False, "reason": str(ex), "violations": []}
    return {"mode": mode, "checked": True, "violations": list(payload["violations"])}
