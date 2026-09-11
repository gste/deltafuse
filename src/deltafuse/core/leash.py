"""Write envelope and git-diff guard (kernel, no LLM)."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import yaml

from deltafuse.core.context import (
    DEFAULT_CHANGE_ROUTE,
    PHASE_CONTRACTS,
    load_change_route,
    matches_contract_globs,
    path_is_listed,
    phase_allowed_paths,
    phase_write_globs,
    posix_relpath,
)
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.queue import WorkItem

LEASH_MODES = frozenset({"off", "advisory", "enforce"})
DEFAULT_LEASH_MODE = "enforce"


class LeashError(Exception):
    """Product root / git / queue error before a diff can be judged."""


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, str):
            continue
        text = raw.replace("\\", "/").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def load_leash_mode(product_root: Path) -> str:
    path = product_root / ".deltafuse" / "config.yaml"
    if not path.is_file():
        return DEFAULT_LEASH_MODE
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_LEASH_MODE
    if not isinstance(data, dict):
        return DEFAULT_LEASH_MODE
    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        return DEFAULT_LEASH_MODE
    raw = workflow.get("leash")
    if raw is None:
        return DEFAULT_LEASH_MODE
    mode = str(raw).strip().lower()
    if mode in LEASH_MODES:
        return mode
    return DEFAULT_LEASH_MODE


def _task_path_lists(product_root: Path, item: WorkItem) -> tuple[list[str], list[str]]:
    if not item.task_path:
        return [], []
    path = product_root / item.task_path
    if not path.is_file():
        return [], []
    try:
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    if not isinstance(meta, dict):
        return [], []
    allowed = [row for row in (meta.get("allowed_paths") or []) if isinstance(row, str)]
    forbidden = [row for row in (meta.get("forbidden_paths") or []) if isinstance(row, str)]
    return allowed, forbidden


def _minus_forbidden(globs: list[str], forbidden: list[str]) -> list[str]:
    if not forbidden:
        return globs
    return [row for row in globs if not path_is_listed(row, forbidden)]


def _change_dir(product_root: Path, item: WorkItem) -> Path | None:
    if not item.path:
        return None
    path = product_root / item.path
    if path.is_dir():
        return path
    return None


def envelope_write_globs(item: WorkItem, product_root: Path) -> list[str]:
    step = item.step or ""
    if item.allowed_write:
        writes = list(item.allowed_write)
    elif step in PHASE_CONTRACTS:
        writes = list(phase_write_globs(step, DEFAULT_CHANGE_ROUTE))
    else:
        writes = []
    change_dir = _change_dir(product_root, item)
    route = DEFAULT_CHANGE_ROUTE
    if change_dir is not None:
        route, _ = load_change_route(change_dir)
        route = route or DEFAULT_CHANGE_ROUTE
        if not item.allowed_write:
            writes = list(phase_write_globs(step, route))
    allowed_paths, forbidden = _task_path_lists(product_root, item)
    if step in {"declare", "implement"} and allowed_paths:
        phase = phase_write_globs(step, route)
        change_side = [glob for glob in phase if glob.replace("\\", "/").startswith("docs/changes")]
        test_side = [glob for glob in phase if glob.replace("\\", "/").startswith("tests")]
        product_side = [path for path in allowed_paths if matches_contract_globs(path, phase)]
        writes = change_side + test_side + product_side
    return _unique(_minus_forbidden(writes, forbidden))


def envelope_read_globs(item: WorkItem) -> list[str]:
    if item.allowed_read:
        return _unique(list(item.allowed_read))
    if item.step:
        return _unique(phase_allowed_paths(item.step, "read"))
    return []


def build_envelope(item: WorkItem | None, product_root: Path) -> dict[str, Any] | None:
    """Write envelope for a ready Worker step. None when the Worker must not write."""
    if item is None or item.kind != "ready" or not item.step:
        return None
    return {
        "step": item.step,
        "change": item.change_id,
        "task": item.task,
        "write": envelope_write_globs(item, product_root),
        "read": envelope_read_globs(item),
    }


def path_in_envelope(rel_path: str, write_globs: list[str]) -> bool:
    return matches_contract_globs(posix_relpath(rel_path), write_globs)


def check_paths(envelope: dict[str, Any] | None, rel_paths: list[str]) -> list[str]:
    """Return violation messages. No envelope → no LS-002 judgement (orphan is LS-003)."""
    if envelope is None:
        return []
    writes = envelope.get("write")
    globs = [row for row in writes if isinstance(row, str)] if isinstance(writes, list) else []
    errors: list[str] = []
    for raw in _unique(rel_paths):
        if raw.startswith(".git/"):
            continue
        if not path_in_envelope(raw, globs):
            step = envelope.get("step") or "?"
            errors.append(f"leash: '{raw}' is outside the {step} write envelope")
    return errors


def git_dirty_paths(product_root: Path) -> list[str]:
    root = product_root.resolve()
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        err = (probe.stderr or probe.stdout or "git rev-parse failed").strip()
        raise LeashError(f"leash needs a git repository: {err}")
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        err = (tracked.stderr or tracked.stdout or "git diff failed").strip()
        raise LeashError(f"leash could not read git diff: {err}")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if untracked.returncode != 0:
        err = (untracked.stderr or untracked.stdout or "git ls-files failed").strip()
        raise LeashError(f"leash could not list untracked files: {err}")
    names = (tracked.stdout or "").splitlines() + (untracked.stdout or "").splitlines()
    out: list[str] = []
    for raw in names:
        text = raw.strip().replace("\\", "/")
        if not text:
            continue
        out.append(text)
    return _unique(out)
