"""Sequence S10 holdout with interrupt after Red, resume, then re-slice.

Does not change prompts. Follow-up text is an evaluator action, not a prompt extra.
Oracle/hidden_suite/fault_suite stay out of the ornith prompt.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness" / "run_case.py"
CASE_MANIFEST = ROOT / "backlog" / "analysis" / "experiments" / "cases" / "S10" / "manifest.yaml"
EXPERIMENT = Path(__file__).resolve().parent
CASE = "S10"
PRE_INTERRUPT = [
    ("intake", "routing", "2048"),
    ("analyze", "routing", "2048"),
    ("analyze", "slices", "4096"),
    ("analyze", "coverage", "2048"),
    ("specify", "routing", "4096"),
    ("decompose", "routing", "4096"),
    ("target", "routing", "2048"),
]
RESUME = [
    ("implement", "routing", "4096"),
]
RESLICE = [
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


def follow_up_text() -> str:
    data = yaml.safe_load(CASE_MANIFEST.read_text(encoding="utf-8")) or {}
    return str((data.get("reslice_protocol") or {}).get("follow_up_input") or "").strip()


def phase_dir_name(phase: str, focus: str, task: str = "TASK-001") -> str:
    if phase == "analyze":
        return f"analyze-{focus}"
    if phase in {"target", "implement"}:
        return f"{phase}-{task}"
    return phase


def last_outcome(repeat: int, phase: str, focus: str, tag: str, task: str = "TASK-001") -> str | None:
    metrics = (
        EXPERIMENT
        / "runs"
        / CASE
        / f"r{repeat}-{tag}"
        / phase_dir_name(phase, focus, task)
        / "metrics.yaml"
    )
    if not metrics.is_file():
        return None
    data = yaml.safe_load(metrics.read_text(encoding="utf-8")) or {}
    return str(data.get("outcome") or "")


def product_dir(repeat: int) -> Path:
    return EXPERIMENT / "work" / f"{CASE}-r{repeat}"


def live_changes(repeat: int) -> list[Path]:
    root = product_dir(repeat) / "docs" / "changes"
    if not root.is_dir():
        return []
    return [p.parent for p in root.glob("*/change.yaml")]


def newest_change(repeat: int) -> Path | None:
    candidates = live_changes(repeat)
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p / "change.yaml").stat().st_mtime)


def write_checkpoint(repeat: int, stage: str) -> Path:
    change = newest_change(repeat)
    red = []
    status = ""
    change_id = ""
    if change is not None:
        change_id = change.name
        data = yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8")) or {}
        status = str(data.get("status") or "")
        red_dir = change / "evidence" / "red"
        if red_dir.is_dir():
            red = sorted(p.stem for p in red_dir.glob("*.yaml"))
    dest = EXPERIMENT / "runs" / CASE / f"r{repeat}-frozen" / f"{stage}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.safe_dump(
            {
                "stage": stage,
                "change_id": change_id,
                "change_ids": [p.name for p in live_changes(repeat)],
                "change_status": status,
                "red_evidence": red,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return dest


def inject_follow_up(repeat: int) -> None:
    text = follow_up_text()
    product = product_dir(repeat)
    intake = product / "docs" / "intake" / "S10-followup.md"
    intake.parent.mkdir(parents=True, exist_ok=True)
    intake.write_text("# Follow-up from user\n\n" + text + "\n", encoding="utf-8")
    change = newest_change(repeat)
    if change is None:
        return
    request = change / "request.md"
    if not request.is_file():
        return
    body = request.read_text(encoding="utf-8")
    marker = "## Follow-up from user"
    if marker in body:
        return
    request.write_text(body.rstrip() + "\n\n" + marker + "\n\n" + text + "\n", encoding="utf-8")


def pick_task(repeat: int) -> str:
    change = newest_change(repeat)
    if change is None:
        return "TASK-001"
    tasks_dir = change / "tasks"
    if not tasks_dir.is_dir():
        return "TASK-001"
    pending: list[str] = []
    implemented: list[str] = []
    for path in sorted(tasks_dir.glob("TASK-*.md")):
        raw = path.read_text(encoding="utf-8")
        meta = {}
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
        task_id = str(meta.get("id") or path.stem.split("-")[0] + "-" + path.stem.split("-")[1])
        if not task_id.startswith("TASK-"):
            continue
        status = str(meta.get("status") or "")
        if status in {"implemented", "verified"}:
            implemented.append(task_id)
        elif status not in {"cancelled", "superseded"}:
            pending.append(task_id)
    if pending:
        return pending[0]
    if implemented:
        return implemented[0]
    return "TASK-001"


def run_step(repeat: int, phase: str, focus: str, tokens: str, tag: str, task: str) -> str | None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    env["A09_ANALYZE_FOCUS"] = focus
    env["A09_MAX_TOKENS"] = tokens
    env["A09_TASK"] = task
    print(f"--- {CASE} r{repeat} {phase} focus={focus} max_tokens={tokens} tag={tag} task={task} ---", flush=True)
    proc = subprocess.run(
        [sys.executable, str(HARNESS), "--case", CASE, "--repeat", str(repeat), "--phase", phase, "--tag", tag],
        cwd=str(ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    outcome = last_outcome(repeat, phase, focus, tag, task)
    print(f"outcome={outcome}", flush=True)
    return outcome


def run_repeat(repeat: int) -> None:
    task = "TASK-001"
    for phase, focus, tokens in PRE_INTERRUPT:
        outcome = run_step(repeat, phase, focus, tokens, "frozen", task)
        if outcome in STOP:
            print(f"stop r{repeat} at {phase}: {outcome}", flush=True)
            return
        if phase == "target":
            path = write_checkpoint(repeat, "interrupt-checkpoint")
            print(f"interrupt after target; checkpoint={path.as_posix()}", flush=True)
    print(f"resume r{repeat} implement on same Change package", flush=True)
    outcome = run_step(repeat, "implement", "routing", "4096", "frozen", task)
    write_checkpoint(repeat, "resume-checkpoint")
    if outcome in STOP:
        print(f"stop r{repeat} at resume implement: {outcome}", flush=True)
        return
    inject_follow_up(repeat)
    print(f"injected follow-up; start re-slice r{repeat}", flush=True)
    for phase, focus, tokens in RESLICE:
        if phase in {"target", "implement"}:
            task = pick_task(repeat)
        outcome = run_step(repeat, phase, focus, tokens, "frozen-reslice", task)
        if outcome in STOP:
            print(f"stop r{repeat} at reslice {phase}: {outcome}", flush=True)
            return
    print(f"r{repeat} completed interrupt/resume/re-slice", flush=True)


def main() -> int:
    repeats = [int(x) for x in (sys.argv[1:] or ["1", "2", "3"])]
    for repeat in repeats:
        run_repeat(repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
