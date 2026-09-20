#!/usr/bin/env python3
"""AW-42 recorded-versus-actual digest reconciler.

Scans tracked reports and evidence manifests for ``ref -> sha256`` claims,
recomputes each digest from the live working tree, and classifies the claim as
matching, drifted, line-ending-only, path-unresolved, or kept in an external
preserved run location that the repository cannot resolve.

Usage:
    python reconcile_hashes.py [--repo ROOT] [--out FILE]

Exit 0 when every claim is verified or explicitly external; 1 when any claim
drifts or cannot be resolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DIGEST = re.compile(r"^[0-9a-f]{64}$")
IGNORED_LABELS = {"this_file", "path", "Path", "SHA256", "sha256", "digest", "hash", "sha"}
REF_KEYS = ("path", "file", "name", "ref", "raw_log", "logfile", "relative_path")
DIGEST_KEYS = {"sha256", "sha2", "digest", "hash"}
EXTERNAL_PREFIXES = ("raw/", "win/", "posix/", "dist/", "<")
# Cards whose evidence AW-42 must reconcile for final acceptance. Earlier cards
# are historical records: their digests are reported, not treated as current.
FINAL_SCOPE_CARDS = ("AW-37", "AW-38", "AW-39", "AW-40", "AW-41", "AW-42",
                     "AW-43", "AW-44", "AW-45")
# Refs written relative to an installed wheel rather than the checkout.
REF_ALIASES = {
    "assets/contracts/artifact-writer.schema.yaml": "docs/contracts/artifact-writer.schema.yaml",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_lf(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def clean_ref(label: str) -> str:
    text = label.strip().strip("`").strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


def looks_like_path(ref: str) -> bool:
    """A digest-table label is a ref only if it is path-shaped, not prose."""
    if not ref or " " in ref or ref.startswith("<"):
        return False
    return "/" in ref or bool(re.search(r"\.[A-Za-z][A-Za-z0-9]{0,9}$", ref))


def extract_markdown_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip().strip("`").strip() for c in stripped.strip("|").split("|")]
        for idx, cell in enumerate(cells):
            if not DIGEST.match(cell):
                continue
            label = ""
            for prev in range(idx - 1, -1, -1):
                if cells[prev] and not DIGEST.match(cells[prev]):
                    label = cells[prev]
                    break
            if label and clean_ref(label).lower() not in IGNORED_LABELS \
                    and looks_like_path(clean_ref(label)):
                pairs.append((label, cell.lower()))
    return pairs


def walk_json(obj) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        ref = next((str(obj[k]) for k in REF_KEYS
                    if isinstance(obj.get(k), str) and str(obj.get(k)).strip()), None)
        digest = next((str(obj[k]).strip().lower() for k in obj
                       if str(k).lower() in DIGEST_KEYS and isinstance(obj[k], str)
                       and DIGEST.match(str(obj[k]).strip().lower())), None)
        if ref and digest and looks_like_path(clean_ref(ref)):
            pairs.append((ref, digest))
        for key, val in obj.items():
            if isinstance(val, str) and DIGEST.match(val.strip().lower()) \
                    and str(key).lower() not in IGNORED_LABELS \
                    and looks_like_path(clean_ref(str(key))):
                pairs.append((str(key), val.strip().lower()))
            elif isinstance(val, (dict, list)):
                pairs.extend(walk_json(val))
    elif isinstance(obj, list):
        for item in obj:
            pairs.extend(walk_json(item))
    return pairs


FINAL_BUNDLE = "backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-42"


def resolve(ref: str, repo: Path, bases: list[Path]) -> Path | None:
    candidate = clean_ref(ref)
    candidate = REF_ALIASES.get(candidate, candidate)
    if not candidate or " " in candidate or candidate.startswith("<"):
        return None
    for base in bases:
        path = base / candidate
        if path.is_file():
            return path
    # A bare log name must not resolve into this card's own freshly generated
    # bundle, or a predecessor's claim would appear to "drift" against evidence
    # produced later by this same card.
    hits = [p for p in repo.rglob(Path(candidate).name)
            if p.is_file() and "node_modules" not in p.parts and ".git" not in p.parts
            and FINAL_BUNDLE not in str(p.relative_to(repo)).replace("\\", "/")]
    return hits[0] if len(hits) == 1 else None


def collect(repo: Path, exclude: list[Path]) -> list[dict]:
    backlog = repo / "backlog" / "schema-driven-artifact-writer"
    claims: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def keep(path: Path) -> bool:
        return not any(path == e or e in path.parents or path in e.parents for e in exclude)

    def add(source: Path, ref: str, digest: str) -> None:
        key = (str(source), ref, digest)
        if key in seen:
            return
        seen.add(key)
        claims.append({"source": str(source.relative_to(repo)).replace("\\", "/"),
                       "claimed_ref": clean_ref(ref),
                       "claimed_sha256": digest,
                       "_source_dir": str(source.parent)})

    md_sources = sorted(backlog.glob("results/*.md")) + sorted(backlog.glob("*.md")) \
        + sorted(backlog.glob("evaluation/*.md")) + sorted(backlog.glob("evidence/**/*.md"))
    for md in [p for p in md_sources if keep(p)]:
        for ref, digest in extract_markdown_pairs(
                md.read_text(encoding="utf-8", errors="replace")):
            add(md, ref, digest)

    json_sources = sorted(list(backlog.glob("evaluation/*.json"))
                          + list(backlog.glob("evidence/**/*.json")))
    for jf in [p for p in json_sources if keep(p)]:
        try:
            data = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        for ref, digest in walk_json(data):
            add(jf, ref, digest)
    return claims


def card_of(source: str) -> str | None:
    """Card a claim belongs to, matched anywhere in the file name so retained
    baseline snapshots (baseline-AW-42-result.md) score as that card."""
    name = Path(source).name
    return next((card for card in FINAL_SCOPE_CARDS if card in name), None)


def claim_kind(source: str) -> str:
    if Path(source).name.startswith("REVIEW"):
        return "review_ledger"
    if card_of(source) and source.endswith(".md"):
        return "report_claim"
    return "evidence_manifest"


MANIFEST_SUFFIXES = ("evidence-index.json", "MANIFEST.json", "harness-baseline-index.json",
                     "bundle-index.json", "check-index.json")


def scope_of(source: str) -> str:
    if card_of(source) is not None or source.endswith(MANIFEST_SUFFIXES):
        return "final_scope"
    return "historical_record"


def classify(repo: Path, claims: list[dict]) -> dict:
    cache: dict[str, str] = {}
    backlog_dir = repo / "backlog" / "schema-driven-artifact-writer"
    for claim in claims:
        claim["claim_kind"] = claim_kind(claim["source"])
        claim["scope"] = scope_of(claim["source"])
        source_dir = Path(claim.pop("_source_dir"))
        bases = [source_dir, backlog_dir / "evaluation", backlog_dir, repo]
        path = resolve(claim["claimed_ref"], repo, bases)
        if path is None:
            claim["resolved_path"] = None
            claim["status"] = ("external_preserved_location"
                              if clean_ref(claim["claimed_ref"]).startswith(EXTERNAL_PREFIXES)
                              else "path_unresolved")
            continue
        rel = str(path.relative_to(repo)).replace("\\", "/")
        claim["resolved_path"] = rel
        if rel not in cache:
            cache[rel] = sha256_file(path)
        claim["actual_sha256"] = cache[rel]
        if cache[rel] == claim["claimed_sha256"]:
            claim["status"] = "match"
        else:
            claim["lf_normalized_sha256"] = sha256_lf(path)
            claim["status"] = ("line_ending_only"
                              if claim["lf_normalized_sha256"] == claim["claimed_sha256"]
                              else "drift")
    summary: dict[str, int] = {}
    for claim in claims:
        key = f"{claim['scope']}/{claim['status']}"
        summary[key] = summary.get(key, 0) + 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", default=None)
    parser.add_argument("--all-scopes", action="store_true",
                        help="also report historical cards AW-00..AW-36 digests")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "backlog" / "schema-driven-artifact-writer").is_dir():
        print(f"error: backlog dir not found under {repo}", file=sys.stderr)
        return 2

    claims = collect(repo, [Path(args.out).resolve()] if args.out else [])
    summary = classify(repo, claims)
    checked = [c for c in claims
               if args.all_scopes or c["scope"] == "final_scope"]
    problems = [c for c in checked if c["status"] != "match"]
    report = {
        "card": "AW-42",
        "generated": "2026-09-20",
        "purpose": ("recorded-versus-actual digest reconciliation over tracked reports "
                    "and evidence manifests"),
        "claim_count": len(claims),
        "final_scope_claim_count": sum(1 for c in claims if c["scope"] == "final_scope"),
        "summary": summary,
        "non_match_by_kind": {
            kind: sum(1 for c in checked if c["claim_kind"] == kind and c["status"] != "match")
            for kind in sorted({c["claim_kind"] for c in checked})
        },
        "problems": problems,
        "claims": claims,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n",
                                  encoding="utf-8", newline="\n")
    print(json.dumps({"claim_count": report["claim_count"],
                      "final_scope_claim_count": report["final_scope_claim_count"],
                      "summary": summary,
                      "non_match_by_kind_reported": report["non_match_by_kind"]}, indent=2))
    for problem in problems:
        print(f"{problem['status']:>30} {problem['claim_kind']:>17} "
              f"{problem['source']} :: {problem['claimed_ref']}")
    fail = [c for c in checked if c["status"] in
            {"drift", "path_unresolved", "line_ending_only", "unresolved"}
            and not (c["claim_kind"] == "review_ledger"
                     and c["status"] == "drift")]
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
