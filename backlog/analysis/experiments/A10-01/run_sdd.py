"""Minimal SDD arm for A10-01. Reuses A09 LLM client/seed; does not change DF prompts."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
A09_HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness"
EXPERIMENT = Path(__file__).resolve().parent
CASES = ROOT / "backlog" / "analysis" / "experiments" / "cases"
SDD_PROMPT = (EXPERIMENT / "prompts" / "sdd.md").read_text(encoding="utf-8")

os.environ.setdefault("DELTAFUSE_LLM_URL", "http://127.0.0.1:1240/v1/chat/completions")
sys.path.insert(0, str(A09_HARNESS))
import run_case as a09  # noqa: E402

WRAPPER = """/no_think
You execute exactly one workflow step on a product repository.
Do not write a chain-of-thought. Put the JSON in the assistant content immediately.
Return ONLY a JSON object. No markdown fences, no prose outside JSON.
Shape:
{"files":[{"path":"relative/from/product/root","content":"full file text"}],"status":"continue","notes":"short"}
Each files[] item is its own object with keys path and content.
Write only paths listed under allowed_write. Do not git push.
"""

STEPS = [
    ("spec", 4096),
    ("task", 2048),
    ("implement", 4096),
    ("review", 4096),
]
STOP = {"fail", "timeout"}
ALLOWED = {
    "S02": {
        "spec": [
            "docs/spec/security/ratelimit.md",
            "docs/spec/_capabilities.yaml",
        ],
        "task": ["TASK.md"],
        "implement": [
            "src/ratelimit/limiter.py",
            "src/ratelimit/__init__.py",
            "tests/test_limiter.py",
        ],
        "review": [
            "src/ratelimit/limiter.py",
            "src/ratelimit/__init__.py",
            "tests/test_limiter.py",
            "docs/spec/security/ratelimit.md",
            "TASK.md",
        ],
    },
    "S05": {
        "spec": [
            "docs/spec/security/ratelimit.md",
            "docs/spec/monitoring/usage_stats.md",
            "docs/spec/security/rate_policy.md",
            "docs/spec/_capabilities.yaml",
        ],
        "task": ["TASK.md"],
        "implement": [
            "src/ratelimit/limiter.py",
            "src/ratelimit/stats.py",
            "src/ratelimit/policy.py",
            "src/ratelimit/__init__.py",
            "tests/test_limiter.py",
            "tests/test_stats.py",
            "tests/test_policy.py",
            "tests/test_integration_stats_policy.py",
        ],
        "review": [
            "src/ratelimit/limiter.py",
            "src/ratelimit/stats.py",
            "src/ratelimit/policy.py",
            "src/ratelimit/__init__.py",
            "tests/test_limiter.py",
            "tests/test_stats.py",
            "tests/test_policy.py",
            "tests/test_integration_stats_policy.py",
            "docs/spec/monitoring/usage_stats.md",
            "docs/spec/security/rate_policy.md",
            "TASK.md",
        ],
    },
}


def product_dir(case_id: str, repeat: int) -> Path:
    return EXPERIMENT / "work" / f"{case_id}-sdd-r{repeat}"


def run_dir(case_id: str, repeat: int, step: str) -> Path:
    d = EXPERIMENT / "runs" / case_id / f"r{repeat}-sdd" / step
    d.mkdir(parents=True, exist_ok=True)
    return d


def seed(case_id: str, repeat: int) -> Path:
    product = product_dir(case_id, repeat)
    if product.exists():
        shutil.rmtree(product)
    product.mkdir(parents=True)
    a09.seed_ratelimit_product(product)
    intake = (CASES / case_id / "input.md").read_text(encoding="utf-8")
    (product / "docs" / "request.md").write_text(intake, encoding="utf-8")
    return product


def pytest_product(product: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short"],
        cwd=product,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def spec_ok(case_id: str, product: Path) -> tuple[bool, str]:
    if case_id == "S02":
        text = (product / "docs/spec/security/ratelimit.md").read_text(encoding="utf-8")
        if "penalty" in text.lower() or "penalty_seconds" in text:
            return True, "spec mentions penalty"
        return False, "ratelimit.md has no penalty"
    missing = []
    for rel in (
        "docs/spec/monitoring/usage_stats.md",
        "docs/spec/security/rate_policy.md",
    ):
        if not (product / rel).is_file():
            missing.append(rel)
    if missing:
        return False, "missing " + ", ".join(missing)
    return True, "usage_stats and rate_policy present"


def task_ok(product: Path) -> tuple[bool, str]:
    p = product / "TASK.md"
    if not p.is_file() or len(p.read_text(encoding="utf-8").strip()) < 40:
        return False, "TASK.md missing or too short"
    return True, "TASK.md present"


def implement_ok(case_id: str, product: Path) -> tuple[bool, str]:
    limiter = (product / "src/ratelimit/limiter.py").read_text(encoding="utf-8")
    if case_id == "S02":
        if "penalty_seconds" in limiter:
            return True, "penalty_seconds in limiter"
        return False, "limiter.py has no penalty_seconds"
    stats = product / "src/ratelimit/stats.py"
    policy = product / "src/ratelimit/policy.py"
    text = limiter
    if stats.is_file():
        text += stats.read_text(encoding="utf-8")
    if policy.is_file():
        text += policy.read_text(encoding="utf-8")
    if "get_stats" in text or stats.is_file():
        if "blocked_until" in text or policy.is_file() or "rate_policy" in text.lower():
            return True, "stats/policy artifacts present"
        return True, "get_stats present (policy weak)"
    return False, "no stats.py / get_stats"


def step_ok(case_id: str, step: str, product: Path) -> tuple[bool, str]:
    if step == "spec":
        return spec_ok(case_id, product)
    if step == "task":
        return task_ok(product)
    if step == "implement":
        return implement_ok(case_id, product)
    code, log = pytest_product(product)
    if code == 0:
        return True, "pytest tests/ pass"
    return False, log[-2000:]


def build_messages(case_id: str, product: Path, step: str, extra: str | None) -> list[dict[str, str]]:
    request = (product / "docs/request.md").read_text(encoding="utf-8")
    spec = (product / "docs/spec/security/ratelimit.md").read_text(encoding="utf-8")
    limiter = (product / "src/ratelimit/limiter.py").read_text(encoding="utf-8")
    tests = (product / "tests/test_limiter.py").read_text(encoding="utf-8")
    caps = (product / "docs/spec/_capabilities.yaml").read_text(encoding="utf-8")
    extra_files = []
    for rel in (
        "TASK.md",
        "docs/spec/monitoring/usage_stats.md",
        "docs/spec/security/rate_policy.md",
        "src/ratelimit/stats.py",
        "src/ratelimit/policy.py",
        "tests/test_stats.py",
        "tests/test_policy.py",
        "tests/test_integration_stats_policy.py",
    ):
        p = product / rel
        if p.is_file():
            extra_files.append(f"### {rel}\n{p.read_text(encoding='utf-8')}")
    extra_block = "\n\n".join(extra_files)
    err = f"\nPrevious attempt errors:\n{extra}\n" if extra else ""
    user = (
        f"step: {step}\ncase: {case_id}\nallowed_write:\n"
        + "\n".join(f"- {p}" for p in ALLOWED[case_id][step])
        + err
        + "\n### docs/request.md\n"
        + request
        + "\n### docs/spec/_capabilities.yaml\n"
        + caps
        + "\n### docs/spec/security/ratelimit.md\n"
        + spec
        + "\n### src/ratelimit/limiter.py\n"
        + limiter
        + "\n### tests/test_limiter.py\n"
        + tests
        + ("\n" + extra_block if extra_block else "")
    )
    return [
        {"role": "system", "content": WRAPPER + "\n\n" + SDD_PROMPT},
        {"role": "user", "content": user},
    ]


def run_step(case_id: str, repeat: int, step: str, max_tokens: int) -> str:
    product = product_dir(case_id, repeat)
    out = run_dir(case_id, repeat, step)
    extra = None
    attempts: list[dict] = []
    a09.MAX_TOKENS = max_tokens
    for n in range(1, 4):
        messages = build_messages(case_id, product, step, extra)
        prompt_txt = "\n\n".join(m["content"] for m in messages)
        (out / f"attempt{n}-prompt.txt").write_text(prompt_txt, encoding="utf-8")
        t0 = time.perf_counter()
        try:
            result = a09.call_llm(messages, out / f"attempt{n}-response.json")
        except Exception as exc:
            attempts.append({"attempt": n, "error": str(exc), "elapsed_s": time.perf_counter() - t0})
            extra = str(exc)
            continue
        parse_error = None
        written: list[str] = []
        try:
            payload = a09.parse_files_payload(result.get("content") or "")
            written = a09.apply_files(product, payload)
        except Exception as exc:
            parse_error = str(exc)
            extra = str(exc)
        ok, note = step_ok(case_id, step, product)
        (out / f"attempt{n}-gate.txt").write_text(note, encoding="utf-8")
        attempts.append(
            {
                "attempt": n,
                "prompt_chars": len(prompt_txt),
                "ttft_s": result.get("ttft_s"),
                "elapsed_s": result.get("elapsed_s"),
                "finish_reason": result.get("finish_reason"),
                "parse_error": parse_error,
                "written": written,
                "ok": ok,
                "note": note[:500],
            }
        )
        if ok and parse_error is None:
            (out / "metrics.yaml").write_text(
                yaml.safe_dump({"outcome": "pass", "attempts": attempts}, sort_keys=False),
                encoding="utf-8",
            )
            return "pass"
        extra = (extra or "") + "\n" + note
    (out / "metrics.yaml").write_text(
        yaml.safe_dump({"outcome": "fail", "attempts": attempts}, sort_keys=False),
        encoding="utf-8",
    )
    return "fail"


def run_repeat(case_id: str, repeat: int) -> None:
    a09.confirm_runtime()
    seed(case_id, repeat)
    for step, tokens in STEPS:
        print(f"--- {case_id} sdd r{repeat} {step} max_tokens={tokens} ---", flush=True)
        outcome = run_step(case_id, repeat, step, tokens)
        print(f"outcome={outcome}", flush=True)
        if outcome in STOP:
            print(f"stop {case_id} r{repeat} at {step}", flush=True)
            return
    print(f"{case_id} r{repeat} sdd completed", flush=True)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        pairs = [("S02", 1), ("S02", 2), ("S02", 3), ("S05", 1), ("S05", 2), ("S05", 3)]
    else:
        pairs = [(args[0], int(args[1]))]
    for case_id, repeat in pairs:
        run_repeat(case_id, repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
