"""A13-02 R1 sequencer: n=1 P0 holdout on current-branch skills. Does not patch extras."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness" / "run_case.py"
EXPERIMENT = Path(__file__).resolve().parent
TAG = "a13"


def phase_dir_name(phase: str, focus: str, task: str | None = None) -> str:
    if phase == "analyze":
        return f"analyze-{focus}"
    if phase in {"target", "implement"}:
        return f"{phase}-{task or 'TASK-001'}"
    return phase


def last_metrics(case: str, repeat: int, phase: str, focus: str, task: str | None = None) -> dict:
    metrics = (
        EXPERIMENT
        / "runs"
        / case
        / f"r{repeat}-{TAG}"
        / phase_dir_name(phase, focus, task)
        / "metrics.yaml"
    )
    if not metrics.is_file():
        return {}
    return yaml.safe_load(metrics.read_text(encoding="utf-8")) or {}


def last_outcome(case: str, repeat: int, phase: str, focus: str, task: str | None = None) -> str | None:
    data = last_metrics(case, repeat, phase, focus, task)
    out = data.get("outcome")
    return str(out) if out else None


def last_gate_text(case: str, repeat: int, phase: str, focus: str, task: str | None = None) -> str:
    run = EXPERIMENT / "runs" / case / f"r{repeat}-{TAG}" / phase_dir_name(phase, focus, task)
    texts = []
    for p in sorted(run.glob("attempt*-gate.txt")):
        texts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n---\n".join(texts)


def run_step(
    case: str,
    repeat: int,
    phase: str,
    focus: str,
    tokens: str,
    task: str | None = None,
) -> str | None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    env["A09_ANALYZE_FOCUS"] = focus
    env["A09_MAX_TOKENS"] = tokens
    if task:
        env["A09_TASK"] = task
    print(f"--- {case} r{repeat} {phase} focus={focus} task={task or '-'} max_tokens={tokens} ---", flush=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "--case",
            case,
            "--repeat",
            str(repeat),
            "--phase",
            phase,
            "--tag",
            TAG,
        ],
        cwd=str(ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    outcome = last_outcome(case, repeat, phase, focus, task)
    print(f"outcome={outcome}", flush=True)
    return outcome


def product_dir(case: str, repeat: int) -> Path:
    return EXPERIMENT / "work" / f"{case}-r{repeat}"


def live_spec_notes(case: str, repeat: int) -> dict:
    product = product_dir(case, repeat)
    paths = {
        "usage_stats": product / "docs" / "spec" / "monitoring" / "usage_stats.md",
        "rate_policy": product / "docs" / "spec" / "security" / "rate_policy.md",
        "ratelimit": product / "docs" / "spec" / "security" / "ratelimit.md",
        "catalog": product / "docs" / "spec" / "_capabilities.yaml",
    }
    return {k: p.is_file() and p.stat().st_size > 0 for k, p in paths.items()}


def run_case_until(case: str, steps: list[tuple], stop_outcomes: set[str]) -> None:
    for phase, focus, tokens, task in steps:
        outcome = run_step(case, 1, phase, focus, tokens, task)
        if outcome in stop_outcomes:
            print(f"stop {case} at {phase}: {outcome}", flush=True)
            return


def main() -> int:
    stop = {"fail", "timeout", "blocked-on-decision"}
    print("A13-02 sequencer start", flush=True)
    run_case_until(
        "S05",
        [
            ("intake", "routing", "2048", None),
            ("analyze", "routing", "2048", None),
            ("analyze", "slices", "4096", None),
            ("analyze", "coverage", "2048", None),
            ("specify", "routing", "4096", None),
        ],
        stop,
    )
    print("S05 live", live_spec_notes("S05", 1), flush=True)
    run_case_until(
        "S01",
        [
            ("intake", "routing", "2048", None),
            ("analyze", "routing", "2048", None),
            ("analyze", "slices", "4096", None),
            ("analyze", "coverage", "2048", None),
            ("specify", "routing", "4096", None),
        ],
        stop,
    )
    print("S01 live", live_spec_notes("S01", 1), flush=True)
    run_case_until(
        "S02",
        [
            ("intake", "routing", "2048", None),
            ("analyze", "routing", "2048", None),
            ("analyze", "slices", "4096", None),
            ("analyze", "coverage", "2048", None),
            ("specify", "routing", "4096", None),
            ("decompose", "routing", "4096", None),
        ],
        stop,
    )
    if last_outcome("S02", 1, "decompose", "routing") == "pass":
        run_step("S02", 1, "target", "routing", "2048", "TASK-001")
        run_step("S02", 1, "target", "routing", "2048", "TASK-002")
    else:
        print("skip S02 Target: decompose did not pass", flush=True)
    run_case_until(
        "S04",
        [
            ("intake", "routing", "2048", None),
            ("analyze", "routing", "2048", None),
        ],
        stop,
    )
    print("A13-02 sequencer done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
