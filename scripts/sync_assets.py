"""Generate the immutable runtime asset bundle (DF3-005 / B-01).

Copies process/schemas, process/templates and process/skills into
src/deltafuse/assets/ and writes a manifest.json with SHA-256 per asset.
Canonical sources stay in process/**; the bundle is generated content that
ships inside the wheel and is re-verified at runtime. Run before building:

    python scripts/sync_assets.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "src" / "deltafuse" / "assets"
BUNDLE_ROOTS = ("schemas", "templates", "skills")
SCHEMA_VERSION = 1


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync() -> list[str]:
    problems: list[str] = []
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    ASSETS.mkdir(parents=True)
    (ASSETS / "__init__.py").write_text(
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
            dest = ASSETS / root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            files[f"{root}/{rel.as_posix()}"] = _hash(dest)

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


if __name__ == "__main__":
    fail = sync()
    sys.exit(1 if fail else 0)
