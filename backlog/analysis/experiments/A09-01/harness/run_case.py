"""A09-01 calibration harness: one DeltaFuse phase per ornith call.

Does not modify framework contracts. Isolated product under experiments/A09-01/work/.
Oracle/hidden_suite/fault_suite must not be attached to the model prompt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK = Path(__file__).resolve().parents[5]
EXPERIMENT = Path(__file__).resolve().parents[1]
CASES = FRAMEWORK / "backlog" / "analysis" / "experiments" / "cases"
SKILLS = {
    "intake": FRAMEWORK / "process" / "skills" / "intake" / "SKILL.md",
    "analyze": FRAMEWORK / "process" / "skills" / "analyze-change" / "SKILL.md",
    "specify": FRAMEWORK / "process" / "skills" / "specify-change" / "SKILL.md",
    "decompose": FRAMEWORK / "process" / "skills" / "decompose-change" / "SKILL.md",
    "target": FRAMEWORK / "process" / "skills" / "target-task" / "SKILL.md",
    "implement": FRAMEWORK / "process" / "skills" / "implement-task" / "SKILL.md",
    "verify": FRAMEWORK / "process" / "skills" / "verify-change" / "SKILL.md",
}
GATES = {
    "intake": "intake",
    "analyze": "analyzed",
    "specify": "specified",
    "decompose": "decomposed",
    "target": "targeting",
    "implement": "implemented",
    "verify": "converged",
}
PHASE_ORDER = ["intake", "analyze", "specify", "decompose", "target", "implement", "verify"]
ENDPOINT = (
    os.environ.get("DELTAFUSE_LLM_URL")
    or os.environ.get("DELTAFUSE_LMSTUDIO_URL")
    or "http://127.0.0.1:1240/v1/chat/completions"
)
MODEL = os.environ.get("A09_MODEL", "ornith-1.5-35b-a3b")
# Frozen profile (thinking off): routing/intake fit in 300s; full dump/16k prefill use 600s.
TIMEOUT_S = int(os.environ.get("A09_LLM_TIMEOUT_S", "300"))
MAX_RETRIES = int(os.environ.get("A09_MAX_RETRIES", "3"))
MAX_TOKENS = int(os.environ.get("A09_MAX_TOKENS", "2048"))
ENABLE_THINKING = os.environ.get("A09_ENABLE_THINKING", "0") == "1"
ANALYZE_FOCUS = os.environ.get("A09_ANALYZE_FOCUS", "routing")
TEMPERATURE = 0.1
TOP_P = 0.9
PROTOCOL_TIMEOUT_S = 300

WRAPPER = """/no_think
You execute exactly one DeltaFuse lifecycle phase on a product repository.
Do not write a chain-of-thought. Put the JSON in the assistant content immediately.
Return ONLY a JSON object. No markdown fences, no prose outside JSON.
Shape:
{"files":[{"path":"relative/from/product/root","content":"full file text"}],"status":"continue","notes":"short"}
status must be one of: continue, blocked-on-decision, halt.
Write only paths listed under allowed_write. Do not git push, do not run destructive git, do not accept Decisions, do not invent requirements.
If the phase cannot proceed without a human Decision, set status to blocked-on-decision and still write the Decision file plus updated change.yaml.
Preserve existing file contents except the paths you intentionally change.
"""


def nvidia_smi() -> dict[str, Any]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip()
        used, total, util = [x.strip() for x in out.split(",")]
        return {"vram_used_mib": int(used), "vram_total_mib": int(total), "gpu_util_pct": int(util)}
    except Exception as exc:
        return {"error": str(exc)}


def openai_base(endpoint: str) -> str:
    url = endpoint.rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    return url.rstrip("/")


def confirm_runtime() -> dict[str, Any]:
    url = openai_base(ENDPOINT) + "/models"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ids = [m.get("id") for m in data.get("data") or [] if m.get("id")]
    if MODEL not in ids:
        raise SystemExit(f"runtime blocked: {MODEL} not in {url} ({ids})")
    return {"id": MODEL, "endpoint": ENDPOINT, "models": ids}


def call_llm(messages: list[dict[str, str]], out_path: Path) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": True,
    }
    if ENABLE_THINKING:
        payload["enable_thinking"] = True
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    ttft = None
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    usage: dict[str, Any] = {}
    finish = None
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            usage = chunk.get("usage") or usage
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content") or ""
            reason = delta.get("reasoning_content") or ""
            if ttft is None and (piece or reason):
                ttft = time.perf_counter() - t0
            if piece:
                content_parts.append(piece)
            if reason:
                reasoning_parts.append(reason)
            if choices[0].get("finish_reason"):
                finish = choices[0]["finish_reason"]
    elapsed = time.perf_counter() - t0
    result = {
        "content": "".join(content_parts),
        "reasoning_content": "".join(reasoning_parts),
        "finish_reason": finish,
        "usage": usage,
        "ttft_s": ttft,
        "elapsed_s": elapsed,
        "timeout_s": TIMEOUT_S,
    }
    out_path.write_text(json.dumps({"request": payload, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def parse_files_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model content")
    return json.loads(cleaned[start : end + 1])


def seed_ratelimit_product(product: Path) -> None:
    spec_dir = product / "docs" / "spec" / "security"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "ratelimit.md").write_text(
        "# security.ratelimit\n\n"
        "## REQ-RL-01 Capacity and refill\n"
        "TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.\n\n"
        "## REQ-RL-02 Consume\n"
        "consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.\n\n"
        "## REQ-RL-03 Unknown keys\n"
        "An unknown key MUST start at full capacity.\n\n"
        "## REQ-RL-04 is_blocked\n"
        "is_blocked(key) MUST return False for the baseline limiter (no penalty lock).\n",
        encoding="utf-8",
    )
    (product / "docs" / "spec" / "_capabilities.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "domains": {
                    "security": {
                        "summary": "Security controls",
                        "capabilities": {
                            "ratelimit": {
                                "summary": "Token-bucket rate limiter",
                                "spec": ["docs/spec/security/ratelimit.md"],
                                "code_roots": ["src/ratelimit"],
                                "test_roots": ["tests"],
                                "status": "active",
                                "type": "supporting",
                            }
                        },
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pkg = product / "src" / "ratelimit"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("from ratelimit.limiter import TokenBucketLimiter\n", encoding="utf-8")
    (pkg / "limiter.py").write_text(
        "from __future__ import annotations\n"
        "import time\n\n"
        "class TokenBucketLimiter:\n"
        "    def __init__(self, capacity: float, refill_rate: float) -> None:\n"
        "        if capacity <= 0 or refill_rate < 0:\n"
        "            raise ValueError('invalid limiter parameters')\n"
        "        self.capacity = float(capacity)\n"
        "        self.refill_rate = float(refill_rate)\n"
        "        self._buckets: dict[str, tuple[float, float]] = {}\n\n"
        "    def _refill(self, key: str) -> tuple[float, float]:\n"
        "        now = time.monotonic()\n"
        "        tokens, last = self._buckets.get(key, (self.capacity, now))\n"
        "        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)\n"
        "        self._buckets[key] = (tokens, now)\n"
        "        return self._buckets[key]\n\n"
        "    def consume(self, key: str, tokens: float) -> bool:\n"
        "        current, ts = self._refill(key)\n"
        "        if current >= tokens:\n"
        "            self._buckets[key] = (current - tokens, ts)\n"
        "            return True\n"
        "        return False\n\n"
        "    def is_blocked(self, key: str) -> bool:\n"
        "        return False\n",
        encoding="utf-8",
    )
    tests = product / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_limiter.py").write_text(
        "from ratelimit.limiter import TokenBucketLimiter\n\n"
        "def test_consume_and_reject():\n"
        "    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.0)\n"
        "    assert limiter.consume('u', 5) is True\n"
        "    assert limiter.consume('u', 1) is False\n"
        "    assert limiter.is_blocked('u') is False\n",
        encoding="utf-8",
    )
    (product / "pyproject.toml").write_text(
        "[project]\nname='ratelimit-product'\nversion='0.0.1'\n"
        "[tool.pytest.ini_options]\npythonpath=['src']\n",
        encoding="utf-8",
    )


def setup_product(case_id: str, repeat: int) -> Path:
    product = EXPERIMENT / "work" / f"{case_id}-r{repeat}"
    if product.exists():
        return product
    sys.path.insert(0, str(FRAMEWORK / "src"))
    from deltafuse.core.installer import install

    install(target_dir=product, framework_root=FRAMEWORK)
    seed_ratelimit_product(product)
    intake_src = CASES / case_id / "input.md"
    dest = product / "docs" / "intake" / f"{case_id}.md"
    dest.write_text(intake_src.read_text(encoding="utf-8"), encoding="utf-8")
    return product


def phase_context(product: Path, phase: str, case_id: str) -> list[Path]:
    files: list[Path] = [
        product / ".deltafuse" / "config.yaml",
        product / ".deltafuse" / "lock.yaml",
    ]
    if phase == "intake":
        files.append(product / "docs" / "intake" / f"{case_id}.md")
        files.append(FRAMEWORK / "process" / "schemas" / "change.schema.yaml")
    else:
        active = find_change_dir(product)
        if active:
            files.extend(sorted(p for p in active.rglob("*") if p.is_file()))
        if phase in {"analyze", "specify", "decompose", "target", "verify"}:
            catalog = product / "docs" / "spec" / "_capabilities.yaml"
            if catalog.is_file():
                files.append(catalog)
            if not (phase == "analyze" and ANALYZE_FOCUS == "routing"):
                spec = product / "docs" / "spec"
                if spec.is_dir():
                    files.extend(sorted(p for p in spec.rglob("*") if p.is_file()))
        if phase == "analyze":
            schema_names = ("routing.schema.yaml",)
            if ANALYZE_FOCUS != "routing":
                schema_names = ("routing.schema.yaml", "slice.schema.yaml", "coverage.schema.yaml", "change.schema.yaml")
            for name in schema_names:
                files.append(FRAMEWORK / "process" / "schemas" / name)
        if phase in {"target", "implement", "verify"}:
            files.extend(sorted((product / "tests").rglob("*.py")))
        if phase in {"implement", "verify"}:
            files.extend(sorted((product / "src").rglob("*.py")))
    readable = [p for p in files if p.is_file()]
    return readable[:24]


def build_messages(phase: str, product: Path, case_id: str, extra_error: str | None) -> tuple[list[dict[str, str]], int]:
    skill = SKILLS[phase].read_text(encoding="utf-8")
    ctx_files = phase_context(product, phase, case_id)
    parts = [
        f"Phase: {phase}",
        f"Product root: (relative paths below)",
        f"allowed_write: see skill and PHASE_CONTRACTS for '{phase}'",
        f"Gate to satisfy after this call: {GATES[phase]}",
    ]
    if extra_error:
        parts.append("Previous attempt failed validation:\n" + extra_error)
    if phase == "analyze" and ANALYZE_FOCUS == "routing":
        parts.append(
            "This call writes ONLY docs/changes/<id>/routing.yaml (map every CR-* to a primary capability). "
            "Do not write analysis.md, slices, or coverage.yaml."
        )
    for path in ctx_files:
        try:
            rel = path.relative_to(product).as_posix()
        except ValueError:
            rel = path.relative_to(FRAMEWORK).as_posix()
        parts.append(f"\n=== FILE {rel} ===\n{path.read_text(encoding='utf-8')}")
    user = "\n".join(parts)
    messages = [
        {"role": "system", "content": WRAPPER + "\n\n# Skill\n" + skill},
        {"role": "user", "content": user},
    ]
    prompt_chars = sum(len(m["content"]) for m in messages)
    return messages, prompt_chars


def apply_files(product: Path, payload: dict[str, Any]) -> list[str]:
    written = []
    for item in payload.get("files") or []:
        rel = item["path"].replace("\\", "/").lstrip("/")
        if ".." in Path(rel).parts:
            raise ValueError(f"path traversal: {rel}")
        dest = product / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item["content"], encoding="utf-8")
        written.append(rel)
    return written


def find_change_dir(product: Path, written: list[str] | None = None) -> Path | None:
    if written:
        for rel in written:
            posix = rel.replace("\\", "/")
            if posix.startswith("docs/changes/") and posix.count("/") >= 2:
                change_id = posix.split("/")[2]
                candidate = product / "docs" / "changes" / change_id
                if (candidate / "change.yaml").is_file():
                    return candidate
    root = product / "docs" / "changes"
    if not root.is_dir():
        return None
    candidates = [p.parent for p in root.glob("*/change.yaml")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p / "change.yaml").stat().st_mtime)


def run_gate(product: Path, phase: str, written: list[str] | None = None) -> tuple[int, str]:
    change_dir = find_change_dir(product, written=written)
    if change_dir is None:
        return 1, "no change directory"
    src = str(FRAMEWORK / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from deltafuse.core.fsm import check_gate, validate_change_package

    errors = validate_change_package(change_dir) + check_gate(change_dir, GATES[phase])
    # check_gate already includes validate_change_package; keep one call
    errors = check_gate(change_dir, GATES[phase])
    text = "\n".join(errors) if errors else "gate ok"
    return (1 if errors else 0), text


def run_phase(case_id: str, repeat: int, phase: str, tag: str = "") -> dict[str, Any]:
    product = setup_product(case_id, repeat)
    run_name = f"r{repeat}-{tag}" if tag else f"r{repeat}"
    run_dir = EXPERIMENT / "runs" / case_id / run_name / phase
    run_dir.mkdir(parents=True, exist_ok=True)
    last_error = None
    metrics: dict[str, Any] = {
        "case": case_id,
        "repeat": repeat,
        "tag": tag or None,
        "phase": phase,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "enable_thinking": ENABLE_THINKING,
        "timeout_s_used": TIMEOUT_S,
        "timeout_s_protocol": PROTOCOL_TIMEOUT_S,
        "analyze_focus": ANALYZE_FOCUS if phase == "analyze" else None,
        "attempts": [],
    }
    for attempt in range(1, MAX_RETRIES + 1):
        messages, prompt_chars = build_messages(phase, product, case_id, last_error)
        (run_dir / f"attempt{attempt}-prompt.txt").write_text(
            messages[0]["content"] + "\n\n----- USER -----\n\n" + messages[1]["content"],
            encoding="utf-8",
        )
        gpu_before = nvidia_smi()
        try:
            result = call_llm(messages, run_dir / f"attempt{attempt}-response.json")
            overflow = result.get("finish_reason") == "length"
            parse_error = None
            written: list[str] = []
            status = "halt"
            try:
                payload = parse_files_payload(result["content"])
                written = apply_files(product, payload)
                status = payload.get("status") or "continue"
            except Exception as exc:
                parse_error = str(exc)
            gate_code, gate_out = (1, "skipped") if parse_error else run_gate(product, phase, written=written)
            if (
                not parse_error
                and phase == "analyze"
                and ANALYZE_FOCUS == "routing"
            ):
                routing_written = any(
                    Path(p).name == "routing.yaml" or p.replace("\\", "/").endswith("/routing.yaml")
                    for p in written
                )
                if routing_written:
                    gate_code, gate_out = 0, "routing-only: routing.yaml written; analyzed gate deferred"
                else:
                    gate_code, gate_out = 1, "routing-only: missing routing.yaml"
            (run_dir / f"attempt{attempt}-gate.txt").write_text(gate_out, encoding="utf-8")
            attempt_row = {
                "attempt": attempt,
                "prompt_chars": prompt_chars,
                "ttft_s": result.get("ttft_s"),
                "elapsed_s": result.get("elapsed_s"),
                "usage": result.get("usage"),
                "finish_reason": result.get("finish_reason"),
                "overflow": overflow,
                "parse_error": parse_error,
                "written": written,
                "model_status": status,
                "gate_exit": gate_code,
                "gpu_before": gpu_before,
                "gpu_after": nvidia_smi(),
                "content_empty": not bool(result.get("content")),
                "reasoning_chars": len(result.get("reasoning_content") or ""),
            }
            metrics["attempts"].append(attempt_row)
            if parse_error:
                last_error = parse_error
                continue
            if gate_code == 0 or status == "blocked-on-decision":
                metrics["outcome"] = "blocked-on-decision" if status == "blocked-on-decision" else "pass"
                break
            last_error = gate_out
        except urllib.error.URLError as exc:
            metrics["attempts"].append({"attempt": attempt, "error": str(exc), "gpu_before": gpu_before})
            last_error = str(exc)
            if "timed out" in str(exc).lower():
                metrics["outcome"] = "timeout"
                break
    else:
        metrics["outcome"] = "fail"
    (run_dir / "metrics.yaml").write_text(yaml.safe_dump(metrics, sort_keys=False), encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=["S02", "S03", "S04"])
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--phase", required=True, choices=PHASE_ORDER + ["all"])
    parser.add_argument("--tag", default="", help="optional run tag, e.g. nothink")
    args = parser.parse_args()
    runtime = confirm_runtime()
    print(f"runtime ok: {runtime['id']} endpoint={runtime.get('endpoint')}", flush=True)
    phases = PHASE_ORDER if args.phase == "all" else [args.phase]
    if args.case == "S04":
        phases = [p for p in phases if p in {"intake", "analyze"}]
    summary = []
    t0 = time.perf_counter()
    for phase in phases:
        if time.perf_counter() - t0 > 1800:
            print("package timeout 30min")
            break
        print(f"=== {args.case} r{args.repeat} {phase} tag={args.tag or '-'} ===", flush=True)
        row = run_phase(args.case, args.repeat, phase, tag=args.tag)
        summary.append({"phase": phase, "outcome": row.get("outcome"), "attempts": len(row.get("attempts", []))})
        print(json.dumps(summary[-1]), flush=True)
        if row.get("outcome") in {"fail", "timeout", "blocked-on-decision"}:
            break
    run_name = f"r{args.repeat}-{args.tag}" if args.tag else f"r{args.repeat}"
    out = EXPERIMENT / "runs" / args.case / run_name / "summary.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"case": args.case, "repeat": args.repeat, "phases": summary}, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
