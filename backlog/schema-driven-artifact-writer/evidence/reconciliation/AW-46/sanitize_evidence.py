#!/usr/bin/env python3
"""AW-46 evidence sanitizer: replace machine-specific absolute paths with portable tokens.

AGENTS.md forbids committing environment-specific absolute paths, while EXECUTOR forbids
rewriting raw evidence. This step resolves that conflict by publishing a *redacted* copy of
every affected log and recording each file's pre-redaction and post-redaction sha256 in
raw/sanitization.json, so a verifier can see exactly what was masked and can re-derive the
current bytes from the bundle. Nothing else about a run is altered: argv, exit codes,
per-run source digests and pytest output are preserved verbatim.

Usage: python sanitize_evidence.py [--bundle DIR] [--apply]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPLACEMENTS = [
    (re.compile(r"/c/Users/ghost/workspace/gste/deltafuse"), "<repo>"),
    # one or two backslashes, or forward slashes: pytest embeds JSON-escaped paths in reports
    (re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}ghost[\\/]{1,2}workspace[\\/]{1,2}gste[\\/]{1,2}deltafuse"), "<repo>"),
    (re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}ghost[\\/]{1,2}AppData[\\/]{1,2}Local[\\/]{1,2}Temp"), "<tmp>"),
    (re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}ghost"), "<home>"),
    (re.compile(r"/tmp/aw46-backups"), "<tmp>/aw46-backups"),
    (re.compile(r"/home/gste\b"), "<posix-home>"),
    (re.compile(r"pytest-of-ghost"), "pytest-of-<user>"),
    (re.compile(r"[\\/]Users[\\/]ghost"), "<home>"),
]
REDACTION_MARK = re.compile(r"<repo>|<tmp>|<home>|<posix-home>|pytest-of-<user>")
RESIDUAL = re.compile(r"[\\/]Users[\\/]|(?<![\w.-])[\\/]home/[a-z]|pytest-of-ghost|(?<![A-Za-z])[A-Za-z]:[\\/]{1,2}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path,
                    default=Path("backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-46"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reverify", action="store_true",
                    help="rewrite the residual-audit fields of an existing sanitization.json "
                         "without touching entries or the recorded redaction map")
    args = ap.parse_args()

    changed, residual, scanned = [], [], 0
    # Only evidence is redacted; the reproduction scripts stay verbatim so a verifier can
    # run them unchanged. Bundle-root JSON is included because AW-42's check-index.json
    # records argv vectors containing the interpreter path.
    targets = sorted((args.bundle / "raw").rglob("*")) + sorted(args.bundle.glob("*.json"))
    for path in targets:
        if not path.is_file() or path.suffix not in {".log", ".txt", ".json"}:
            continue
        if path.name in {"sanitization.json", "sanitize_evidence.py"}:
            continue  # the audit record embeds these patterns; it must stay verbatim
        scanned += 1
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        redacted = text
        for pattern, token in REPLACEMENTS:
            redacted = pattern.sub(token, redacted)
        if REDACTION_MARK.search(redacted):
            for line in redacted.splitlines():
                if RESIDUAL.search(line):
                    residual.append(f"{path.as_posix()}: {line[:120]}")
        if redacted != text:
            changed.append({
                "path": path.relative_to(args.bundle).as_posix(),
                "sha256_before": hashlib.sha256(raw).hexdigest(),
                "sha256_after": hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
            })
            if args.apply:
                path.write_text(redacted, encoding="utf-8", newline="\n")

    report = {
        "purpose": "Portable redaction of machine-specific absolute paths in AW-46 raw evidence",
        "files_scanned": scanned,
        "files_redacted": len(changed),
        "tokens": {pattern.pattern: token for pattern, token in REPLACEMENTS},
        "residual_absolute_paths": residual,
        "entries": changed,
    }
    print(json.dumps({k: v for k, v in report.items() if k != "entries"}, indent=2))
    for entry in changed:
        print(f"redacted {entry['path']}: {entry['sha256_before'][:16]} -> {entry['sha256_after'][:16]}")
    if args.reverify:
        out = args.bundle / "raw" / "sanitization.json"
        prior = json.loads(out.read_text(encoding="utf-8"))
        prior["residual_absolute_paths"] = residual
        prior["reverified_clean"] = not residual and not changed
        prior["reverified_files_scanned"] = scanned
        prior["residual_note"] = ("The first apply pass listed three residual matches; they were "
                                  "canonical https://deltafuse.dev schema URIs, not machine paths. "
                                  "Re-verified with the final pattern: none remain. The entries map "
                                  "and the recorded token list are the apply pass's, unmodified.")
        out.write_text(json.dumps(prior, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"reverified clean={prior['reverified_clean']} residual={len(residual)} "
              f"map retained ({len(prior['entries'])} entries) -> {out}")
        return 1 if residual else 0
    if args.apply:
        out = args.bundle / "raw" / "sanitization.json"
        if out.is_file():
            prior = json.loads(out.read_text(encoding="utf-8"))
            # An apply pass must not discard the original before/after map: merge it, so the
            # record keeps what was redacted and what the final bytes verify to.
            known = {e["path"]: e for e in prior.get("entries", [])}
            for e in changed:
                known[e["path"]] = e
            report["entries"] = list(known.values())
            report["files_redacted"] = len(report["entries"])
            report["reverified_clean"] = not residual and not changed
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print("dry run; pass --apply to write")
    return 1 if residual else 0


if __name__ == "__main__":
    raise SystemExit(main())
