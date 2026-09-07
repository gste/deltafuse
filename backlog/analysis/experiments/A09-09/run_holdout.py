"""Sequence S09 holdout phases. Does not change prompts; stops a repeat on fail or terminal status."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness" / "run_case.py"
EXPERIMENT = Path(__file__).resolve().parent
CASE = "S09"
TERMINAL = {"rejected", "duplicate", "not-reproduced", "superseded", "archived"}
STEPS = [
    ("intake", "routing", "2048"),
    ("analyze", "routing", "2048"),
    ("analyze", "slices", "4096"),
    ("analyze", "coverage", "2048"),
    ("specify", "routing", "4096"),
    ("decompose", "routing", "4096"),
    ("target", "routing", "2048"),
    ("implement", "routing", "4096"),
    ("verify", "routing", "2048"),
]


def phase_dir_name(phase: str, focus: str) -> str:
    if phase == "analyze":
        return f"analyze-{focus}"
    if phase in {"target", "implement"}:
        return f"{phase}-TASK-001"
    return phase


def last_outcome(repeat: int, phase: str, focus: str) -> str | None:
    metrics = EXPERIMENT / "runs" / CASE / f"r{repeat}-frozen" / phase_dir_name(phase, focus) / "metrics.yaml"
    if not metrics.is_file():
        return None
    data = yaml.safe_load(metrics.read_text(encoding="utf-8")) or {}
    return str(data.get("outcome") or "")


def live_change_status(repeat: int) -> str | None:
    root = EXPERIMENT / "work" / f"{CASE}-r{repeat}" / "docs" / "changes"
    if not root.is_dir():
        return None
    candidates = [p.parent for p in root.glob("*/change.yaml")]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: (p / "change.yaml").stat().st_mtime)
    data = yaml.safe_load((newest / "change.yaml").read_text(encoding="utf-8")) or {}
    return str(data.get("status") or "") or None


def run_repeat(repeat: int) -> None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    for phase, focus, tokens in STEPS:
        env["A09_ANALYZE_FOCUS"] = focus
        env["A09_MAX_TOKENS"] = tokens
        print(f"--- {CASE} r{repeat} {phase} focus={focus} max_tokens={tokens} ---", flush=True)
        proc = subprocess.run(
            [sys.executable, str(HARNESS), "--case", CASE, "--repeat", str(repeat), "--phase", phase, "--tag", "frozen"],
            cwd=str(ROOT),
            env=env,
        )
        if proc.returncode != 0:
            raise SystemExit(proc.returncode)
        outcome = last_outcome(repeat, phase, focus)
        status = live_change_status(repeat)
        print(f"outcome={outcome} change_status={status}", flush=True)
        if outcome in {"fail", "timeout", "blocked-on-decision"}:
            print(f"stop r{repeat} at {phase}: {outcome}", flush=True)
            return
        if status in TERMINAL:
            print(f"stop r{repeat} at {phase}: terminal {status}", flush=True)
            return
    print(f"r{repeat} completed all sequenced phases", flush=True)


def main() -> int:
    repeats = [int(x) for x in (sys.argv[1:] or ["1", "2", "3"])]
    for repeat in repeats:
        run_repeat(repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
