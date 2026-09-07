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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

FRAMEWORK = Path(__file__).resolve().parents[5]
_EXPERIMENT_DIR = os.environ.get("A09_EXPERIMENT_DIR")
EXPERIMENT = Path(_EXPERIMENT_DIR) if _EXPERIMENT_DIR else Path(__file__).resolve().parents[1]
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
TASK = os.environ.get("A09_TASK", "TASK-001")
TEMPERATURE = 0.1
TOP_P = 0.9
PROTOCOL_TIMEOUT_S = 300

WRAPPER = """/no_think
You execute exactly one DeltaFuse lifecycle phase on a product repository.
Do not write a chain-of-thought. Put the JSON in the assistant content immediately.
Return ONLY a JSON object. No markdown fences, no prose outside JSON.
Shape:
{"files":[{"path":"relative/from/product/root","content":"full file text"}],"status":"continue","notes":"short"}
Each files[] item is its own object with keys path and content. Do not put two paths in one object. Do not use a frontmatter key.
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


def seed_s01_product(product: Path) -> None:
    """Empty holdout product: installer catalog only, no limiter spec/code."""
    (product / "src").mkdir(parents=True, exist_ok=True)
    (product / "tests").mkdir(parents=True, exist_ok=True)
    (product / "pyproject.toml").write_text(
        "[project]\nname='empty-product'\nversion='0.0.1'\n"
        "[tool.pytest.ini_options]\npythonpath=['src']\n",
        encoding="utf-8",
    )


def seed_s03_product(product: Path) -> None:
    """Correct spec, buggy limiter: int() truncates fractional refill."""
    seed_ratelimit_product(product)
    (product / "docs" / "spec" / "security" / "ratelimit.md").write_text(
        "# security.ratelimit\n\n"
        "## REQ-RL-01 Capacity and refill\n"
        "TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0. "
        "Tokens MUST be refilled proportionally to elapsed time, preserving fractional balances.\n\n"
        "## REQ-RL-02 Consume\n"
        "consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.\n\n"
        "## REQ-RL-03 Unknown keys\n"
        "An unknown key MUST start at full capacity.\n\n"
        "## REQ-RL-04 is_blocked\n"
        "is_blocked(key) MUST return False for the baseline limiter (no penalty lock).\n",
        encoding="utf-8",
    )
    (product / "src" / "ratelimit" / "limiter.py").write_text(
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
        "        gained = int((now - last) * self.refill_rate)\n"
        "        tokens = min(self.capacity, tokens + gained)\n"
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


def setup_product(case_id: str, repeat: int) -> Path:
    product = EXPERIMENT / "work" / f"{case_id}-r{repeat}"
    if product.exists():
        return product
    sys.path.insert(0, str(FRAMEWORK / "src"))
    from deltafuse.core.installer import install

    install(target_dir=product, framework_root=FRAMEWORK)
    if case_id == "S01":
        seed_s01_product(product)
    elif case_id == "S03":
        seed_s03_product(product)
    else:
        # S02/S04 calibration and S05 holdout: live security.ratelimit + code.
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
            schema_by_focus = {
                "routing": ("routing.schema.yaml",),
                "slices": ("slice.schema.yaml",),
                "coverage": ("coverage.schema.yaml",),
                "analysis": ("change.schema.yaml",),
            }
            schema_names = schema_by_focus.get(
                ANALYZE_FOCUS,
                ("routing.schema.yaml", "slice.schema.yaml", "coverage.schema.yaml", "change.schema.yaml"),
            )
            for name in schema_names:
                files.append(FRAMEWORK / "process" / "schemas" / name)
            if case_id == "S04":
                files.append(FRAMEWORK / "process" / "schemas" / "decision.schema.yaml")
                files.append(FRAMEWORK / "process" / "schemas" / "change.schema.yaml")
        if phase == "specify":
            files.append(FRAMEWORK / "process" / "schemas" / "spec-delta.schema.yaml")
        if phase == "decompose":
            files.append(FRAMEWORK / "process" / "schemas" / "task.schema.yaml")
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
    if phase == "intake":
        parts.append(
            "Claim ids in request.md MUST be CR-001, CR-002, … (pattern CR-NNN). "
            "You may still label them observation/expectation/constraint/hypothesis in prose. "
            "Do not use O1/E1/C1 as ids. "
            "change.yaml must include empty lists: deltas, slices, decisions, tasks. "
            "Use status continue."
        )
    if phase == "analyze" and ANALYZE_FOCUS == "routing":
        if case_id == "S04":
            parts.append(
                "This call writes docs/changes/<id>/routing.yaml (map every CR-* to a primary capability). "
                "Do not add schema_version; routing.schema.yaml forbids extra keys. "
                "Do not edit docs/spec/** or src/**. Do not Specify. "
                "If you already treat the VIP policy fork as blocking, you MUST also write "
                "docs/decisions/DEC-0001-<slug>.md (status proposed) AND change.yaml with "
                "status blocked-on-decision and decisions: [that DEC path], and set JSON "
                "status blocked-on-decision. Writing only the DEC file is not enough. "
                "Otherwise use status continue and do not write slices or coverage.yaml."
            )
        else:
            parts.append(
                "This call writes ONLY docs/changes/<id>/routing.yaml (map every CR-* to a primary capability). "
                "Do not add schema_version; routing.schema.yaml forbids extra keys. "
                "Use status continue. Do not set blocked-on-decision and do not write Decision files. "
                "Do not write analysis.md, slices, or coverage.yaml."
            )
    if phase == "analyze" and ANALYZE_FOCUS == "slices":
        if case_id == "S04":
            parts.append(
                "This request lists mutually exclusive VIP policies. Do NOT pick one. "
                "Do not edit docs/spec/** or src/**. Do not write coverage.yaml. "
                "Write files[]: (1) docs/decisions/DEC-0001-<slug>.md with YAML frontmatter matching "
                "decision.schema.yaml: id DEC-0001, title, kind architecture, status proposed, "
                "owner pending-human, date (ISO), change <id>, affects.capabilities [security.ratelimit], "
                "affects.spec_refs [docs/spec/security/ratelimit.md], supersedes null, superseded_by null. "
                "No schema_version. Body lists the forks without choosing. "
                "(2) docs/changes/<id>/change.yaml — keep existing fields, set status: blocked-on-decision, "
                "decisions: [docs/decisions/DEC-0001-<slug>.md]. "
                "Optional short SLICE-01.md that records the open fork. "
                "JSON status MUST be blocked-on-decision."
            )
        else:
            parts.append(
                "This call writes ONLY one file: docs/changes/<id>/slices/SLICE-01.md "
                "(YAML frontmatter matching slice.schema.yaml, then markdown body). "
                "Keep the body short. Frontmatter claims must list the CR-NNN ids from request.md. "
                "Use status continue. Do not set blocked-on-decision: unknowns are not blocking Decisions "
                "for a single unambiguous feature. "
                "Do not write coverage.yaml, analysis.md, or extra slices."
            )
    if phase == "analyze" and ANALYZE_FOCUS == "coverage":
        if case_id == "S04":
            parts.append(
                "Do not write coverage.yaml. The Change must stop for a human Decision. "
                "Write docs/decisions/DEC-0001-<slug>.md (status proposed) and change.yaml "
                "status blocked-on-decision. JSON status MUST be blocked-on-decision. "
                "Do not edit docs/spec/** or src/**."
            )
        else:
            parts.append(
                "This call writes ONLY docs/changes/<id>/coverage.yaml matching coverage.schema.yaml. "
                "Do not add schema_version. Do not rewrite slices or analysis.md. "
                "Use status continue. Do not set blocked-on-decision and do not write Decision files: "
                "intake unknowns (U*) are not blocking Decisions for a single unambiguous feature. "
                "Map each CR-NNN id from request.md to slice SLICE-01."
            )
    if phase == "specify":
        if case_id == "S03":
            parts.append(
                "This is a bug with a correct live spec. Do NOT edit docs/spec/**. "
                "Write ONLY docs/changes/<id>/spec-delta.md with YAML frontmatter matching "
                "spec-delta.schema.yaml (no schema_version; status: proposed; slices: [SLICE-01]; "
                "do NOT put added/modified/removed in frontmatter). "
                "Body: ADDED/MODIFIED/REMOVED none — specification unchanged. "
                "Use status continue. Keep content short."
            )
        elif case_id == "S02":
            parts.append(
                "Write two files[] objects (separate objects, keys path and content): "
                "(1) docs/changes/<id>/spec-delta.md with YAML frontmatter matching spec-delta.schema.yaml "
                "(no schema_version; status: proposed; slices: [SLICE-01]; do NOT put added/modified/removed "
                "in frontmatter — those strings are treated as file paths and will fail the gate) "
                "and ADDED/MODIFIED/REMOVED headings only in the markdown body; "
                "(2) the updated live spec docs/spec/security/ratelimit.md with new REQ-RL-* for the cooldown. "
                "Keep REQ-RL-01..04. Do not invent Decisions. Use status continue. Keep content short."
            )
    if phase == "decompose":
        if case_id == "S03":
            parts.append(
                "Write TWO files[] objects (separate objects, keys path and content): "
                "(1) docs/changes/<id>/tasks/TASK-001-<slug>.md — frontmatter MUST match "
                "task.schema.yaml: id TASK-001, slice SLICE-01, kind bugfix (not kind bug), "
                "status pending, depends_on [], requirement_delta none, "
                "spec_refs [docs/spec/security/ratelimit.md#REQ-RL-01], design_ref null, "
                "allowed_paths [src/ratelimit/limiter.py, tests/test_limiter.py], "
                "forbidden_paths [docs/spec/**]. No schema_version. Keep body short. "
                "(2) docs/changes/<id>/change.yaml — keep existing fields, set status: decomposed, "
                "and tasks: [docs/changes/<id>/tasks/TASK-001-<slug>.md]. "
                "Writing only the task file leaves status normalized and fails the gate. "
                "Optionally update coverage.yaml: claims.*.tasks must be ids like TASK-001, not file paths. "
                "Use status continue. Do not write code or spec."
            )
        elif case_id == "S02":
            parts.append(
                "Write 1 or 2 tasks as separate files[] objects (path + content): "
                "docs/changes/<id>/tasks/TASK-001-<slug>.md (and optional TASK-002). "
                "Frontmatter MUST match task.schema.yaml: id TASK-NNN, slice SLICE-01, kind feature, "
                "status pending, depends_on [], requirement_delta added, spec_refs to existing "
                "docs/spec/security/ratelimit.md#REQ-RL-05 (or 06/07), design_ref null, "
                "allowed_paths [src/ratelimit/limiter.py, tests/test_limiter.py], "
                "forbidden_paths [docs/spec/auth/**]. No schema_version. Keep body short. "
                "Optionally update coverage.yaml: claims.*.tasks must be ids like TASK-001, not file paths. "
                "Set change.yaml status to decomposed. Use status continue. Do not write code."
            )
    if phase == "target":
        if case_id == "S03":
            parts.append(
                "Write ONLY tests/test_limiter.py. Keep the existing baseline test. "
                "Add the smallest failing test that fractional refill accumulates. "
                "Unknown keys start at full capacity: first consume(capacity) MUST be True. "
                "Then, with refill_rate 0.5, after ~1s still cannot consume 1 more token; "
                "after ~2s total can consume 1. Public API only; no private _fields. "
                "Do not edit src/ or docs/spec/. Do not write evidence YAML. Use status continue."
            )
        elif case_id == "S02" and TASK == "TASK-002":
            parts.append(
                "Write ONLY tests/test_limiter.py. Keep existing tests. "
                "Add the smallest test for TASK-002 using only the public API "
                "(consume, is_blocked, constructor). Do not read or assign private fields "
                "(no limiter._blocked_until or other _names). "
                "After the penalty window, consume may succeed only when tokens are available "
                "(leave tokens or use refill_rate > 0); do not assert consume True on an empty bucket. "
                "If production already lifts the block, a correct test will pass — that is already-green, "
                "not a reason to manufacture Red. "
                "Do not edit src/ratelimit/limiter.py. Do not write evidence YAML. Use status continue."
            )
        elif case_id == "S02":
            parts.append(
                "Write ONLY tests/test_limiter.py (path + content). Keep the existing baseline test. "
                "Add the smallest failing test for TASK-001: penalty_seconds > 0, failed consume locks the key, "
                "later consume returns False while blocked. Do not edit src/ratelimit/limiter.py. "
                "Do not write evidence YAML (the harness will run pytest). Use status continue."
            )
    if phase == "implement":
        if case_id == "S03":
            parts.append(
                "Write ONLY src/ratelimit/limiter.py. Do not edit tests or docs/spec/**. "
                "Do not write evidence YAML. Fix refill so elapsed * refill_rate is not truncated to int; "
                "keep fractional token balance. Use status continue."
            )
        elif case_id == "S02":
            parts.append(
                "Write ONLY src/ratelimit/limiter.py. Do not edit tests. Do not write evidence YAML. "
                "Add optional penalty_seconds=0.0; on failed consume when penalty_seconds > 0 lock the key "
                "for that duration; is_blocked(key) True while locked; keep baseline when penalty_seconds is 0. "
                "Use status continue."
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
        text = item.get("content")
        if text is None and item.get("frontmatter") is not None:
            fm = str(item.get("frontmatter") or "").strip()
            body = str(item.get("body") or "")
            if fm.startswith("---"):
                text = fm if not body else fm.rstrip() + "\n" + body
            else:
                text = "---\n" + fm + "\n---\n" + body
        if text is None:
            raise ValueError(
                "files[] item needs key 'content' (full file text). "
                f"Got keys: {sorted(item.keys())}."
            )
        dest = product / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        written.append(rel)
    return written


def run_pytest(product: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_limiter.py", "-q", "--tb=short"],
        cwd=product,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def write_red_evidence(change_dir: Path, task_id: str, command: str, exit_code: int, log: str) -> str:
    category = "behavioral-mismatch"
    low = log.lower()
    if "importerror" in low or "modulenotfound" in low or "syntaxerror" in low:
        category = "import-error"
    payload = {
        "schema_version": 2,
        "change": change_dir.name,
        "task": task_id,
        "phase": "red",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": command,
        "exit_code": int(exit_code),
        "result": "expected-failure",
        "failure_category": category,
        "summary": (log[-800:] if log else "pytest failed"),
        "changed_paths": ["tests/test_limiter.py"],
        "spec_status": "unchanged",
    }
    dest = change_dir / "evidence" / "red" / f"{task_id}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return dest.relative_to(change_dir.parent.parent.parent).as_posix()


def write_pass_evidence(
    change_dir: Path,
    task_id: str,
    phase: str,
    command: str,
    log: str,
    changed_paths: list[str],
) -> str:
    payload = {
        "schema_version": 2,
        "change": change_dir.name,
        "task": task_id,
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": command,
        "exit_code": 0,
        "result": "passed",
        "failure_category": None,
        "summary": (log[-800:] if log else "pytest passed"),
        "changed_paths": changed_paths,
        "spec_status": "unchanged",
    }
    dest = change_dir / "evidence" / phase / f"{task_id}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return dest.relative_to(change_dir.parent.parent.parent).as_posix()


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


def s04_human_gate_complete(product: Path, written: list[str], status: str) -> bool:
    if status != "blocked-on-decision":
        return False
    wrote_decision = any(
        p.replace("\\", "/").startswith("docs/decisions/")
        and Path(p).name.startswith("DEC-")
        and "template" not in Path(p).name.lower()
        for p in written
    )
    if not wrote_decision:
        change_dir = find_change_dir(product, written=written)
        if change_dir is not None:
            wrote_decision = any(
                p.name.startswith("DEC-") and "template" not in p.name.lower()
                for p in (product / "docs" / "decisions").glob("DEC-*.md")
            )
        if not wrote_decision:
            return False
    change_dir = find_change_dir(product, written=written)
    if change_dir is None:
        return False
    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8")) or {}
    if data.get("status") != "blocked-on-decision":
        return False
    decisions = data.get("decisions") or []
    return any("DEC-" in str(item) for item in decisions)


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


def analyze_step_name(phase: str) -> str:
    if phase == "analyze" and ANALYZE_FOCUS:
        return f"analyze-{ANALYZE_FOCUS}"
    if phase in {"target", "implement"}:
        return f"{phase}-{TASK}"
    return phase


def slice_schema_errors(change_dir: Path) -> list[str]:
    from deltafuse.core.fsm import validate_change_package

    return [
        e
        for e in validate_change_package(change_dir)
        if ".md:" in e and e.split(":", 1)[0].startswith("SLICE-")
    ]


def run_phase(case_id: str, repeat: int, phase: str, tag: str = "") -> dict[str, Any]:
    product = setup_product(case_id, repeat)
    run_name = f"r{repeat}-{tag}" if tag else f"r{repeat}"
    run_dir = EXPERIMENT / "runs" / case_id / run_name / analyze_step_name(phase)
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
        "task": TASK if phase in {"target", "implement"} else None,
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
            if not parse_error and case_id == "S03" and phase in {"specify", "implement", "target", "decompose"}:
                spec_writes = [
                    p.replace("\\", "/")
                    for p in written
                    if p.replace("\\", "/").startswith("docs/spec/")
                ]
                if spec_writes:
                    parse_error = "S03 spec unchanged: must not edit " + ",".join(spec_writes)
            if not parse_error and case_id == "S04":
                premature = [
                    p.replace("\\", "/")
                    for p in written
                    if p.replace("\\", "/").startswith("docs/spec/")
                    or p.replace("\\", "/").startswith("src/")
                ]
                if premature:
                    parse_error = "S04 must not edit spec or code before Decision: " + ",".join(
                        premature
                    )
            if not parse_error and phase == "target":
                prod_writes = [
                    p.replace("\\", "/")
                    for p in written
                    if p.replace("\\", "/").startswith("src/")
                ]
                if prod_writes:
                    parse_error = "target must not change production code: " + ",".join(prod_writes)
                else:
                    test_src = (product / "tests" / "test_limiter.py").read_text(encoding="utf-8")
                    private_hits = re.findall(r"\._[A-Za-z_]\w*", test_src)
                    if private_hits:
                        parse_error = (
                            "target must not touch private fields "
                            + ",".join(sorted(set(private_hits)))
                            + "; use public consume/is_blocked only"
                        )
                    else:
                        change_dir = find_change_dir(product, written=written)
                        pytest_code, pytest_log = run_pytest(product)
                        (run_dir / f"attempt{attempt}-pytest.txt").write_text(
                            pytest_log, encoding="utf-8"
                        )
                        if pytest_code == 0:
                            parse_error = None
                            gate_code, gate_out = 0, (
                                f"already-green: pytest passed for {TASK}; no authentic Red "
                                "(production already implements this behavior)"
                            )
                            (run_dir / f"attempt{attempt}-gate.txt").write_text(
                                gate_out, encoding="utf-8"
                            )
                            metrics["attempts"].append(
                                {
                                    "attempt": attempt,
                                    "prompt_chars": prompt_chars,
                                    "ttft_s": result.get("ttft_s"),
                                    "elapsed_s": result.get("elapsed_s"),
                                    "written": written,
                                    "model_status": status,
                                    "gate_exit": 0,
                                    "pytest_exit": 0,
                                    "already_green": True,
                                    "gpu_before": gpu_before,
                                    "gpu_after": nvidia_smi(),
                                    "content_empty": not bool(result.get("content")),
                                    "reasoning_chars": len(result.get("reasoning_content") or ""),
                                }
                            )
                            metrics["outcome"] = "already-green"
                            (run_dir / "metrics.yaml").write_text(
                                yaml.safe_dump(metrics, sort_keys=False), encoding="utf-8"
                            )
                            return metrics
                        elif change_dir is None:
                            parse_error = "no change directory for red evidence"
                        else:
                            ev_rel = write_red_evidence(
                                change_dir,
                                TASK,
                                "python -m pytest tests/test_limiter.py -q --tb=short",
                                pytest_code,
                                pytest_log,
                            )
                            written.append(ev_rel)
            if not parse_error and phase == "implement":
                test_writes = [
                    p.replace("\\", "/")
                    for p in written
                    if p.replace("\\", "/").startswith("tests/")
                ]
                src_writes = [
                    p.replace("\\", "/")
                    for p in written
                    if p.replace("\\", "/").startswith("src/")
                ]
                if test_writes:
                    parse_error = "implement must not edit tests: " + ",".join(test_writes)
                elif not src_writes:
                    parse_error = "implement must write src/ratelimit/limiter.py"
                else:
                    change_dir = find_change_dir(product, written=written)
                    pytest_code, pytest_log = run_pytest(product)
                    (run_dir / f"attempt{attempt}-pytest.txt").write_text(pytest_log, encoding="utf-8")
                    cmd = "python -m pytest tests/test_limiter.py -q --tb=short"
                    if pytest_code != 0:
                        parse_error = "Green required: pytest failed\n" + pytest_log[-1500:]
                    elif change_dir is None:
                        parse_error = "no change directory for green evidence"
                    else:
                        written.append(
                            write_pass_evidence(change_dir, TASK, "green", cmd, pytest_log, src_writes)
                        )
                        written.append(
                            write_pass_evidence(
                                change_dir, TASK, "regression", cmd, pytest_log, src_writes
                            )
                        )
            gate_code, gate_out = (1, "skipped") if parse_error else run_gate(product, phase, written=written)
            if not parse_error and phase == "analyze" and ANALYZE_FOCUS == "routing":
                routing_written = any(
                    Path(p).name == "routing.yaml" or p.replace("\\", "/").endswith("/routing.yaml")
                    for p in written
                )
                if not routing_written:
                    gate_code, gate_out = 1, "routing-only: missing routing.yaml"
                else:
                    change_dir = find_change_dir(product, written=written)
                    pkg_errors = []
                    if change_dir is not None:
                        from deltafuse.core.fsm import validate_change_package

                        pkg_errors = [
                            e
                            for e in validate_change_package(change_dir)
                            if e.startswith("routing.yaml:")
                        ]
                    if pkg_errors:
                        only_sv = all("schema_version" in e for e in pkg_errors)
                        routing_path = change_dir / "routing.yaml" if change_dir is not None else None
                        if only_sv and routing_path is not None and routing_path.is_file():
                            data = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
                            if isinstance(data, dict) and "schema_version" in data:
                                data.pop("schema_version")
                                routing_path.write_text(
                                    yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
                                )
                                pkg_errors = [
                                    e
                                    for e in validate_change_package(change_dir)
                                    if e.startswith("routing.yaml:")
                                ]
                        if pkg_errors:
                            gate_code, gate_out = 1, "\n".join(pkg_errors)
                        else:
                            gate_code, gate_out = (
                                0,
                                "routing-only: stripped schema_version; schema ok; analyzed gate deferred",
                            )
                    else:
                        gate_code, gate_out = 0, "routing-only: routing.yaml schema ok; analyzed gate deferred"
            elif not parse_error and phase == "analyze" and ANALYZE_FOCUS == "slices":
                slice_written = any(
                    "/slices/" in p.replace("\\", "/") and p.endswith(".md") for p in written
                )
                if not slice_written:
                    gate_code, gate_out = 1, "slices-only: missing slices/SLICE-*.md"
                else:
                    change_dir = find_change_dir(product, written=written)
                    pkg_errors = slice_schema_errors(change_dir) if change_dir is not None else ["no change directory"]
                    if pkg_errors:
                        gate_code, gate_out = 1, "\n".join(pkg_errors)
                    else:
                        gate_code, gate_out = 0, "slices-only: slice schema ok; analyzed gate deferred"
            elif not parse_error and phase == "analyze" and ANALYZE_FOCUS == "coverage":
                cov_written = any(
                    Path(p).name == "coverage.yaml" or p.replace("\\", "/").endswith("/coverage.yaml")
                    for p in written
                )
                if not cov_written:
                    gate_code, gate_out = 1, "coverage-only: missing coverage.yaml"
                else:
                    change_dir = find_change_dir(product, written=written)
                    pkg_errors = ["no change directory"]
                    if change_dir is not None:
                        from deltafuse.core.schemas import SchemaRegistry

                        cov_path = change_dir / "coverage.yaml"
                        cov_data = yaml.safe_load(cov_path.read_text(encoding="utf-8"))
                        pkg_errors = [
                            f"coverage.yaml: {e}"
                            for e in SchemaRegistry().validate("coverage", cov_data)
                        ]
                    if pkg_errors:
                        gate_code, gate_out = 1, "\n".join(pkg_errors)
                    else:
                        gate_code, gate_out = 0, "coverage-only: coverage schema ok; completeness deferred to analyzed gate"
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
            wrote_decision = any(
                p.replace("\\", "/").startswith("docs/decisions/")
                and Path(p).name.startswith("DEC-")
                and "template" not in Path(p).name.lower()
                for p in written
            )
            if case_id == "S04" and status == "blocked-on-decision" and not s04_human_gate_complete(
                product, written, status
            ):
                last_error = (
                    "S04 incomplete human gate: write docs/decisions/DEC-*.md AND set "
                    "change.yaml status blocked-on-decision with decisions: [that path]"
                )
                gate_code = 1
                attempt_row["gate_exit"] = 1
                metrics["attempts"][-1] = attempt_row
                (run_dir / f"attempt{attempt}-gate.txt").write_text(last_error, encoding="utf-8")
                continue
            if (
                case_id == "S04"
                and phase == "analyze"
                and ANALYZE_FOCUS in {"slices", "coverage"}
                and not s04_human_gate_complete(product, written, status)
            ):
                last_error = (
                    "S04 must set status blocked-on-decision and write docs/decisions/DEC-*.md; "
                    "do not choose a VIP policy and do not Specify"
                )
                gate_code = 1
                attempt_row["gate_exit"] = 1
                metrics["attempts"][-1] = attempt_row
                (run_dir / f"attempt{attempt}-gate.txt").write_text(last_error, encoding="utf-8")
                continue
            if status == "blocked-on-decision" and not wrote_decision:
                last_error = (
                    "status blocked-on-decision requires writing docs/decisions/DEC-*.md"
                    + (
                        ""
                        if case_id == "S04"
                        else "; this request is a single unambiguous feature — use status continue"
                    )
                )
                gate_code = 1
                attempt_row["gate_exit"] = 1
                metrics["attempts"][-1] = attempt_row
                (run_dir / f"attempt{attempt}-gate.txt").write_text(last_error, encoding="utf-8")
                continue
            if gate_code == 0 or (
                status == "blocked-on-decision"
                and wrote_decision
                and (case_id != "S04" or s04_human_gate_complete(product, written, status))
            ):
                metrics["outcome"] = "blocked-on-decision" if status == "blocked-on-decision" else "pass"
                break
            last_error = gate_out
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
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
    parser.add_argument("--case", required=True, choices=["S01", "S02", "S03", "S04", "S05"])
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
        summary.append(
            {
                "phase": analyze_step_name(phase),
                "outcome": row.get("outcome"),
                "attempts": len(row.get("attempts", [])),
            }
        )
        print(json.dumps(summary[-1]), flush=True)
        if row.get("outcome") in {"fail", "timeout", "blocked-on-decision"}:
            break
    run_name = f"r{args.repeat}-{args.tag}" if args.tag else f"r{args.repeat}"
    out = EXPERIMENT / "runs" / args.case / run_name / "summary.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = list(summary)
    if out.exists():
        prev = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
        prev_phases = list(prev.get("phases") or [])
        by_name = {row.get("phase"): row for row in prev_phases if row.get("phase")}
        for row in summary:
            by_name[row.get("phase")] = row
        order: list[str] = []
        for p in PHASE_ORDER:
            if p == "analyze":
                for focus in ("routing", "slices", "coverage", "analysis"):
                    name = f"analyze-{focus}"
                    if name in by_name:
                        order.append(name)
            elif p in {"target", "implement"}:
                order.extend(sorted(n for n in by_name if n == p or n.startswith(p + "-")))
            elif p in by_name:
                order.append(p)
        extra = [p for p in by_name if p not in order]
        merged = [by_name[p] for p in order + extra]
    out.write_text(
        yaml.safe_dump({"case": args.case, "repeat": args.repeat, "tag": args.tag or None, "phases": merged}, sort_keys=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
