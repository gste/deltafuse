"""Code ownership: which capabilities a Change's code touched, and whether routing named them.

q4 decision D (backlog/roadmap/q4-analyze-routing/1-DECISION.md). `routing.yaml`
is written by the Worker and every later gate checks relative to it, so a
domain routing never claimed was invisible. The catalog already declares who
owns which code (`code_roots` per capability); this module reads that map and
the Change's diff and names the capabilities the code entered without routing
naming them. Deterministic: git and the catalog, nothing else.

A path is `covered` when one of its owners is routed (primary or related),
`unrouted` when it has owners and none is routed - the defect - and `unowned`
when no capability claims it (a catalog gap, recorded, never judged).
`resolution` says how blind the check is: the share of covered paths with more
than one owner (1.0 when every capability shares one root).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.context import posix_relpath
from deltafuse.core.leash import is_exempt_path


def _root_prefix(raw: str) -> str:
    """`src/ratelimit`, `src/ratelimit/`, `src/ratelimit/**` -> `src/ratelimit/`."""
    text = posix_relpath(str(raw)).rstrip("/")
    if text.endswith("/**"):
        text = text[:-3]
    elif text.endswith("**"):
        text = text[:-2].rstrip("/")
    return text.rstrip("/") + "/" if text else ""


def capability_code_roots(product_root: Path | str) -> dict[str, list[str]]:
    """capability -> path prefixes from `docs/spec/_capabilities.yaml`."""
    from deltafuse.core.integrity import load_capability_catalog

    catalog, errors = load_capability_catalog(Path(product_root))
    if errors or not isinstance(catalog, dict):
        return {}
    out: dict[str, list[str]] = {}
    for domain, body in (catalog.get("domains") or {}).items():
        caps = body.get("capabilities") if isinstance(body, dict) else None
        for name, cap in (caps or {}).items():
            roots = cap.get("code_roots") if isinstance(cap, dict) else None
            prefixes = [_root_prefix(r) for r in roots or [] if isinstance(r, str) and r.strip()]
            if prefixes:
                out[f"{domain}.{name}"] = [p for p in prefixes if p]
    return out


def owners(path: str, roots: dict[str, list[str]]) -> frozenset[str]:
    rel = posix_relpath(path)
    return frozenset(cap for cap, prefixes in roots.items() if any(rel.startswith(p) for p in prefixes))


def routed_capabilities(change_path: Path | str) -> set[str]:
    """Primary and related capabilities over all claims of `routing.yaml`."""
    try:
        data = yaml.safe_load((Path(change_path) / "routing.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    out: set[str] = set()
    for row in (data.get("claims") or {}).values() if isinstance(data, dict) else ():
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("primary_capability"), str):
            out.add(row["primary_capability"])
        out.update(c for c in row.get("related_capabilities") or [] if isinstance(c, str))
    return out


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def change_code_paths(product_root: Path, change_path: Path) -> list[str] | None:
    """Code paths the Change touched, or None without git history to tell.

    The base is the first commit that holds the Change's `change.yaml`: code
    changed after the Change existed is the Change's. Before that commit
    exists, the diff since HEAD is.
    """
    root = Path(product_root)
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        return None
    rel = Path(change_path).resolve().relative_to(root.resolve()).as_posix() + "/change.yaml"
    log = _git(root, "log", "--format=%H", "--diff-filter=A", "--", rel)
    commits = [line for line in (log.stdout or "").splitlines() if line.strip()]
    base = commits[-1] if commits else "HEAD"
    diff = _git(root, "diff", "--name-only", base)
    if diff.returncode != 0:
        return None
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    paths = set((diff.stdout or "").splitlines()) | set((untracked.stdout or "").splitlines())
    # Not CODE_WRITE_GLOBS: a service repository keeps code in
    # `document-service/...` (bench case J03), outside `src/**`.
    return sorted(
        p for p in (posix_relpath(x) for x in paths if x.strip())
        if not is_exempt_path(p)
        and not p.startswith(("tests/", "docs/", "."))
    )


def under_routing(product_root: Path | str, change_path: Path | str) -> dict[str, Any]:
    """The ownership record of a Change: what its code entered and what routing named."""
    root = Path(product_root)
    roots = capability_code_roots(root)
    paths = change_code_paths(root, Path(change_path))
    record: dict[str, Any] = {"unrouted": {}, "unowned": [], "resolution": None, "measurable": False}
    if not roots or paths is None or not paths:
        record["reason"] = (
            "catalog declares no code_roots" if not roots
            else "no git history" if paths is None
            else "no code paths touched"
        )
        return record
    routed = routed_capabilities(change_path)
    covered_owner_counts: list[int] = []
    for path in paths:
        found = owners(path, roots)
        if not found:
            record["unowned"].append(path)
        elif found & routed:
            covered_owner_counts.append(len(found))
        else:
            for cap in sorted(found):
                record["unrouted"].setdefault(cap, []).append(path)
    record["measurable"] = True
    if covered_owner_counts:
        shared = sum(1 for n in covered_owner_counts if n > 1)
        record["resolution"] = round(shared / len(covered_owner_counts), 4)
    return record
