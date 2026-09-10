"""A13-04 R3: S11 n=1 two-Change series. Does not patch extras. Analog/S10 not this run."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness" / "run_case.py"
CASE_MANIFEST = ROOT / "backlog" / "analysis" / "experiments" / "cases" / "S11" / "manifest.yaml"
EXPERIMENT = Path(__file__).resolve().parent
CASE = "S11"
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


def case_manifest() -> dict:
    return yaml.safe_load(CASE_MANIFEST.read_text(encoding="utf-8")) or {}


def evaluator_intake_dir() -> Path:
    dest = EXPERIMENT / "evaluator-intake"
    dest.mkdir(parents=True, exist_ok=True)
    data = case_manifest()
    protocol = data.get("protocol") or {}
    (dest / "CHG-A.md").write_text(
        "# Evaluator intake CHG-A\n\n" + str((protocol.get("phase_a") or {}).get("input") or "").strip() + "\n",
        encoding="utf-8",
    )
    (dest / "CHG-C.md").write_text(
        "# Evaluator intake CHG-C\n\n" + str((protocol.get("phase_c") or {}).get("input") or "").strip() + "\n",
        encoding="utf-8",
    )
    return dest


def phase_dir_name(phase: str, focus: str, task: str = "TASK-001") -> str:
    if phase == "analyze":
        return f"analyze-{focus}"
    if phase in {"target", "implement"}:
        return f"{phase}-{task}"
    return phase


def last_outcome(repeat: int, phase: str, focus: str, tag: str, task: str = "TASK-001") -> str | None:
    metrics = (
        EXPERIMENT / "runs" / CASE / f"r{repeat}-{tag}" / phase_dir_name(phase, focus, task) / "metrics.yaml"
    )
    if not metrics.is_file():
        return None
    data = yaml.safe_load(metrics.read_text(encoding="utf-8")) or {}
    return str(data.get("outcome") or "")


def product_dir(repeat: int, suffix: str) -> Path:
    return EXPERIMENT / "work" / f"{CASE}-r{repeat}{suffix}"


def write_stage(repeat: int, tag: str, name: str, payload: dict) -> Path:
    dest = EXPERIMENT / "runs" / CASE / f"r{repeat}-{tag}" / f"{name}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return dest


def has_green(repeat: int, suffix: str) -> bool:
    root = product_dir(repeat, suffix) / "docs" / "changes"
    if not root.is_dir():
        return False
    return any(root.glob("*/evidence/green/*.yaml"))


def spec_has_burst(repeat: int, suffix: str) -> bool:
    spec = product_dir(repeat, suffix) / "docs" / "spec" / "security" / "ratelimit.md"
    if not spec.is_file():
        return False
    return "burst_allowance" in spec.read_text(encoding="utf-8")


def run_step(
    repeat: int,
    phase: str,
    focus: str,
    tokens: str,
    tag: str,
    suffix: str,
    intake_override: str | None = None,
) -> str | None:
    env = os.environ.copy()
    env["DELTAFUSE_LLM_URL"] = env.get("DELTAFUSE_LLM_URL") or "http://127.0.0.1:1240/v1/chat/completions"
    env["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
    env["A09_ANALYZE_FOCUS"] = focus
    env["A09_MAX_TOKENS"] = tokens
    env["A09_TASK"] = "TASK-001"
    env["A09_WORK_SUFFIX"] = suffix
    if intake_override:
        env["A09_INTAKE_OVERRIDE"] = intake_override
    else:
        env.pop("A09_INTAKE_OVERRIDE", None)
    print(
        f"--- {CASE} r{repeat} {phase} focus={focus} max_tokens={tokens} tag={tag} suffix={suffix or '-'} ---",
        flush=True,
    )
    proc = subprocess.run(
        [sys.executable, str(HARNESS), "--case", CASE, "--repeat", str(repeat), "--phase", phase, "--tag", tag],
        cwd=str(ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    outcome = last_outcome(repeat, phase, focus, tag)
    print(f"outcome={outcome}", flush=True)
    return outcome


def run_change(repeat: int, tag: str, suffix: str, intake_override: str | None) -> str | None:
    stopped = None
    for phase, focus, tokens in STEPS:
        outcome = run_step(repeat, phase, focus, tokens, tag, suffix, intake_override)
        if outcome in STOP:
            print(f"stop r{repeat} {tag} at {phase}: {outcome}", flush=True)
            return outcome
        stopped = outcome
    print(f"r{repeat} {tag} completed sequenced phases", flush=True)
    return stopped


def merge_a_into_b(repeat: int) -> None:
    src = product_dir(repeat, "-chga")
    dest = product_dir(repeat, "-chgb")
    copied = []
    spec_paths = ["docs/spec/security/ratelimit.md", "docs/spec/_capabilities.yaml"]
    code_paths = ["src/ratelimit/limiter.py", "tests/test_limiter.py"]
    for rel in spec_paths:
        a_path = src / rel
        if not a_path.is_file():
            continue
        b_path = dest / rel
        b_path.parent.mkdir(parents=True, exist_ok=True)
        b_path.write_text(a_path.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(rel)
    a_limiter = src / "src/ratelimit/limiter.py"
    if a_limiter.is_file() and "burst_allowance" in a_limiter.read_text(encoding="utf-8"):
        for rel in code_paths:
            a_path = src / rel
            if not a_path.is_file():
                continue
            b_path = dest / rel
            b_path.parent.mkdir(parents=True, exist_ok=True)
            b_path.write_text(a_path.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(rel)
    write_stage(
        repeat,
        "a13-merge",
        "merge-checkpoint",
        {"copied": copied, "burst_in_b_spec": spec_has_burst(repeat, "-chgb")},
    )


def prepare_chgc(repeat: int, deletion_intake: Path) -> None:
    src = product_dir(repeat, "-chga")
    dest = product_dir(repeat, "-chgc")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    changes = dest / "docs" / "changes"
    if changes.is_dir():
        for child in changes.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    intake = dest / "docs" / "intake" / f"{CASE}.md"
    intake.parent.mkdir(parents=True, exist_ok=True)
    intake.write_text(deletion_intake.read_text(encoding="utf-8"), encoding="utf-8")


def run_repeat(repeat: int) -> None:
    intakes = evaluator_intake_dir()
    chga_intake = str(intakes / "CHG-A.md")
    print(f"=== S11 r{repeat} CHG-B (input.md, window stats) ===", flush=True)
    run_change(repeat, "a13-chgb", "-chgb", None)
    print(f"=== S11 r{repeat} CHG-A (evaluator burst_allowance) ===", flush=True)
    run_change(repeat, "a13-chga", "-chga", chga_intake)
    a_specified = last_outcome(repeat, "specify", "routing", "a13-chga") == "pass"
    if has_green(repeat, "-chgb") and a_specified and spec_has_burst(repeat, "-chga"):
        print(f"=== S11 r{repeat} merge CHG-A into CHG-B ===", flush=True)
        merge_a_into_b(repeat)
        outcome = run_step(repeat, "verify", "routing", "2048", "a13-merge", "-chgb")
        if outcome in STOP:
            print(f"stop r{repeat} merge verify: {outcome}", flush=True)
    else:
        print(f"skip r{repeat} merge: need CHG-B Green, CHG-A Specify pass, and burst in spec", flush=True)
    if a_specified and spec_has_burst(repeat, "-chga"):
        print(f"=== S11 r{repeat} CHG-C (delete burst) ===", flush=True)
        prepare_chgc(repeat, intakes / "CHG-C.md")
        run_change(repeat, "a13-chgc", "-chgc", None)
    else:
        print(f"skip r{repeat} CHG-C: CHG-A did not Specify burst", flush=True)
    print(f"r{repeat} S11 protocol finished", flush=True)


def main() -> int:
    print("A13-04 sequencer start", flush=True)
    evaluator_intake_dir()
    run_repeat(1)
    print("A13-04 sequencer done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
