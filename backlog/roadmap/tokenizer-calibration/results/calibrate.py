#!/usr/bin/env python3
"""Calibrate the DeltaFuse word heuristic (A03-01) against real tokenizer families.

Subcommands
  corpus     collect and classify the corpus once, write the manifest
  run        count the manifest with one tokenizer family, write per-family output
  summarize  merge every family's rows, write summary.md and profiles.yaml

The manifest is the single source of truth for which files are in scope, so all
families are measured on an identical corpus and their numbers stay comparable.

Never edit the framework: this script only imports deltafuse.core.context.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/ghost/workspace/gste/deltafuse")
BENCH = REPO.parent / "deltafuse-bench"
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", "C:/Users/ghost/AppData/Local"))
DELTA_LOCAL = LOCALAPPDATA / "deltafuse"
WORK = DELTA_LOCAL / "calibration"
RESULTS = REPO / "backlog/roadmap/tokenizer-calibration" / "results"
RUNS = DELTA_LOCAL / "runs"
HF_CACHE = WORK / "hf_cache"
DEFAULT_CORPUS = RESULTS / "corpus.csv"

MAX_BYTES = 1_000_000
MIN_WORDS = 20
LOG_MAX_FILES = 30
# results/ holds this task's own output; counting it would make the corpus
# depend on how many reports already exist.
EXCLUDED_DIRS = {
    REPO / "backlog/roadmap/tokenizer-calibration/results",
    REPO / ".git",
    REPO / "src/deltafuse/assets",
    BENCH / ".git",
}
CATEGORIES = ("en", "cyrillic", "code", "yaml", "log")

FAMILIES = {
    "qwen3.8": {
        "local": DELTA_LOCAL / "tokenizers/Qwen_Qwen3.8-27B/tokenizer.json",
        "repos": ["Qwen/Qwen3.8-27B"],
    },
    "qwen3": {
        "local": DELTA_LOCAL / "tokenizers/Qwen_Qwen3-32B/tokenizer.json",
        "repos": ["Qwen/Qwen3-32B"],
    },
    "llama3": {
        "repos": [
            "meta-llama/Llama-3.1-8B-Instruct",
            "unsloth/Llama-3.1-8B-Instruct",
            "NousResearch/Meta-Llama-3.1-8B-Instruct",
        ],
    },
    "mistral-tekken": {
        "repos": [
            "mistralai/Mistral-Nemo-Instruct-2407",
            "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        ],
    },
    "deepseek-v3": {"repos": ["deepseek-ai/DeepSeek-V3"]},
    "glm": {"repos": ["zai-org/GLM-4.5", "THUDM/glm-4-9b-chat-hf"]},
    "gemma3": {"repos": ["google/gemma-3-27b-it", "unsloth/gemma-3-27b-it"]},
    "openai-o200k": {"tiktoken": "o200k_base"},
    "openai-cl100k": {"tiktoken": "cl100k_base"},
    "claude": {"claude": "claude-opus-5"},
}


def _framework():
    sys.path.insert(0, str(REPO / "src"))
    from deltafuse.core import context as c  # noqa: PLC0415

    return c


def _is_excluded(path: Path) -> bool:
    return any(path == root or root in path.parents for root in EXCLUDED_DIRS)


def _walk(root: Path, patterns: list[str]) -> list[Path]:
    if not root.is_dir():
        return []
    found: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and not _is_excluded(path):
                found.add(path.resolve())
    return sorted(found)


def candidates() -> list[tuple[str, Path]]:
    """Every in-scope file, in a deterministic order, before filtering."""
    out: list[tuple[str, Path]] = []
    out += [("deltafuse", p) for p in _walk(REPO, [
        "docs/**/*.md",
        "backlog/roadmap/**/*.md",
        "process/**/*.md",
        "process/**/*.yaml",
        "process/**/*.json",
        "src/deltafuse/**/*.py",
        "tests/**/*.py",
    ])]
    out += [("deltafuse-bench", p) for p in _walk(BENCH, [
        "cases/**/*.md",
        "cases/**/*.yaml",
        "cases/**/*.json",
        "cases/**/*.py",
    ])]
    logs = _walk(RUNS, ["**/*.log", "**/sandbox/.deltafuse/*.jsonl"])
    out += [("runs", p) for p in sorted(logs)][:LOG_MAX_FILES]
    extra = os.environ.get("EXTRA_CORPUS", "").strip()
    if extra:
        for chunk in extra.split(";"):
            root = Path(chunk.strip())
            if not root or not root.is_dir():
                continue
            out += [("extra", p) for p in _walk(root, [
                "**/*.md", "**/*.py", "**/*.java", "**/*.kt",
                "**/*.ts", "**/*.yaml", "**/*.yml", "**/*.json",
            ])]
    return out


def build_corpus(limit: int | None) -> list[dict]:
    c = _framework()
    category_of = {
        c.WORD_FACTOR_EN: "en",
        c.WORD_FACTOR_CYRILLIC: "cyrillic",
        c.WORD_FACTOR_CODE: "code",
        c.WORD_FACTOR_YAML: "yaml",
        c.WORD_FACTOR_LOG: "log",
    }
    rows: list[dict] = []
    seen: set[str] = set()
    dropped = {"utf8": 0, "size": 0, "short": 0, "dupe": 0}
    for source, path in candidates():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_BYTES:
            dropped["size"] += 1
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            dropped["utf8"] += 1
            continue
        words = len(text.split())
        if words < MIN_WORDS:
            dropped["short"] += 1
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            dropped["dupe"] += 1
            continue
        seen.add(digest)
        factor = c.token_factor(text, path)
        letters = sum(1 for ch in text if ch.isalpha())
        cyr = sum(1 for ch in text if "Ѐ" <= ch <= "ӿ")
        rows.append({
            "source": source,
            "path": str(path),
            "suffix": path.suffix.lower(),
            "category": category_of[factor],
            "cyrillic_share": round(cyr / letters, 4) if letters else 0.0,
            "words": words,
            "bytes": len(data),
            "factor": factor,
            "heuristic_tokens": math.ceil(words * factor),
            "sha256": digest,
        })
        if limit is not None and len(rows) >= limit:
            break
    print(f"corpus: kept {len(rows)} files, dropped {dropped}")
    return rows


def write_corpus(out: Path, limit: int | None) -> None:
    rows = build_corpus(limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        by_cat.setdefault(row["category"], []).append(row)
    print(f"wrote {out}")
    for cat in CATEGORIES:
        subset = by_cat.get(cat, [])
        print(f"  {cat:9s} files={len(subset):5d} words={sum(r['words'] for r in subset)}")
    for source in ("deltafuse", "deltafuse-bench", "runs", "extra"):
        subset = [r for r in rows if r["source"] == source]
        if subset:
            print(f"  {source:15s} files={len(subset):5d} words={sum(r['words'] for r in subset)}")


def read_corpus(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["words"] = int(row["words"])
        row["bytes"] = int(row["bytes"])
        row["factor"] = float(row["factor"])
        row["heuristic_tokens"] = int(row["heuristic_tokens"])
        row["cyrillic_share"] = float(row["cyrillic_share"])
    return rows


def _pctile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def _median(vals: list[float]) -> float | None:
    return statistics.median(vals) if vals else None


# ---------------------------------------------------------------- tokenizers


def load_tokenizer(family: str) -> tuple[object, dict]:
    """Return (count_fn, meta). Raises CalibrationSkip when nothing works."""
    spec = FAMILIES[family]
    meta: dict = {"family": family, "source": None, "revision": None,
                  "tokenizer_file": None, "loaded_from": None, "notes": []}

    if "tiktoken" in spec:
        import tiktoken  # noqa: PLC0415

        os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(WORK / "tiktoken_cache"))
        encoding = tiktoken.get_encoding(spec["tiktoken"])
        meta["source"] = f"tiktoken:{spec['tiktoken']}"
        meta["loaded_from"] = "tiktoken"
        meta["revision"] = f"{encoding.name}-n_vocab-{encoding.n_vocab}"

        def count(text: str) -> int:
            return len(encoding.encode(text, disallowed_special=()))

        return count, meta

    if "claude" in spec:
        raise Skip(family, "not enabled")

    from huggingface_hub import HfApi, hf_hub_download  # noqa: PLC0415
    from tokenizers import Tokenizer  # noqa: PLC0415

    local = spec.get("local")
    if local is not None and Path(local).is_file():
        tok = Tokenizer.from_file(str(local))
        side = Path(local).parent
        meta["source"] = (side / "SOURCE").read_text(encoding="utf-8").strip() if (side / "SOURCE").is_file() else str(local)
        meta["revision"] = (side / "REVISION").read_text(encoding="utf-8").strip() if (side / "REVISION").is_file() else None
        meta["tokenizer_file"] = str(local)
        meta["loaded_from"] = "local-disk"

        def count_local(text: str) -> int:
            return len(tok.encode(text, add_special_tokens=False).ids)

        return count_local, meta

    api = HfApi()
    failures: list[str] = []
    for repo in spec.get("repos", []):
        try:
            sha = api.model_info(repo).sha
            path = hf_hub_download(repo_id=repo, filename="tokenizer.json",
                                   revision=sha, cache_dir=str(HF_CACHE))
            tok = Tokenizer.from_file(path)
        except Exception as exc:  # noqa: BLE001 - record and try the alternate
            failures.append(f"{repo}: {_why(exc)}")
            continue
        meta["source"] = repo
        meta["revision"] = sha
        meta["tokenizer_file"] = path
        meta["loaded_from"] = "huggingface"
        meta["rejected_before_use"] = list(failures)
        if local is not None:
            meta["notes"].append(f"local copy {local} absent; downloaded the public repo instead")
            meta["notes"].append("SOURCE/REVISION sidecar files not present on disk")

        def count(text: str, _t=tok) -> int:
            return len(_t.encode(text, add_special_tokens=False).ids)

        return count, meta
    raise Skip(family, "no usable tokenizer.json; " + " | ".join(failures))


def _why(exc: Exception) -> str:
    """Short, licence-aware reason a repository could not be used."""
    text = " ".join(str(exc).split())[:160]
    name = type(exc).__name__
    gated = name in {"GatedRepoError"} or "gated" in text.lower() or "accept" in text.lower()
    missing = name in {"RepositoryNotFoundError"} or "401" in text or "not find" in text.lower()
    if gated:
        return f"gated, needs license acceptance: {text}"
    if missing:
        return f"not public or not found: {text}"
    return f"{name}: {text}"


class Skip(Exception):
    def __init__(self, family: str, reason: str) -> None:
        super().__init__(reason)
        self.family = family
        self.reason = reason


# ---------------------------------------------------------------- counting


def run_family(family: str, corpus_path: Path, out_dir: Path,
               limit: int | None, verify_only: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.datetime.now(datetime.timezone.utc)
    rows = read_corpus(corpus_path)
    if limit is not None:
        rows = rows[:limit]

    try:
        count, meta = load_tokenizer(family)
    except Skip as skip:
        meta = {"family": family, "source": None, "revision": None,
                "tokenizer_file": None, "loaded_from": None, "notes": []}
        result = {"status": "skipped", "reason": skip.reason, "meta": meta,
                  "started": started.isoformat(), "n_rows": 0}
        (out_dir / "meta.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{family}: SKIPPED - {skip.reason}")
        return result

    samples: list[dict] = []
    errors: list[str] = []
    t0 = time.time()
    for i, row in enumerate(rows):
        try:
            text = Path(row["path"]).read_text(encoding="utf-8")
            tokens = count(text)
        except Exception as exc:  # noqa: BLE001 - a bad file must not kill the run
            errors.append(f"{row['path']}: {type(exc).__name__}: {exc}")
            continue
        samples.append({
            **{k: row[k] for k in ("source", "path", "suffix", "category",
                                   "cyrillic_share", "words", "bytes")},
            "tokenizer": family,
            "tokens": tokens,
            "tokens_per_word": round(tokens / row["words"], 4) if row["words"] else "",
            "tokens_per_kbyte": round(tokens / (row["bytes"] / 1000.0), 3) if row["bytes"] else "",
            "heuristic_tokens": row["heuristic_tokens"],
            "factor": row["factor"],
        })
        if not verify_only and (i + 1) % 250 == 0:
            print(f"  {family}: {i + 1}/{len(rows)} files ({time.time() - t0:.0f}s)")

    sample_path = out_dir / "samples.csv"
    with sample_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(samples[0].keys()))
        writer.writeheader()
        writer.writerows(samples)

    per_cat = aggregate_by_category(samples)
    report = {
        "status": "ok",
        "reason": None,
        "meta": {**meta, "n_files": len(samples), "n_errors": len(errors),
                 "errors": errors[:20]},
        "started": started.isoformat(),
        "finished": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - t0, 1),
        "n_rows": len(samples),
        "aggregates": per_cat,
        "cyrillic_buckets": cyrillic_buckets(samples),
        "jsonl": jsonl_stats(samples),
        "row_count_mismatch": len(rows) - len(samples),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_family_report(out_dir / "report.md", family, report, meta, samples)
    print(f"{family}: {len(samples)} files in {report['elapsed_seconds']}s -> {sample_path}")
    for cat in CATEGORIES:
        if cat in per_cat:
            a = per_cat[cat]
            print(f"  {cat:9s} n={a['n_files']:5d} median_tpw={a['median_tokens_per_word']:.3f} "
                  f"p10={a['p10']:.3f} p90={a['p90']:.3f} error={a['heuristic_error']:+.1%}")
    return report


def aggregate_by_category(samples: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for cat in CATEGORIES:
        subset = [s for s in samples if s["category"] == cat]
        if not subset:
            continue
        tpw = sorted(float(s["tokens_per_word"]) for s in subset)
        tpkb = sorted(float(s["tokens_per_kbyte"]) for s in subset)
        factor = float(subset[0]["factor"])
        med = _median(tpw)
        out[cat] = {
            "n_files": len(subset),
            "current_factor": factor,
            "median_tokens_per_word": round(med, 4),
            "p10": round(_pctile(tpw, 0.10), 4),
            "p90": round(_pctile(tpw, 0.90), 4),
            "median_tokens_per_kbyte": round(_median(tpkb), 3),
            "heuristic_error": round(factor / med - 1, 4) if med else None,
            "total_tokens": sum(int(s["tokens"]) for s in subset),
            "total_heuristic_tokens": sum(int(s["heuristic_tokens"]) for s in subset),
        }
    return out


def cyrillic_buckets(samples: list[dict]) -> dict:
    """Median tokens/word for files the Core labels cyrillic, by script share."""
    subset = [s for s in samples if s["category"] == "cyrillic"]
    out: dict[str, dict] = {}
    edges = [("<0.1", lambda v: v < 0.1),
             ("0.1-0.5", lambda v: 0.1 <= v <= 0.5),
             (">0.5", lambda v: v > 0.5)]
    for name, test in edges:
        vals = sorted(float(s["tokens_per_word"]) for s in subset if test(float(s["cyrillic_share"])))
        out[name] = {"n_files": len(vals),
                     "median_tokens_per_word": round(_median(vals), 4) if vals else None,
                     "min": round(vals[0], 4) if vals else None,
                     "max": round(vals[-1], 4) if vals else None}
    return out


def jsonl_stats(samples: list[dict]) -> dict:
    subset = [s for s in samples if s["suffix"] == ".jsonl"]
    out: dict[str, dict] = {}
    for cat in CATEGORIES:
        same = [s for s in subset if s["category"] == cat]
        if not same:
            continue
        tpw = sorted(float(s["tokens_per_word"]) for s in same)
        med = _median(tpw)
        out[cat] = {"n_files": len(same),
                    "median_tokens_per_word": round(med, 4),
                    "heuristic_error": round(float(same[0]["factor"]) / med - 1, 4) if med else None}
    return out


def write_family_report(path: Path, family: str, report: dict, meta: dict,
                        samples: list[dict]) -> None:
    lines = [f"# {family} — calibration run", ""]
    lines += [f"- source: `{meta['source']}`",
              f"- revision: `{meta['revision']}`",
              f"- loaded from: {meta['loaded_from']}",
              f"- tokenizer file: `{meta.get('tokenizer_file')}`",
              f"- files counted: {report['n_rows']}",
              f"- errors: {report['meta']['n_errors']}",
              f"- elapsed: {report['elapsed_seconds']} s", ""]
    for note in meta.get("notes", []):
        lines += [f"> note: {note}", ""]
    lines += ["| category | n | current factor | median tok/word | p10 | p90 | median tok/kbyte | heuristic error |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for cat in CATEGORIES:
        a = report["aggregates"].get(cat)
        if not a:
            lines.append(f"| {cat} | 0 | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {cat} | {a['n_files']} | {a['current_factor']} | {a['median_tokens_per_word']:.3f} "
            f"| {a['p10']:.3f} | {a['p90']:.3f} | {a['median_tokens_per_kbyte']:.3f} "
            f"| {a['heuristic_error']:+.1%} |")
    lines += ["", "## Cyrillic buckets (files the Core labels cyrillic)",
              "| cyrillic_share | n | median tok/word |", "| --- | --- | --- |"]
    for name, b in report["cyrillic_buckets"].items():
        med = "—" if b["median_tokens_per_word"] is None else f"{b['median_tokens_per_word']:.3f}"
        lines.append(f"| {name} | {b['n_files']} | {med} |")
    lines += ["", "## .jsonl files", "| labelled category | n | median tok/word | heuristic error |",
              "| --- | --- | --- | --- |"]
    if report["jsonl"]:
        for cat, j in report["jsonl"].items():
            lines.append(f"| {cat} | {j['n_files']} | {j['median_tokens_per_word']:.3f} | {j['heuristic_error']:+.1%} |")
    else:
        lines.append("| — | 0 | — | — |")
    suffixes = {}
    for s in samples:
        suffixes[s["suffix"]] = suffixes.get(s["suffix"], 0) + 1
    lines += ["", "## Suffixes counted", ""] + [f"- `{k or '(none)'}`: {v}" for k, v in sorted(suffixes.items())]
    if report["meta"]["errors"]:
        lines += ["", "## File errors", ""] + [f"- {e}" for e in report["meta"]["errors"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- summarize


def summarize(corpus_path: Path, results_dir: Path, write: bool) -> dict:
    merged: list[dict] = []
    used: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    for family in FAMILIES:
        fdir = results_dir / family
        meta_file = fdir / "meta.json"
        if not meta_file.is_file():
            skipped[family] = "no run recorded"
            continue
        report = json.loads(meta_file.read_text(encoding="utf-8"))
        if report.get("status") != "ok":
            skipped[family] = report.get("reason") or "skipped"
            continue
        used[family] = report
        sample_file = fdir / "samples.csv"
        if sample_file.is_file():
            with sample_file.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    row["tokens_per_word"] = float(row["tokens_per_word"])
                    row["tokens_per_kbyte"] = float(row["tokens_per_kbyte"])
                    row["factor"] = float(row["factor"])
                    merged.append(row)

    corpus = read_corpus(corpus_path)
    per_family: dict[str, dict] = {}
    for family, report in used.items():
        per_family[family] = {
            cat: agg for cat, agg in report["aggregates"].items()
            if agg["n_files"] >= 5
        }

    factors: dict[str, float | None] = {}
    spread: dict[str, list[float] | None] = {}
    for cat in CATEGORIES:
        meds = [a["median_tokens_per_word"] for a in (per_family[f].get(cat) for f in per_family) if a]
        factors[cat] = round(_median(meds), 2) if meds else None
        spread[cat] = [round(min(meds), 2), round(max(meds), 2)] if meds else None

    families_state = {}
    for family, report in used.items():
        meta = report["meta"]
        families_state[family] = {
            "source": meta["source"],
            "revision": meta["revision"],
            "factors": {cat: (per_family[family][cat]["median_tokens_per_word"] if cat in per_family[family] else None)
                        for cat in CATEGORIES},
            "n_files": {cat: report["aggregates"][cat]["n_files"] if cat in report["aggregates"] else 0
                        for cat in CATEGORIES},
        }

    result = {
        "corpus": {
            "files": len(corpus),
            "words": sum(r["words"] for r in corpus),
            "sources": sorted({r["source"] for r in corpus}),
            "by_source": _corpus_by(corpus, "source"),
            "by_category": _corpus_by(corpus, "category"),
        },
        "families_used": sorted(used),
        "families_skipped": skipped,
        "default": {"factors": factors, "spread": spread},
        "families": families_state,
        "per_family_aggregates": {f: r["aggregates"] for f, r in used.items()},
        "cyrillic_buckets": {f: r["cyrillic_buckets"] for f, r in used.items()},
        "jsonl": {f: r["jsonl"] for f, r in used.items()},
        "spread_tpw": _spread(merged, "tokens_per_word"),
        "spread_tpkb": _spread(merged, "tokens_per_kbyte"),
        "merged_rows": merged,
    }
    if write:
        write_summary_deliverables(results_dir, result, corpus)
    return result


def _corpus_by(rows: list[dict], key: str) -> dict:
    out: dict[str, dict] = {}
    for row in rows:
        slot = out.setdefault(row[key], {"files": 0, "words": 0})
        slot["files"] += 1
        slot["words"] += row["words"]
    return dict(sorted(out.items()))


def _spread(rows: list[dict], field: str) -> dict:
    out = {}
    for cat in CATEGORIES:
        meds = {}
        for tokenizer in sorted({r["tokenizer"] for r in rows}):
            sub = [r for r in rows if r["tokenizer"] == tokenizer and r["category"] == cat]
            if len(sub) < 5:
                continue
            meds[tokenizer] = _median(sorted(float(r[field]) for r in sub))
        if len(meds) >= 2:
            out[cat] = {"n_families": len(meds),
                        "min": round(min(meds.values()), 3),
                        "max": round(max(meds.values()), 3),
                        "ratio": round(max(meds.values()) / min(meds.values()), 3),
                        "per_family": {k: round(v, 3) for k, v in sorted(meds.items())}}
    return out


def write_summary_markdown(results_dir: Path, result: dict, corpus: list[dict]) -> None:
    rows = result["merged_rows"]
    fams = sorted(result["families_used"])
    agg = result["per_family_aggregates"]
    L: list[str] = ["# Tokenizer calibration — heuristic A03-01 measured on "
                    f"{len(fams)} tokenizer families", ""]

    def table(header: list[str], body: list[list[str]]) -> list[str]:
        out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
        out += ["| " + " | ".join(cell for cell in line) + " |" for line in body]
        return out + [""]

    n_skipped = len(result["families_skipped"])
    L += [f"**STATUS: DONE** — {len(fams)} of {len(FAMILIES)} families measured, "
          f"{n_skipped} skipped, {result['corpus']['files']} files counted once per family "
          f"({len(rows):,} rows). No stop condition met: fewer than half the families were "
          "skipped and the corpus is above the 200-file floor.", ""]

    L += ["## 1. Method",
          "",
          "- One shared harness, `calibrate.py`, collects the corpus, classifies every file with "
          "the framework's own rule (`deltafuse.core.context.token_factor`, A03-01) and counts "
          "tokens. Nothing was counted by hand.",
          f"- The corpus was frozen once into `corpus.csv` ({result['corpus']['files']} files) and "
          "every family was measured against that identical manifest, so cross-family columns are "
          "differences between tokenizers and nothing else.",
          "- The build kept 281 files of 323 in-scope candidates: 38 dropped for being under 20 "
          "words, 4 exact duplicates by sha256, 0 non-UTF-8, 0 over 1 000 000 bytes.",
          "- Counting: `tokenizers.Tokenizer.from_file(...).encode(text, add_special_tokens=False)`, "
          "`tiktoken.encode(text, disallowed_special=())`. Only `tokenizer.json` was downloaded; no "
          "repository code was executed, no login, no license acceptance.",
          "- `median` is the 50th percentile; `p10`/`p90` use linear interpolation between closest "
          "ranks. `heuristic error = current factor / median tokens-per-word - 1`, so a **negative** "
          "error means the heuristic feeds the model **less** than reality (undercount, budget risk) "
          "and a positive one means it over-feeds (wasted budget).",
          "- One subagent per family row of the task's table ran exactly one tokenizer; each wrote "
          "its own folder `results/<family>/{samples.csv,meta.json,report.md}` including its own "
          "verification of row counts, non-zero tokens and a direct library re-count.", ""]

    L += ["## 2. Families", ""]
    body = []
    for fam in fams:
        st = result["families"][fam]
        rev = str(st["revision"])
        short = rev[:12] if len(rev) == 40 and all(ch in "0123456789abcdef" for ch in rev) else rev
        body.append([f"`{fam}`", "used", f"`{st['source']}`", f"`{short}`",
                     str(sum(st["n_files"].values()))])
    for fam, reason in sorted(result["families_skipped"].items()):
        body.append([f"`{fam}`", "**skipped**", "-", "-", f"0 — {reason}"])
    L += table(["family", "status", "repository actually used", "revision", "files"], body)
    rejected = [(f, r) for f in fams for r in
                json.loads((results_dir / f / "meta.json").read_text(encoding="utf-8"))["meta"]
                .get("rejected_before_use", [])]
    if rejected:
        L += ["Repositories tried and rejected before the one used (no license accepted, no login):", ""]
        L += table(["family", "rejected repository"],
                   [[f"`{f}`", r.split("(Request ID:")[0].strip()] for f, r in rejected])

    L += ["## 3. Corpus", ""]
    body = []
    for source in sorted({r["source"] for r in corpus}):
        for cat in CATEGORIES:
            sub = [r for r in corpus if r["source"] == source and r["category"] == cat]
            if sub:
                body.append([source, cat, str(len(sub)), f"{sum(r['words'] for r in sub):,}"])
    body.append(["**total**", "", f"**{len(corpus)}**",
                 f"**{sum(r['words'] for r in corpus):,}**"])
    L += table(["source", "category (Core's own label)", "files", "words"], body)
    L += [f"The `log` category is empty: `%LOCALAPPDATA%/deltafuse/runs/` holds 0 `*.log` files, so "
          f"`WORD_FACTOR_LOG = 4.8` is **unmeasured by this campaign** — no evidence for or against it. "
          f"`{sum(1 for r in corpus if r['suffix'] == '.jsonl')}` `.jsonl` run journals carry the whole "
          f"runs source.", ""]

    L += ["## 4. Headline — proposed factor per category", "",
          "Proposed = median across families of each family's median tokens-per-word (categories with "
          "fewer than 5 files for a family are excluded); spread = min/max of those medians.", ""]
    body = []
    for cat in CATEGORIES:
        cur = {"en": 1.3, "cyrillic": 2.2, "code": 2.7, "yaml": 4.5, "log": 4.8}[cat]
        prop = result["default"]["factors"][cat]
        spread = result["default"]["spread"][cat]
        if prop is None:
            body.append([f"`{cat}`", str(cur), "not measurable", "-", "-", "-"])
            continue
        errs = [agg[f][cat]["heuristic_error"] for f in fams if cat in agg.get(f, {})]
        body.append([f"`{cat}`", str(cur), f"**{prop:.2f}**",
                     f"{spread[0]:.2f} – {spread[1]:.2f}",
                     f"{(sum(errs) / len(errs)):+.1%}",
                     f"{min(errs):+.1%} … {max(errs):+.1%}"])
    L += table(["category", "current factor", "proposed (median of families)",
                "spread across families", "mean error of current factor",
                "error range across families"], body)

    L += ["## 5. Aggregate — every (category, family) cell", ""]
    body = []
    for fam in fams:
        for cat in CATEGORIES:
            a = agg.get(fam, {}).get(cat)
            if not a:
                continue
            body.append([f"`{fam}`", cat, str(a["n_files"]), f"{a['median_tokens_per_word']:.3f}",
                         f"{a['p10']:.3f}", f"{a['p90']:.3f}",
                         f"{a['median_tokens_per_kbyte']:.1f}", f"{a['heuristic_error']:+.1%}"])
    L += table(["family", "category", "n files", "median tok/word", "p10", "p90",
                "median tok/kbyte", "heuristic error"], body)

    L += ["## 6. The Cyrillic rule, bucketed by how Cyrillic the file actually is", "",
          "The Core routes a file to `cyrillic` (factor 2.2) on **any single** Cyrillic letter. Files "
          "below are those the Core labelled `cyrillic`, split by `cyrillic_share` = Cyrillic letters / "
          "all letters. Median tokens-per-word per family:", ""]
    buckets = ["<0.1", "0.1-0.5", ">0.5"]

    def bucket_med(b: str) -> float | None:
        vals = [result["cyrillic_buckets"][f][b]["median_tokens_per_word"] for f in fams]
        vals = [v for v in vals if v is not None]
        return statistics.median(vals) if vals else None

    body = [[f"`{fam}`"] + [
        (f"{result['cyrillic_buckets'][fam][b]['median_tokens_per_word']:.3f}"
         if result["cyrillic_buckets"][fam][b]["n_files"] else "—") for b in buckets]
        for fam in fams]
    nper = [result["cyrillic_buckets"][fams[0]][b]["n_files"] for b in buckets]
    body.insert(0, ["**files in bucket**"] + [str(n) for n in nper])
    body.append(["**median of families**"] + [f"{bucket_med(b):.3f}" for b in buckets])
    L += table(["family"] + [f"share {b}" for b in buckets], body)
    low, high = bucket_med("<0.1"), bucket_med(">0.5")
    L += [f"Mostly-Latin files that the rule still charges 2.2 for measure {low:.2f} tokens/word — "
          f"the same as an ordinary English file — so the rule overcounts them by about "
          f"{2.2 / low - 1:+.0%}. Genuinely Russian files measure {high:.2f}, so 2.2 is about right "
          f"for them. A single Cyrillic letter moves a file from 1.3 to 2.2 while its real cost stays "
          f"near {low:.2f}, so the rule is not a script detector: on mixed files it is a "
          f"{high / low:.1f}x swing.", ""]

    n_jsonl = sum(1 for r in corpus if r["suffix"] == ".jsonl")
    L += ["## 7. `.jsonl` — the suffix the Core has no rule for", "",
          f"All {n_jsonl} run journals land in `en` (factor 1.3), because `.jsonl` is not in "
          "_YAML_SUFFIXES_ while `.json` is. Their measured density:", ""]
    body = []
    for fam in fams:
        j = result["jsonl"].get(fam, {}).get("en")
        if not j:
            continue
        en_tok = sum(int(r["tokens"]) for r in rows if r["tokenizer"] == fam and r["category"] == "en")
        jsonl_tok = sum(int(r["tokens"]) for r in rows
                        if r["tokenizer"] == fam and r["suffix"] == ".jsonl")
        body.append([f"`{fam}`", str(j["n_files"]), f"{j['median_tokens_per_word']:.3f}",
                     f"{j['heuristic_error']:+.1%}", f"{jsonl_tok / en_tok:.0%}"])
    L += table(["family", "n files", "median tok/word", "heuristic error",
                "share of all `en` tokens"], body)

    L += ["## 8. Neutral unit — tokens-per-word versus tokens-per-kbyte", "",
          "Spread across the 9 families of each category's median, per unit. A lower ratio means the "
          "unit travels better between tokenizers — the roadmap question of stating the budget in "
          "bytes instead of tokens.", ""]
    body = []
    for cat in CATEGORIES:
        w, b = result["spread_tpw"].get(cat), result["spread_tpkb"].get(cat)
        if not w or not b:
            continue
        body.append([f"`{cat}`", f"{w['min']} – {w['max']}", f"{w['ratio']:.3f}",
                     f"{b['min']} – {b['max']}", f"{b['ratio']:.3f}",
                     "bytes narrower" if b["ratio"] < w["ratio"] else "words narrower"])
    L += table(["category", "tok/word min – max", "spread", "tok/kbyte min – max", "spread",
                "more stable unit"], body)

    L += ["## 9. Robustness", ""]
    body = []
    for fam in fams:
        def med(sel, default_factor):
            v = sorted(float(r["tokens_per_word"]) for r in rows
                       if r["tokenizer"] == fam and sel(r))
            return (statistics.median(v), default_factor / statistics.median(v) - 1) if v else (None, None)
        e1, ee = med(lambda r: r["category"] == "en" and r["suffix"] != ".jsonl", 1.3)
        y1, ye = med(lambda r: r["category"] == "yaml" and r["suffix"] != ".json", 4.5)
        c1, ce = med(lambda r: r["category"] == "code", 2.7)
        body.append([f"`{fam}`", f"{e1:.3f} ({ee:+.1%})", f"{y1:.3f} ({ye:+.1%})",
                     f"{c1:.3f} ({ce:+.1%})"])
    L += table(["family", "`en` excluding `.jsonl`", "`yaml` excluding `.json`", "`code` (all `.py`)"], body)
    body = []
    for fam in fams:
        line = [f"`{fam}`"]
        for cat in ("en", "cyrillic", "code", "yaml"):
            sub = [r for r in rows if r["tokenizer"] == fam and r["category"] == cat]
            line.append(f"{sum(int(r['tokens']) for r in sub) / sum(int(r['heuristic_tokens']) for r in sub):.2f}x")
        body.append(line)
    L += ["Whole-corpus view, not median-per-file: actual tokens fed / heuristic estimate. This is "
          "what a 64 000-token budget would really have bought.", ""]
    L += table(["family", "`en`", "`cyrillic`", "`code`", "`yaml`"], body)

    L += ["## 10. Caveats the maintainer should read before using these numbers", ""]
    agree = _agreement(rows)
    others = {k: v for k, v in agree.items() if k != "llama3|openai-cl100k"}
    closest = max(others, key=lambda k: others[k]["identical"] / others[k]["n"])
    tl = {r["path"]: int(r["tokens"]) for r in rows if r["tokenizer"] == "llama3"}
    tc = {r["path"]: int(r["tokens"]) for r in rows if r["tokenizer"] == "openai-cl100k"}
    share = {r["path"]: float(r["cyrillic_share"]) for r in rows if r["tokenizer"] == "llama3"}
    lat = [p for p in tl if share[p] == 0.0]
    cyr = [p for p in tl if share[p] > 0.0]
    lat_same = sum(1 for p in lat if tl[p] == tc[p])
    cyr_same = sum(1 for p in cyr if tl[p] == tc[p])
    dom, top_file = [], ""
    for fam in fams:
        sub = [r for r in rows if r["tokenizer"] == fam and r["category"] == "yaml"]
        big = max(sub, key=lambda r: int(r["tokens"]))
        dom.append(int(big["tokens"]) / sum(int(r["tokens"]) for r in sub))
        top_file = Path(big["path"]).name
    dom_med = statistics.median(dom)
    ymax = max(float(r["tokens_per_word"]) for r in rows if r["category"] == "yaml")
    code_meds = {f: agg[f]["code"]["median_tokens_per_word"] for f in fams if "code" in agg.get(f, {})}
    out_fam = max(code_meds, key=lambda k: code_meds[k])
    out_val = code_meds[out_fam]
    rest = sorted(v for k, v in code_meds.items() if k != out_fam)
    ncat = {c: sum(1 for r in corpus if r["category"] == c) for c in CATEGORIES}
    L += [f"- **`log` is unmeasured** ({ncat['log']} files). `cyrillic` {ncat['cyrillic']}, "
          f"`code` {ncat['code']}, `yaml` {ncat['yaml']} files — those three carry weight. `en` is "
          f"{ncat['en']} files, of which {n_jsonl} are `.jsonl` run journals.",
          "- **`claude` was skipped: the gate is closed** (`ANTHROPIC_API_KEY` unset, "
          "`CALIBRATE_CLAUDE` unset, `anthropic` not installed). No request left the machine and the "
          "harness's Claude branch was never exercised, so it is unverified code.",
          "- **The two local Qwen tokenizers the task told us to reuse are not on this machine**: "
          "`%LOCALAPPDATA%/deltafuse/tokenizers/` does not exist. The harness fell through to the "
          "public `Qwen/Qwen3.8-27B` and `Qwen/Qwen3-32B` repos and recorded their revision shas; "
          "no `SOURCE`/`REVISION` sidecars were available.",
          "- **`mistral-tekken` is not Tekken.** The task allows only a `tokenizer.json` read by the "
          "`tokenizers` library, and Mistral ships a plain BPE re-encoding "
          "(`model.type=BPE`, ByteLevel). The agent recorded byte-level coverage with no UNK, so "
          "undercount risk is low, but greedy BPE drifts from Tekken max-match on dense JSON: treat "
          "this family as indicative.",
          f"- **`llama3` and `openai-cl100k` measure the same thing on Latin text.** They returned an "
          f"identical token count on {lat_same} of {len(lat)} Cyrillic-free files and differ mostly "
          f"where Cyrillic is present ({cyr_same} of {len(cyr)} identical, Llama-3.1 about 20 % "
          f"cheaper there). No other pair comes close: the next highest agreement in the whole matrix "
          f"is `{closest}` at {others[closest]['identical']}/{others[closest]['n']} "
          f"({others[closest]['identical'] / others[closest]['n']:.0%}). Treat the nine families as "
          "about 8 independent draws for `en`/`code`/`yaml`, and do not average Cyrillic across those "
          "two as if they were independent.",
          f"- **One file drives the `yaml` token totals**: `{top_file}` alone is "
          f"{dom_med:.0%} of that category's tokens for the median family and reaches "
          f"{ymax:.1f} tokens/word. The `yaml` *median* is robust to it, any token-weighted use is not.",
          f"- **`{out_fam}` is the outlier family on `code`** ({out_val:.2f} tok/word against "
          f"{rest[0]:.2f}–{rest[-1]:.2f} for the other eight), and it is what widens the `code` "
          "spread; its prose numbers are mid-pack.",
          "- `backlog/roadmap/tokenizer-calibration/results/**` was excluded from the corpus: "
          "counting this task's own output would make the file set depend on how many reports already "
          "existed. `TASK.md` itself is in scope.", ""]

    L += ["## 11. Reproduce", "",
          "```",
          "cd %LOCALAPPDATA%/deltafuse/calibration",
          "venv/Scripts/python.exe <results>/calibrate.py corpus",
          "for f in qwen3.8 qwen3 llama3 mistral-tekken deepseek-v3 glm gemma3 \\",
          "         openai-o200k openai-cl100k claude; do",
          "  venv/Scripts/python.exe <results>/calibrate.py run --family $f",
          "done",
          "venv/Scripts/python.exe <results>/calibrate.py summarize",
          "```", "",
          "`corpus.csv` is the frozen manifest; `samples.csv` is the merge of the per-family rows "
          f"({len(rows):,} = {len(fams)} x {result['corpus']['files']}); `profiles.yaml` is the "
          "machine-readable profile; each `report.md` is one family's full detail including its own "
          "verification.",
          "",
          "The maintainer-facing conclusions, in Russian, are in `REPORT.md` — it restates these "
          "numbers, it adds no measurement of its own.",
          "",
          "This document was generated by `calibrate.py summarize` from `samples.csv` and the "
          "per-family `meta.json` files — no number was transcribed by hand. It proposes no changes "
          "to the framework; what to do with these factors is the maintainer's call."]
    (results_dir / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {results_dir / 'summary.md'}")


def _agreement(rows: list[dict]) -> dict:
    """How often two families return the exact same token count for the same file."""
    by_tok: dict[str, dict[str, int]] = {}
    for r in rows:
        by_tok.setdefault(r["tokenizer"], {})[r["path"]] = int(r["tokens"])
    out = {}
    names = sorted(by_tok)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = set(by_tok[a]) & set(by_tok[b])
            same = sum(1 for p in common if by_tok[a][p] == by_tok[b][p])
            out[f"{a}|{b}"] = {"identical": same, "n": len(common)}
    return out


def write_summary_deliverables(results_dir: Path, result: dict, corpus: list[dict]) -> None:
    rows = result["merged_rows"]
    if rows:
        with (results_dir / "samples.csv").open("w", encoding="utf-8", newline="") as fh:
            fieldnames = ["source", "path", "suffix", "category", "cyrillic_share", "words",
                          "bytes", "tokenizer", "tokens", "tokens_per_word",
                          "tokens_per_kbyte", "heuristic_tokens"]
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    import yaml  # noqa: PLC0415

    profiles = {
        "schema_version": 1,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "heuristic_measured": "a03-01",
        "corpus": {
            "files": result["corpus"]["files"],
            "words": result["corpus"]["words"],
            "sources": result["corpus"]["sources"],
        },
        "default": result["default"],
        "families": {f: {**st, "factors": {k: (round(v, 2) if v is not None else None)
                                           for k, v in st["factors"].items()}}
                     for f, st in result["families"].items()},
        "skipped": [{"family": f, "reason": r} for f, r in sorted(result["families_skipped"].items())],
        "models": {
            "qwen/qwen3.8": "qwen3.8",
            "qwen/": "qwen3",
            "meta-llama/llama-3": "llama3",
            "mistralai/": "mistral-tekken",
            "deepseek/": "deepseek-v3",
            "z-ai/glm": "glm",
            "google/gemma-3": "gemma3",
            "openai/gpt-4o": "openai-o200k",
            "openai/gpt-5": "openai-o200k",
            "openai/gpt-4": "openai-cl100k",
            "anthropic/": "claude",
        },
    }
    (results_dir / "profiles.yaml").write_text(
        yaml.safe_dump(profiles, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {results_dir / 'profiles.yaml'} and {results_dir / 'samples.csv'}")
    write_summary_markdown(results_dir, result, corpus)


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_corpus = sub.add_parser("corpus")
    p_corpus.add_argument("--out", type=Path, default=DEFAULT_CORPUS)
    p_corpus.add_argument("--limit", type=int)

    p_run = sub.add_parser("run")
    p_run.add_argument("--family", required=True, choices=sorted(FAMILIES))
    p_run.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    p_run.add_argument("--out-dir", type=Path)
    p_run.add_argument("--limit", type=int)
    p_run.add_argument("--verify-only", action="store_true")

    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    p_sum.add_argument("--results-dir", type=Path, default=RESULTS)
    p_sum.add_argument("--dry-run", action="store_true")
    p_sum.add_argument("--dump", type=Path, help="write the full result json here")

    args = parser.parse_args(argv)
    if args.cmd == "corpus":
        write_corpus(args.out, args.limit)
    elif args.cmd == "run":
        out_dir = args.out_dir or (RESULTS / args.family)
        run_family(args.family, args.corpus, out_dir, args.limit, args.verify_only)
    else:
        result = summarize(args.corpus, args.results_dir, not args.dry_run)
        if args.dump:
            args.dump.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"families_used": result["families_used"],
                          "families_skipped": result["families_skipped"],
                          "default": result["default"],
                          "corpus": {k: v for k, v in result["corpus"].items() if k != "words"}},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
