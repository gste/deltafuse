"""A13-03 R2 sequencer: n=1 docs/ops + Analyze. Does not patch extras for 2 slices."""
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


def last_metrics(case: str, phase: str, focus: str, task: str | None = None) -> dict:
    metrics = (
        EXPERIMENT / "runs" / case / f"r1-{TAG}" / phase_dir_name(phase, focus, task) / "metrics.yaml"
    )
    if not metrics.is_file():
        return {}
    return yaml.safe_load(metrics.read_text(encoding="utf-8")) or {}


def last_outcome(case: str, phase: str, focus: str, task: str | None = None) -> str | None:
    data = last_metrics(case, phase, focus, task)
    out = data.get("outcome")
    return str(out) if out else None


def run_step(case: str, phase: str, focus: str, tokens: str, task: str | None = None) -> str | None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    env["A09_ANALYZE_FOCUS"] = focus
    env["A09_MAX_TOKENS"] = tokens
    if task:
        env["A09_TASK"] = task
    print(f"--- {case} r1 {phase} focus={focus} task={task or '-'} max_tokens={tokens} ---", flush=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "--case",
            case,
            "--repeat",
            "1",
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
    outcome = last_outcome(case, phase, focus, task)
    print(f"outcome={outcome}", flush=True)
    return outcome


def product_dir(case: str) -> Path:
    return EXPERIMENT / "work" / f"{case}-r1"


def find_chg(case: str) -> Path | None:
    changes = product_dir(case) / "docs" / "changes"
    if not changes.is_dir():
        return None
    dirs = [p for p in changes.iterdir() if p.is_dir() and p.name.startswith("CHG-")]
    return dirs[0] if dirs else None


def case_snapshot(case: str) -> dict:
    product = product_dir(case)
    chg = find_chg(case)
    routing = {}
    if chg and (chg / "routing.yaml").is_file():
        routing = yaml.safe_load((chg / "routing.yaml").read_text(encoding="utf-8")) or {}
    slices = []
    if chg and (chg / "slices").is_dir():
        slices = sorted(p.name for p in (chg / "slices").glob("SLICE-*.md"))
    limiter = product / "src" / "ratelimit" / "limiter.py"
    spec = product / "docs" / "spec" / "security" / "ratelimit.md"
    coverage = {}
    if chg and (chg / "coverage.yaml").is_file():
        coverage = yaml.safe_load((chg / "coverage.yaml").read_text(encoding="utf-8")) or {}
    claims = list((coverage.get("claims") or {}).keys()) if isinstance(coverage, dict) else []
    analysis = bool(chg and (chg / "analysis.md").is_file())
    return {
        "route": routing.get("route"),
        "primary": routing.get("primary_capability"),
        "schema_version": "schema_version" in routing if isinstance(routing, dict) else None,
        "slices": slices,
        "limiter_exists": limiter.is_file(),
        "ratelimit_spec": spec.is_file(),
        "analysis_md": analysis,
        "claim_ids": claims,
        "src_writes": last_metrics(case, "implement", "routing").get("attempts"),
    }


def run_case_until(case: str, steps: list[tuple], stop_outcomes: set[str]) -> None:
    for phase, focus, tokens, task in steps:
        outcome = run_step(case, phase, focus, tokens, task)
        if outcome in stop_outcomes:
            print(f"stop {case} at {phase}: {outcome}", flush=True)
            return


def main() -> int:
    stop = {"fail", "timeout", "blocked-on-decision"}
    print("A13-03 sequencer start", flush=True)
    code_steps = [
        ("intake", "routing", "2048", None),
        ("analyze", "routing", "2048", None),
        ("analyze", "slices", "4096", None),
        ("analyze", "coverage", "2048", None),
        ("specify", "routing", "4096", None),
        ("decompose", "routing", "4096", None),
        ("target", "routing", "2048", "TASK-001"),
        ("implement", "routing", "4096", "TASK-001"),
    ]
    analyze_steps = [
        ("intake", "routing", "2048", None),
        ("analyze", "routing", "2048", None),
        ("analyze", "slices", "4096", None),
        ("analyze", "coverage", "2048", None),
    ]
    run_case_until("S03", code_steps, stop)
    print("S03 snap", case_snapshot("S03"), flush=True)
    run_case_until("S08b", code_steps, stop)
    print("S08b snap", case_snapshot("S08b"), flush=True)
    run_case_until("S08c", code_steps, stop)
    print("S08c snap", case_snapshot("S08c"), flush=True)
    run_case_until("S05", analyze_steps, stop)
    print("S05 snap", case_snapshot("S05"), flush=True)
    run_case_until("S02", analyze_steps, stop)
    print("S02 snap", case_snapshot("S02"), flush=True)
    print("A13-03 sequencer done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
