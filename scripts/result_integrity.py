"""QF-024: reference-integrity checker for qualification RESULT files.

Every commit SHA claimed by a RESULT must (a) exist in this repository and
(b) be an ancestor of the active branch HEAD — unless the reference sits in
an explicitly marked correction section, because historical mis-references
are preserved and explained, not silently rewritten (QF-024 rule 1).

Expected package prefixes (optionally enforced) make a missing RESULT.md a
violation instead of a silent pass.

Usage:
    python scripts/result_integrity.py [--expect QF-019 QF-020 ...] [--head HEAD]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO / "backlog" / "product" / "v3" / "qualification-fixes"

# SHA-like tokens: 7..40 hex chars on word boundaries (full SHAs and the
# short forms this repository's history uses).
_SHA_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_COMMIT_LINE = re.compile(r"commit", re.IGNORECASE)
_CORRECTION_HEADING = re.compile(
    r"^#{1,3}\s+.*(коррекц|correction)", re.IGNORECASE
)
# labeled content hashes (wheel/blob digests) are not commit references
_LABELED_HASH = re.compile(
    r"(sha256|sha1|md5|digest)[:=\s`]*[0-9a-f]{7,64}", re.IGNORECASE
)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)


def extract_commit_references(text: str) -> list[dict]:
    """SHA tokens from lines that talk about commits, with correction
    sections exempt (a correction documents the WRONG and the RIGHT sha)."""
    references: list[dict] = []
    in_correction = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            in_correction = bool(_CORRECTION_HEADING.search(line))
            continue
        if not _COMMIT_LINE.search(line):
            continue
        scan = _LABELED_HASH.sub("", line)
        for match in _SHA_TOKEN.finditer(scan):
            references.append({
                "sha": match.group(0).lower(),
                "line": line.strip()[:160],
                "in_correction": in_correction,
            })
    return references


def check_results(repo: Path = REPO, results_root: Path = RESULTS_ROOT,
                  expect: list[str] | None = None,
                  head: str = "HEAD") -> list[str]:
    """Return the list of integrity violations (empty = pass)."""
    violations: list[str] = []
    if not results_root.is_dir():
        return [f"results root missing: {results_root}"]

    result_files = sorted(results_root.glob("*/RESULT.md"))
    if expect:
        have = {p.parent.name.split("-")[0].upper() for p in result_files}
        for prefix in expect:
            if not any(name.upper().startswith(prefix.upper())
                       for name in (p.parent.name for p in result_files)):
                violations.append(
                    f"missing RESULT for expected package {prefix}"
                )

    existing: dict[str, bool] = {}
    ancestors: dict[str, bool] = {}
    for result in result_files:
        package = result.parent.name
        text = result.read_text(encoding="utf-8")
        refs = extract_commit_references(text)
        # a reference that the file itself documents as wrong (correction
        # section) is preserved history, not a live violation
        corrected = {r["sha"] for r in refs if r["in_correction"]}
        for ref in refs:
            if ref["in_correction"] or ref["sha"] in corrected:
                continue
            sha = ref["sha"]
            if sha not in existing:
                probe = _git(["cat-file", "-e", f"{sha}^{{commit}}"], repo)
                existing[sha] = probe.returncode == 0
            if not existing[sha]:
                violations.append(
                    f"{package}: SHA {sha!r} does not exist in this "
                    f"repository (line: {ref['line']})"
                )
                continue
            if sha not in ancestors:
                merge = _git(["merge-base", "--is-ancestor", sha, head], repo)
                ancestors[sha] = merge.returncode == 0
            if not ancestors[sha]:
                violations.append(
                    f"{package}: SHA {sha!r} is not in the ancestry of "
                    f"{head} (alternate/dangling base; line: {ref['line']})"
                )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expect", nargs="*", default=None,
                    help="package prefixes that MUST have a RESULT.md")
    ap.add_argument("--head", default="HEAD")
    args = ap.parse_args(argv)
    violations = check_results(expect=args.expect, head=args.head)
    if violations:
        print(f"result integrity: {len(violations)} violation(s)")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("result integrity: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
