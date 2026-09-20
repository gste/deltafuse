#!/usr/bin/env python3
"""AW-42 final-source inventory: HEAD, dirty diff, untracked files and per-scope
byte digests for source, contracts/schemas, generated assets, templates, scripts
and tests.

Writes a JSON manifest whose own digest is recorded externally (never inside
itself), so the report cannot certify itself.

Usage:
    python inventory_source.py --repo ROOT --out FILE [--head SHA]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCOPES = {
    "runtime_src": ["src"],
    "contracts_and_schemas": ["docs/contracts", "process/schemas"],
    "generated_assets": ["src/deltafuse/assets"],
    "templates": ["process/templates"],
    "skills": ["process/skills"],
    "scripts": ["scripts"],
    "tests": ["tests"],
    "writer_docs": ["docs"],
    "backlog_records": ["backlog/schema-driven-artifact-writer"],
}
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".git", "dist", "build",
                 ".venv", "venv", ".pi"}


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(("git", *args), cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def tracked_paths(repo: Path) -> list[str]:
    return [line for line in git(repo, "ls-files", "-z").split("\0") if line]


def classify(path: str, scopes: dict[str, list[str]]) -> str:
    """Most specific prefix wins, so assets/ inside src/ is not swallowed by src/."""
    best, best_len = "other", -1
    for name, prefixes in scopes.items():
        for prefix in prefixes:
            pre = prefix.rstrip("/")
            if path == pre or path.startswith(pre + "/"):
                if len(pre) > best_len:
                    best, best_len = name, len(pre)
    return best


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def head_blobs(repo: Path) -> dict[str, str]:
    """path -> git blob id for the whole tree at HEAD, in one git call."""
    mapping: dict[str, str] = {}
    for line in git(repo, "ls-tree", "-r", "HEAD").splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            mapping[path.strip('"').replace("\\", "/")] = parts[2]
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", required=True)
    parser.add_argument("--head", default=None)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    head = args.head or git(repo, "rev-parse", "HEAD").strip()
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    version = (repo / "VERSION").read_text(encoding="utf-8").strip()
    blobs_at_head = head_blobs(repo)

    status_lines = [line for line in git(repo, "status", "--porcelain=v1").splitlines() if line]
    dirty: dict[str, str] = {}
    for line in status_lines:
        state, path = line[:2].strip(), line[3:].strip().strip('"')
        full = repo / path
        if full.is_file():
            dirty[path] = f"{state}:{hashlib.sha256(full.read_bytes()).hexdigest()}"
        elif not full.exists():
            dirty[path] = f"{state}:absent"

    untracked = [line for line in git(repo, "ls-files", "--others", "--exclude-standard",
                                      "-z").split("\0") if line]
    porcelain_untracked = [line[3:].strip().strip('"') for line in status_lines
                           if line[:2] == "??"]
    modified_tracked = [line[3:].strip().strip('"') for line in status_lines
                        if "M" in line[:2]]

    files: dict[str, dict] = {}
    for rel in tracked_paths(repo):
        rel = rel.replace("\\", "/")
        full = repo / rel
        if any(part in EXCLUDE_PARTS for part in Path(rel).parts):
            continue
        entry = {"scope": classify(rel, SCOPES), "tracked": True}
        if full.is_file():
            data = full.read_bytes()
            entry["worktree_sha256"] = hashlib.sha256(data).hexdigest()
            entry["bytes"] = len(data)
            blob = blobs_at_head.get(rel)
            entry["head_blob"] = blob
            entry["head_matches_worktree"] = blob == git_blob_sha1(data)
            entry["head_matches_worktree_after_crlf_norm"] = (
                blob == git_blob_sha1(data.replace(b"\r\n", b"\n")))
        else:
            entry["worktree_sha256"] = None
            entry["head_blob"] = blobs_at_head.get(rel)
            entry["head_matches_worktree"] = False
            entry["head_matches_worktree_after_crlf_norm"] = False
            entry["note"] = "tracked at HEAD but absent from working tree"
        files[rel] = entry

    extra: dict[str, dict] = {}
    for rel in untracked:
        full = repo / rel
        if not full.is_file() or any(part in EXCLUDE_PARTS for part in Path(rel).parts):
            continue
        data = full.read_bytes()
        extra[rel] = {"scope": classify(rel, SCOPES), "tracked": False,
                      "worktree_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}

    out_path = Path(args.out).resolve()
    out_rel = str(out_path.relative_to(repo)).replace("\\", "/") if out_path.is_relative_to(repo) \
        else str(out_path)
    # A manifest never digests itself: drop its own path before composing scopes.
    extra.pop(out_rel, None)
    manifest = {
        "card": "AW-42",
        "generated": "2026-09-20",
        "purpose": "final working-tree source inventory for acceptance reconciliation",
        "self_digest_policy": "this manifest's own path is excluded from all scope digests",
        "identity": {
            "head_commit": head,
            "branch": branch,
            "version": version,
            "porcelain_status": status_lines,
            "dirty_tracked_files": modified_tracked,
            "untracked_files": [p for p in untracked if p != out_rel],
            "porcelain_untracked_entries": porcelain_untracked,
            "dirty_digests": dirty,
            "head_is_sufficient_identity": not (modified_tracked or untracked),
            "core_autocrlf": git(repo, "config", "core.autocrlf").strip() or "unset",
            "eol_note": ("worktree digests are raw bytes; where core.autocrlf or "
                         ".gitattributes normalize EOL, head_matches_worktree is false "
                         "while head_matches_worktree_after_crlf_norm is true"),
        },
        "counts": {
            "tracked_files_included": len(files),
            "untracked_files_included": len(extra),
            "tracked_content_differs_from_head": sum(
                1 for e in files.values() if e["tracked"] and not e.get("head_matches_worktree",
                                                                        True)),
            "tracked_crlf_only_differs_from_head": sum(
                1 for e in files.values() if e["tracked"] and not e.get("head_matches_worktree",
                                                                        True)
                and e.get("head_matches_worktree_after_crlf_norm")),
        },
        "scopes": {
            name: {
                "files": sorted(p for p, e in {**files, **extra}.items()
                                if e["scope"] == name),
                "count": sum(1 for e in {**files, **extra}.values() if e["scope"] == name),
                "scope_digest": _scope_digest(sorted(
                    (p, e.get("worktree_sha256") or "absent")
                    for p, e in {**files, **extra}.items() if e["scope"] == name)),
            }
            for name in list(SCOPES) + ["other"]
        },
        "files": {**files, **extra},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"head": head, "branch": branch, "version": version,
                      "counts": manifest["counts"],
                      "dirty_tracked": modified_tracked, "untracked": untracked,
                      "scope_digests": {k: v["scope_digest"] for k, v in
                                        manifest["scopes"].items()}}, indent=2))
    return 0


def _scope_digest(rows: list[tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for path, digest in rows:
        h.update(f"{path}\0{digest}\n".encode("utf-8"))
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
