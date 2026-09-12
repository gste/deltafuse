"""Generate the immutable runtime asset bundle (DF3-005 / B-01).

Copies process/schemas, process/templates and process/skills into
src/deltafuse/assets/ and writes a manifest.json with SHA-256 per asset.
Canonical sources stay in process/**; the bundle is generated content that
ships inside the wheel and is re-verified at runtime. Run before building:

    python scripts/sync_assets.py

V3-FIX-022: `--check` is read-only. It generates the bundle into a temporary
directory, compares the manifest with the committed one and reports drift
without ever touching src/deltafuse/assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
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


def sync() -> list[str]:
    problems: list[str] = []
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    files, problems = _generate(ASSETS)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/sync_assets.py",
        "canonical": "process/**",
        "files": files,
    }
    manifest_path = ASSETS / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(f"bundle: {len(files)} assets -> {manifest_path.relative_to(REPO)}")
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
