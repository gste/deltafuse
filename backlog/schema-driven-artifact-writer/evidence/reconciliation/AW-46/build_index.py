#!/usr/bin/env python3
"""AW-46 bundle index: hash every retained raw artifact and prove log/exit pairing.

The index never digests itself and never digests this script's output, so no derived
report participates in a self-referential hash cycle.

Usage: python build_index.py [--repo PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CARD = "AW-46"
REL_BUNDLE = Path("backlog/schema-driven-artifact-writer/evidence/reconciliation") / CARD
SOURCE_FILES = [
    "src/deltafuse/core/artifact_patch.py",
    "scripts/evaluate_artifact_writer.py",
    "tests/unit/test_artifact_patch.py",
    "tests/unit/test_artifact_writer_eval.py",
    "backlog/schema-driven-artifact-writer/cards/AW-39.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args()
    repo = args.repo.resolve()
    bundle = repo / REL_BUNDLE
    raw = bundle / "raw"

    problems: list[str] = []
    transitions = raw / "restoration-transitions.log"
    trans_text = transitions.read_text(encoding="utf-8") if transitions.is_file() else ""
    verifications = trans_text.count("verify ")
    mismatches = trans_text.count("MISMATCH")
    logs = sorted(p.name[: -len(".log")] for p in raw.glob("*.log"))
    for stem in logs:
        if stem == "restoration-transitions":
            continue  # not a command run: the restore audit, summarized in "restoration"
        if not (raw / f"{stem}.exit").is_file():
            problems.append(f"log without exit record: raw/{stem}.log")
    for exit_file in sorted(raw.glob("*.exit")):
        stem = exit_file.name[: -len(".exit")]
        if stem != "pre-run-identity" and not (raw / f"{stem}.log").is_file():
            problems.append(f"exit record without log: {exit_file.name}")

    runs = []
    for stem in logs:
        if stem in {"pre-run-identity", "restoration-transitions"}:
            continue
        exit_path = raw / f"{stem}.exit"
        summary = ""
        for line in reversed((raw / f"{stem}.log").read_text(encoding="utf-8", errors="replace").splitlines()):
            if line.startswith(("--- pytest rc=", "--- rc=")):
                summary = line.strip("- ")
                break
        runs.append(
            {
                "label": stem,
                "exit": int(exit_path.read_text(encoding="utf-8").strip()) if exit_path.is_file() else None,
                "recorded": summary,
                "log_sha256": sha256(raw / f"{stem}.log"),
            }
        )

    files = {}
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(bundle).as_posix()
        if rel == "bundle-index.json" or "__pycache__" in Path(rel).parts:
            continue
        files[rel] = {"sha256": sha256(path), "bytes": path.stat().st_size}

    index = {
        "card": CARD,
        "purpose": "Reproducible evidence that AW39-R3's JSON Pointer escaping and "
                   "missing-nested-path clauses now have committed assertions that fail "
                   "under mutation of either pointer resolver.",
        "self_digest_policy": "bundle-index.json is excluded from its own file map; "
                              "source and report digests are recorded elsewhere.",
        "tested_source_identity": {
            "head_commit": "290c13a387b5fe15ccdd9f31fe4ebdca0be6fbc1",
            "note": "HEAD identifies the commit only; the bytes actually tested are the "
                    "digests below plus this bundle's raw logs.",
            "files": {
                rel: {"sha256": sha256(repo / rel), "exists": (repo / rel).is_file()}
                for rel in SOURCE_FILES
            },
        },
        "raw_pairs": {"logs": len(logs), "exit_records": len(list(raw.glob("*.exit")))},
        "restoration": {
            "transitions_ref": "raw/restoration-transitions.log",
            "verifications": verifications,
            "mismatches": mismatches,
        },
        "runs": runs,
        "problems": problems,
        "files": files,
    }
    out = bundle / "bundle-index.json"
    out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}: {len(files)} files, {len(runs)} runs, problems={problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
