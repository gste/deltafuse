"""Sequence S12 holdout. Full adversarial input.md; does not change prompts."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness" / "run_case.py"
EXPERIMENT = Path(__file__).resolve().parent
CASE = "S12"
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
STOP = {"fail", "timeout", "blocked-on-decision"}


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


def run_repeat(repeat: int) -> None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    env.pop("A09_INTAKE_OVERRIDE", None)
    env.pop("A09_WORK_SUFFIX", None)
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
        print(f"outcome={outcome}", flush=True)
        if outcome in STOP:
            print(f"stop r{repeat} at {phase}: {outcome}", flush=True)
            return
    print(f"r{repeat} completed all sequenced phases", flush=True)


def main() -> int:
    repeats = [int(x) for x in (sys.argv[1:] or ["1", "2", "3"])]
    for repeat in repeats:
        run_repeat(repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
