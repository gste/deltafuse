#!/usr/bin/env python3
"""AW-46 evidence EOL normalizer.

The repository pins `* text=auto eol=lf` with core.autocrlf=true, so a CRLF file staged
here would be stored as an LF blob while its recorded sha256 was computed over the CRLF
bytes. That would make every quoted digest in the result records unverifiable after a
fresh checkout - the same checkout-normalization trap AW-42 catalogued for source files.

This script rewrites CRLF and lone-CR line endings to LF inside the evidence bundles and
records a before/after digest map, so the worktree bytes, the committed blob and the
published digests all agree.

Usage: python normalize_eol.py [--apply] [BUNDLE_DIR ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULTS = [
    Path("backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-42"),
    Path("backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-46"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundles", type=Path, nargs="*", default=DEFAULTS)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    for bundle in args.bundles:
        entries = []
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            if path.name in {"eol-normalization.json", "normalize_eol.py"} or "__pycache__" in path.parts:
                continue
            raw = path.read_bytes()
            if b"\r\n" not in raw and b"\r" not in raw:
                continue
            fixed = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            entries.append({
                "path": path.relative_to(bundle).as_posix(),
                "sha256_before_crlf": sha(raw),
                "sha256_after_lf": sha(fixed),
                "bytes_before": len(raw),
                "bytes_after": len(fixed),
            })
            if args.apply:
                path.write_bytes(fixed)
        total += len(entries)
        print(f"{bundle}: {len(entries)} files carried CRLF/CR")
        for e in entries:
            print(f"  {e['path']:62s} {e['sha256_before_crlf'][:12]} -> {e['sha256_after_lf'][:12]}")
        if entries and args.apply:
            out = bundle / "eol-normalization.json"
            out.write_text(json.dumps({
                "purpose": "CRLF -> LF normalization so recorded sha256 values survive the "
                           "repository's eol=lf checkout policy",
                "date": "2026-09-20",
                "entries": sorted(entries, key=lambda e: e["path"]),
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
            print(f"  wrote {out}")
    print("total files normalized:", total, "(dry run)" if not args.apply else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
