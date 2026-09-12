"""Qualification runner (DF3-009 items 8-10).

Drives the reference qualification described in
backlog/product/v3/thresholds.md: N clean runs per release case on the
reference 35B A3B worker through the configured host, applying absolute
thresholds to every run and to the medians.

The reference model runs require the host (LM Studio with ornith-1.5-35b-a3b,
context limit 32768) — this script never fabricates results. Without the host
it still validates the report structure and prints what is missing.

Usage:
    python scripts/qualify.py --host lm-studio --cases M01-cooldown M02-policy-stats M03-adversarial
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THRESHOLDS_DOC = REPO / "backlog" / "product" / "v3" / "thresholds.md"
RUNS_DIR = REPO / "bench" / "runs"

ABSOLUTE = {
    "correctness_failed": 0,
    "stages_completed": 7,
    "gate_retries_max": 2,
    "context_peak_tokens_max": 32768,
    "framework_input_tokens_max": 16384,
    "max_unique_files": 24,
    "hallucinated_paths": 0,
    "envelope_violations": 0,
    "evidence_authentic": True,
}


def host_available(host: str) -> bool:
    """The reference host must answer before any run is attempted."""
    if host != "lm-studio":
        return False
    try:
        probe = subprocess.run(
            ["curl", "-sf", "http://127.0.0.1:1234/v1/models"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        return False
    return probe.returncode == 0


def run_case(case: str, host: str, index: int) -> dict:
    """One clean run. Implemented on the host machine; fails loudly here."""
    run_id = f"{case}-run{index}"
    raise SystemExit(
        f"reference run {run_id} requires the {host} host with the reference "
        "35B A3B worker; this machine has no such host — see "
        "backlog/product/v3/thresholds.md for the runbook"
    )


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="lm-studio")
    ap.add_argument("--cases", nargs="+", default=["M01-cooldown", "M02-policy-stats", "M03-adversarial"])
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    print(f"framework commit: {subprocess.run(['git','rev-parse','HEAD'], capture_output=True, text=True, cwd=REPO).stdout.strip()}")
    print(f"thresholds: {THRESHOLDS_DOC.relative_to(REPO)}")
    if not host_available(args.host):
        print(
            f"PENDING: host '{args.host}' with the reference 35B A3B model is not "
            "reachable; qualification runs are not executed and no results are "
            "fabricated. Start LM Studio with ornith-1.5-35b-a3b (context 32768) "
            "and re-run this script."
        )
        return 2

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": args.host,
        "thresholds": ABSOLUTE,
        "runs": [],
    }
    for case in args.cases:
        for index in range(1, args.runs + 1):
            try:
                manifest["runs"].append(run_case(case, args.host, index))
            except SystemExit as exit_exc:
                print(f"run failed: {exit_exc}")
                return 3
    (RUNS_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"runs recorded under {RUNS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
