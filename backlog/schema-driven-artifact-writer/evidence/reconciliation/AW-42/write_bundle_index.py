#!/usr/bin/env python3
"""AW-42 evidence bundle index: hash every raw log and tool in the bundle and
bind them to the tested working-tree identity. The manifest never digests
itself; its own digest is published in results/AW-42.md instead.

Usage:
    python write_bundle_index.py [--repo ROOT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BUNDLE_REL = "backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-42"
# The two whole-tree reports digest bundle files, so indexing them here would make
# the bundle index and the inventory mutually recursive and never settle. They are
# cited by digest from results/AW-42.md instead, which is outside the bundle.
SKIP = {"MANIFEST.json", "bundle-index.json", "hash-reconciliation.json",
        "source-inventory.json"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(("git", *args), cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    bundle = repo / BUNDLE_REL

    entries = []
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(bundle)).replace("\\", "/")
        if rel in SKIP:
            continue
        entries.append({"path": f"{BUNDLE_REL}/{rel}", "sha256": sha256(path),
                        "bytes": path.stat().st_size})

    logs = {Path(e["path"]).stem for e in entries if e["path"].endswith(".log")}
    exit_codes = {Path(e["path"]).stem: (repo / e["path"]).read_text(encoding="utf-8").strip()
                  for e in entries if e["path"].endswith(".exit")}
    orphan_exits = sorted(set(exit_codes) - logs)
    # Observational transcripts captured without a separate exit capture. They are
    # listed rather than given an invented exit code.
    observational_logs = sorted(logs - set(exit_codes))

    manifest = {
        "schema_version": 1,
        "card": "AW-42",
        "generated": "2026-09-20",
        "bundle": "AW-42 final source/evidence reconciliation raw log bundle",
        "retention": "every referenced artifact is stored in this repository bundle; "
                     "no <preserved-run-location> indirection is used",
        "tested_source_identity": {
            "head_commit": git(repo, "rev-parse", "HEAD"),
            "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "version": (repo / "VERSION").read_text(encoding="utf-8").strip(),
            "porcelain_status": [l for l in git(repo, "status", "--porcelain=v1").splitlines()
                                 if l],
            "note": "dirty entries are the AW-42 write set plus the sixth-review planning "
                    "files; no runtime, contract, schema, asset or test byte changed for "
                    "this reconciliation",
        },
        "environments": {
            "windows": {
                "os": "nt", "platform": "win32", "filesystem": "ntfs",
                "python": sys.version.split()[0],
            },
            "posix": {
                "distro": "Ubuntu 24.04.3 LTS",
                "kernel": "6.6.87.2-microsoft-standard-WSL2",
                "arch": "x86_64", "python": "3.12.3", "pytest": "9.1.1",
                "filesystem": "ext4 (native Linux root fs; run dir under $HOME, "
                              "import origin verified outside /mnt/c)",
                "symlink_capability": "available - see raw/posix-symlink-capability.log",
            },
        },
        "recorded_exits": dict(sorted(exit_codes.items())),
        "orphan_exit_files": orphan_exits,
        "observational_logs_without_exit": observational_logs,
        "files": entries,
    }
    (bundle / "bundle-index.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                              encoding="utf-8", newline="\n")
    print(json.dumps({"head": manifest["tested_source_identity"]["head_commit"],
                      "indexed_files": len(entries),
                      "orphan_exit_files": orphan_exits,
                      "recorded_exits": manifest["recorded_exits"]}, indent=2))
    return 0 if not orphan_exits else 1


if __name__ == "__main__":
    raise SystemExit(main())
