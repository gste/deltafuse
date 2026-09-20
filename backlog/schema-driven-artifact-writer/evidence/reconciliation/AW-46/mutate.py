#!/usr/bin/env python3
"""AW-46 mutation driver helper: apply one named pointer-decoding mutation.

Always starts from the pristine backup so mutations never compound, and prints the
resulting sha256 so each raw log records the exact bytes under test.

Usage: python mutate.py --backup-dir DIR --variant VARIANT
  variant: none | writer-delete | writer-swapped | oracle-delete
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

WRITER_ANCHOR = '    tokens = [t.replace("~1", "/").replace("~0", "~") for t in raw_tokens]'
ORACLE_ANCHOR = '    parts = [p.replace("~1", "/").replace("~0", "~") for p in raw_parts]'
SILENT_REMOVE_ANCHOR = (
    '            raise ArtifactPatchError(f"Target key \'{target_key}\' in pointer '
    '\'{ptr}\' does not exist", code="remove_target_missing", path=ptr)'
)

TARGETS = {
    "writer": "src/deltafuse/core/artifact_patch.py",
    "oracle": "scripts/evaluate_artifact_writer.py",
}

VARIANTS = {
    "none": [],
    "writer-delete": [("writer", WRITER_ANCHOR, "    tokens = list(raw_tokens)")],
    "writer-swapped": [
        ("writer", WRITER_ANCHOR,
         '    tokens = [t.replace("~0", "~").replace("~1", "/") for t in raw_tokens]')
    ],
    "oracle-delete": [("oracle", ORACLE_ANCHOR, "    parts = list(raw_parts)")],
    "writer-silent-remove": [
        ("writer", SILENT_REMOVE_ANCHOR, "            pass  # MUTATION: skip a failed lookup")
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir", type=Path, required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    args = ap.parse_args()

    for which, target in TARGETS.items():
        src = args.backup_dir / f"{which}.pristine"
        dest = Path.cwd() / target
        dest.write_bytes(src.read_bytes())

    for which, anchor, replacement in VARIANTS[args.variant]:
        path = Path.cwd() / TARGETS[which]
        text = path.read_text(encoding="utf-8")
        if text.count(anchor) != 1:
            raise SystemExit(f"mutation anchor for {which} not found exactly once")
        path.write_text(text.replace(anchor, replacement), encoding="utf-8", newline="\n")

    for which, target in TARGETS.items():
        print(f"mutated {args.variant} {target} sha256={sha256(Path.cwd() / target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
