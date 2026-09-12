"""Generate the immutable runtime asset bundle (DF3-005 / B-01).

Copies process/schemas, process/templates and process/skills into
src/deltafuse/assets/ and writes a manifest.json with SHA-256 per asset.
Canonical sources stay in process/**; the bundle is generated content that
ships inside the wheel and is re-verified at runtime. Run before building:

    python scripts/sync_assets.py

V3-FIX-022: `--check` is read-only. It generates the bundle into a temporary
directory, compares the manifest with the committed one and reports drift
without ever touching src/deltafuse/assets.

QF-009: `sync` is atomic. The new bundle is generated into a temporary
sibling directory, self-verified (manifest + SHA-256 per file) and only then
swapped in via renames with rollback. Any failure — generation, verification
or swap — leaves the previous bundle byte-for-byte intact; stale
`assets.next-*` / `assets.prev-*` directories from crashed runs are cleaned
at startup and never swapped in without verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "src" / "deltafuse" / "assets"
BUNDLE_ROOTS = ("schemas", "templates", "skills")
SCHEMA_VERSION = 1


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generate(target: Path) -> tuple[dict[str, str], list[str]]:
    """Generate the bundle into `target`; returns (files manifest, problems)."""
    problems: list[str] = []
    target.mkdir(parents=True, exist_ok=True)
    (target / "__init__.py").write_text(
        '"""Generated runtime asset bundle. DO NOT EDIT: run scripts/sync_assets.py."""\n',
        encoding="utf-8",
    )
    files: dict[str, str] = {}
    for root in BUNDLE_ROOTS:
        source_dir = REPO / "process" / root
        if not source_dir.is_dir():
            problems.append(f"missing process/{root}")
            continue
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            rel = path.relative_to(source_dir)
            dest = target / root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            files[f"{root}/{rel.as_posix()}"] = _hash(dest)
    return files, problems


# QF-009: module-level alias so tests can inject rename failures.
_rename = os.rename


def _cleanup_stale(parent: Path) -> None:
    """Remove temp dirs left behind by crashed runs."""
    for pattern in ("assets.next-*", "assets.prev-*"):
        for stale in parent.glob(pattern):
            shutil.rmtree(stale, ignore_errors=True)


def _verify_bundle(bundle: Path) -> None:
    """Self-check the generated bundle: manifest parses, files match hashes."""
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, digest in sorted(manifest["files"].items()):
        path = bundle / rel
        if not path.is_file():
            raise RuntimeError(f"generated bundle is missing {rel}")
        if _hash(path) != digest:
            raise RuntimeError(f"generated bundle hash mismatch: {rel}")


def _swap_in(new_dir: Path, target: Path) -> None:
    """Atomic directory swap with rollback (QF-009).

    os.replace cannot replace a non-empty directory on Windows, so the swap
    is: target -> prev, new -> target; on failure prev -> target restores the
    previous bundle byte-for-byte.
    """
    prev = target.parent / f"assets.prev-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    had_previous = target.exists()
    if had_previous:
        _rename(target, prev)
    try:
        _rename(new_dir, target)
    except Exception as ex:
        if had_previous and prev.exists():
            _rename(prev, target)  # rollback
        raise RuntimeError(f"bundle swap failed; previous bundle restored: {ex}") from ex
    if had_previous:
        shutil.rmtree(prev, ignore_errors=True)


def sync() -> list[str]:
    parent = ASSETS.parent
    _cleanup_stale(parent)
    next_dir = parent / f"assets.next-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        files, problems = _generate(next_dir)
        if problems:
            shutil.rmtree(next_dir, ignore_errors=True)
            return problems
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_by": "scripts/sync_assets.py",
            "canonical": "process/**",
            "files": files,
        }
        manifest_text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        (next_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
        _verify_bundle(next_dir)  # never swap an unverified bundle
        _swap_in(next_dir, ASSETS)
    except Exception:
        shutil.rmtree(next_dir, ignore_errors=True)  # no temp garbage
        raise
    print(f"bundle: {len(files)} assets -> {ASSETS.relative_to(REPO)}")
    return problems


def check() -> int:
    """V3-FIX-022: read-only drift check; never mutates the assets tree."""
    if not (ASSETS / "manifest.json").is_file():
        print("check: src/deltafuse/assets is missing; run sync_assets.py")
        return 1
    before = (ASSETS / "manifest.json").read_bytes()
    committed = json.loads(before.decode("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        files, problems = _generate(Path(tmp))
    if problems:
        for problem in problems:
            print(f"check: {problem}")
        return 1
    expected = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/sync_assets.py",
        "canonical": "process/**",
        "files": files,
    }
    drift = []
    for key, value in expected["files"].items():
        if committed["files"].get(key) != value:
            drift.append(key)
    for key in sorted(set(committed["files"]) - set(expected["files"])):
        drift.append(f"-{key} (stale bundle entry)")
    # b) actual packaged files vs the committed manifest
    for rel, digest in sorted(committed["files"].items()):
        path = ASSETS / rel
        if not path.is_file():
            drift.append(f"missing packaged asset: {rel}")
        elif _hash(path) != digest:
            drift.append(f"tampered packaged asset: {rel}")
    if committed.get("schema_version") != expected["schema_version"]:
        drift.append("manifest schema_version")
    if drift:
        print(f"check: bundle is stale ({len(drift)} drift); run sync_assets.py:")
        for key in drift[:20]:
            print(f"  {key}")
        return 1
    print(f"check: bundle is up to date ({len(files)} assets)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="read-only: report bundle drift without regenerating",
    )
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    sys.exit(1 if sync() else 0)
