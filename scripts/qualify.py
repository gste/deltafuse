"""Qualification runner (roadmap item 0.3).

Drives the qualification described in
`backlog/roadmap/q0-qualification-baseline/thresholds.md`: N clean runs per
bench case on the reference dense Worker through OpenRouter, applying the
absolute thresholds T1-T10 to every run and to the medians.

Per run the runner creates a clean bench sandbox, drives the Worker through a
restricted tool surface (shell = deltafuse/pytest/read-only git; writes stay
inside the sandbox), scores the disk with the judge pack, and writes a report.
The campaign manifest carries the framework commit, the model, the tokenizer
mode and the threshold revision.

It never fabricates a result. A measurement that could not be taken is a
failure, not an implicit pass, and a campaign without a measured tokenizer
exits `pending` before the first Worker call.

    python scripts/qualify.py --cases M01-cooldown --pack ../deltafuse-bench

Environment:
    OPENROUTER_API_KEY          required for a live campaign
    DELTAFUSE_TOKENIZE_URL      required: POST /tokenize for framework input
    DELTAFUSE_TOKENIZER_REQUIRED set to 1 by the runner itself
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from deltafuse.core.context import (  # noqa: E402
    TOKENIZER_REQUIRED_ENV,
    TOKENIZE_URL_ENV,
    count_tokens,
    tokenizer_config,
)

THRESHOLDS_DOC = REPO / "backlog" / "roadmap" / "q0-qualification-baseline" / "thresholds.md"
THRESHOLDS_MARKER = "<!-- deltafuse:thresholds -->"
DEFAULT_RUNS_DIR = REPO / "bench" / "runs"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY_ENV = "OPENROUTER_API_KEY"
SCHEMA_VERSION = 1
MAX_STEP_CALLS = 24
MAX_STEPS = 80
REQUEST_TIMEOUT_S = 600

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_PENDING = 2


class QualificationError(Exception):
    """The campaign cannot produce an honest verdict."""


# --------------------------------------------------------------------------
# thresholds
# --------------------------------------------------------------------------

OPS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda got, want: got == want,
    "lte": lambda got, want: got <= want,
    "gte": lambda got, want: got >= want,
}


def load_thresholds(doc: Path = THRESHOLDS_DOC) -> dict[str, Any]:
    """Read the machine-readable block from thresholds.md. No second source."""
    if not doc.is_file():
        raise QualificationError(f"thresholds document not found: {doc}")
    text = doc.read_text(encoding="utf-8")
    if THRESHOLDS_MARKER not in text:
        raise QualificationError(f"{doc} has no {THRESHOLDS_MARKER} marker")
    tail = text.split(THRESHOLDS_MARKER, 1)[1]
    match = re.search(r"```yaml\r?\n(.*?)\r?\n```", tail, re.S)
    if match is None:
        raise QualificationError(f"{doc}: no yaml block after {THRESHOLDS_MARKER}")
    block = match.group(1)
    data = yaml.safe_load(block)
    if not isinstance(data, dict) or not isinstance(data.get("thresholds"), list):
        raise QualificationError(f"{doc}: threshold block is not a mapping with `thresholds`")
    for row in data["thresholds"]:
        missing = [k for k in ("id", "metric", "op", "value") if k not in row]
        if missing:
            raise QualificationError(f"{doc}: threshold {row!r} missing {missing}")
        if row["op"] not in OPS:
            raise QualificationError(f"{doc}: threshold {row['id']} has unknown op {row['op']!r}")
    data["revision"] = hashlib.sha256(block.encode("utf-8")).hexdigest()[:8]
    try:
        data["source"] = doc.resolve().relative_to(REPO).as_posix()
    except ValueError:
        data["source"] = doc.resolve().as_posix()
    return data


def evaluate(thresholds: dict[str, Any], metrics: dict[str, Any], scope: str) -> tuple[list[str], list[str]]:
    """Apply thresholds of *scope*. Returns (gating failures, observed-only notes).

    A metric that is absent or None is a failure for a gating threshold: rule 3
    of thresholds.md, a missing measurement is never an implicit pass.
    """
    failures: list[str] = []
    observed: list[str] = []
    for row in thresholds["thresholds"]:
        if scope not in (row.get("scope") or ["per_run", "median"]):
            continue
        gating = bool(row.get("gating"))
        sink = failures if gating else observed
        metric = row["metric"]
        got = metrics.get(metric)
        if got is None:
            sink.append(f"{row['id']} {metric}: not measured")
            continue
        if not OPS[row["op"]](got, row["value"]):
            sink.append(f"{row['id']} {metric}={got} violates {row['op']} {row['value']}")
    return failures, observed


def budget_adjusted_score(
    thresholds: dict[str, Any], metrics: dict[str, Any], score: Any
) -> dict[str, Any]:
    """Score of the run after the framework-budget penalty (scoring.budget_penalty).

    The framework budget is an orientation for the unit of work, not a limit
    (owner decision 2026-09-21): a run that did the work above it keeps its
    verdict and loses score in proportion to the overshoot. Returns
    `budget_factor` and `score_adjusted`; both None when the peak or the score
    was not measured - an unmeasured run is not scored as clean.
    """
    cfg = (thresholds.get("scoring") or {}).get("budget_penalty")
    if not cfg:
        return {}
    peak = metrics.get(cfg["metric"])
    reference = float(cfg["reference"])
    if peak is None or reference <= 0:
        return {"budget_factor": None, "score_adjusted": None}
    overshoot = max(0.0, (float(peak) - reference) / reference)
    factor = max(float(cfg.get("floor", 0.0)), 1.0 - float(cfg.get("rate", 1.0)) * overshoot)
    adjusted = None if score is None else round(float(score) * factor, 1)
    return {"budget_factor": round(factor, 4), "score_adjusted": adjusted}


def median_metrics(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Median per metric over runs; a metric missing anywhere stays unmeasured."""
    names: set[str] = set()
    for run in runs:
        names.update((run.get("metrics") or {}).keys())
    out: dict[str, Any] = {}
    for name in sorted(names):
        values = [(run.get("metrics") or {}).get(name) for run in runs]
        if any(v is None for v in values) or not values:
            out[name] = None
            continue
        out[name] = statistics.median(values)
    return out


# --------------------------------------------------------------------------
# sandbox
# --------------------------------------------------------------------------


def _run(argv: Sequence[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


DELTAFUSE_ARGV = [sys.executable, "-m", "deltafuse"]
GIT_READONLY = frozenset({"status", "diff", "log", "show", "ls-files", "rev-parse", "branch"})
# Human Gate commands. The runner is the standing human; the Worker never clicks.
WORKER_FORBIDDEN_DELTAFUSE = frozenset({"decide"})


class Sandbox:
    """A bench product the Worker mutates and the runner measures."""

    def __init__(self, root: Path, pack: Path) -> None:
        self.root = root
        self.pack = pack
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(REPO / "src")

    # -- runner-side commands (judge, not Worker) --------------------------

    def cli(self, *args: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            DELTAFUSE_ARGV + list(args),
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=self.env,
        )
        return proc

    def cli_json(self, *args: str) -> dict[str, Any]:
        proc = self.cli(*args)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as ex:
            raise QualificationError(
                f"`deltafuse {' '.join(args)}` did not return JSON: {proc.stdout[:200]}"
            ) from ex

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return _run(["git", *args], self.root)

    def git_init(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.email", "qualify@deltafuse.invalid")
        self.git("config", "user.name", "deltafuse-qualify")
        self.commit("qualification baseline")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", message)

    def envelope_violations(self) -> list[str]:
        """T7: paths outside the current write envelope, straight from the Core."""
        proc = self.cli("leash", ".", "--json")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return [f"leash did not return JSON: {proc.stdout[:160]}"]
        return [str(e) for e in (payload.get("errors") or [])]

    # -- Worker-side tool surface ------------------------------------------

    def resolve(self, rel: str) -> Path | None:
        """Sandbox-relative path, or None when it escapes the sandbox."""
        try:
            target = (self.root / rel).resolve()
        except OSError:
            return None
        root = self.root.resolve()
        if target != root and root not in target.parents:
            return None
        return target


def hallucinated_argv_paths(argv: Sequence[str], sandbox: Sandbox) -> list[str]:
    """T6: path-looking arguments that do not exist on disk.

    Deterministic and conservative: only tokens that already look like a path
    (a separator, or a source/artifact suffix) are considered, so an ordinary
    subcommand name is never counted.
    """
    suffixes = (".py", ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg")
    out: list[str] = []
    for token in list(argv)[1:]:
        if token.startswith("-"):
            continue
        looks_like_path = "/" in token or "\\" in token or token.endswith(suffixes)
        if not looks_like_path:
            continue
        bare = token.split("::", 1)[0].split("#", 1)[0]
        if Path(argv[0]).stem.lower() == "git" and ":" in bare and not re.match(r"^[A-Za-z]:[\/]", bare):
            # `git show HEAD:docs/x.md` names a blob in history, not a file on
            # disk; whether it exists is git's answer, not a T6 fact.
            continue
        target = sandbox.resolve(bare)
        if target is None or not target.exists():
            out.append(token)
    return out


# --------------------------------------------------------------------------
# Worker tool surface
# --------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run",
            "description": (
                "Run one allowed command in the product root. Allowed: `deltafuse ...`, "
                "`pytest ...`, and read-only `git` (status, diff, log, show, ls-files, "
                "rev-parse, branch). Never `git push`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Argument vector, e.g. [\"deltafuse\", \"next\", \"--json\"]",
                    }
                },
                "required": ["argv"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read one file, relative to the product root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write one file in full, relative to the product root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List one directory, relative to the product root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


@dataclass
class CallRecord:
    """One provider request: what went in and how much of it was the framework."""

    prompt_tokens: int | None
    completion_tokens: int | None
    framework_tokens: int | None
    unique_files: int
    cost_usd: float | None = None


@dataclass
class RunTrace:
    calls: list[CallRecord] = field(default_factory=list)
    hallucinated: list[str] = field(default_factory=list)
    envelope_violations: list[str] = field(default_factory=list)
    files_in_context: set[str] = field(default_factory=set)
    steps: int = 0
    gates_clicked: list[str] = field(default_factory=list)
    gate_attempts: list[str] = field(default_factory=list)

    def hallucinate(self, path: str) -> None:
        if path not in self.hallucinated:
            self.hallucinated.append(path)


def _framework_tokens(messages: Sequence[dict[str, Any]]) -> int:
    """Framework-controlled input of this request: what the Core put in, not the model.

    System instructions and tool results are framework-authored; assistant
    turns are not. Counted with the measured tokenizer, which the campaign
    requires, so the number is comparable between machines.
    """
    total = 0
    for message in messages:
        if message.get("role") not in ("system", "tool"):
            continue
        content = message.get("content")
        if isinstance(content, str) and content:
            total += count_tokens(content).tokens
    return total


class OpenRouterWorker:
    """Minimal OpenAI-compatible tool loop. One conversation per lifecycle step."""

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        timeout: int = REQUEST_TIMEOUT_S,
        max_cost_usd: float | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_cost_usd = max_cost_usd
        self.spent_usd = 0.0

    def charge(self, usage: dict[str, Any]) -> float | None:
        """Book the provider-reported cost; refuse the next call past the ceiling."""
        cost = usage.get("cost")
        if isinstance(cost, (int, float)):
            self.spent_usd += float(cost)
            return float(cost)
        return None

    def check_budget(self) -> None:
        if self.max_cost_usd is not None and self.spent_usd >= self.max_cost_usd:
            raise QualificationError(
                f"cost ceiling reached: ${self.spent_usd:.4f} >= ${self.max_cost_usd:.2f}"
            )

    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            OPENROUTER_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "DeltaFuse qualification",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            detail = ex.read().decode("utf-8", errors="replace")[:400]
            raise QualificationError(f"OpenRouter HTTP {ex.code}: {detail}") from ex
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as ex:
            raise QualificationError(f"OpenRouter request failed: {ex}") from ex
        if not body.get("choices"):
            raise QualificationError(f"OpenRouter returned no choices: {str(body)[:300]}")
        return body


SYSTEM_PROMPT = (
    "You are the Worker in a DeltaFuse product. The Core owns the lifecycle: it "
    "selects the step, checks gates and keeps evidence. You write only what the "
    "named step allows.\n\n"
    "Use the tools. Do not describe what you would do; do it. When the step is "
    "complete and its gate passes, reply with a short plain-text summary and no "
    "tool call.\n\n"
    "Human Gates are not yours: if `deltafuse next` halts on a decision or spec "
    "gate, stop and say so. Never run `git push`."
)


def execute_tool(
    name: str,
    args: dict[str, Any],
    sandbox: Sandbox,
    trace: RunTrace,
) -> str:
    if name == "read_file":
        rel = str(args.get("path") or "")
        target = sandbox.resolve(rel)
        if target is None:
            return f"refused: '{rel}' is outside the product root"
        if not target.is_file():
            trace.hallucinate(rel)
            return f"error: '{rel}' does not exist"
        trace.files_in_context.add(rel.replace("\\", "/"))
        return target.read_text(encoding="utf-8", errors="replace")

    if name == "list_dir":
        rel = str(args.get("path") or ".")
        target = sandbox.resolve(rel)
        if target is None:
            return f"refused: '{rel}' is outside the product root"
        if not target.is_dir():
            trace.hallucinate(rel)
            return f"error: '{rel}' is not a directory"
        return "\n".join(sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir()))

    if name == "write_file":
        rel = str(args.get("path") or "")
        target = sandbox.resolve(rel)
        if target is None:
            return f"refused: '{rel}' is outside the product root"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(args.get("content") or ""), encoding="utf-8")
        for violation in sandbox.envelope_violations():
            if violation not in trace.envelope_violations:
                trace.envelope_violations.append(violation)
        return f"wrote {rel}"

    if name == "run":
        argv = [str(a) for a in (args.get("argv") or [])]
        if not argv:
            return "error: empty argv"
        tool = Path(argv[0]).stem.lower()
        if tool == "git" and (len(argv) < 2 or argv[1] not in GIT_READONLY):
            return f"refused: only read-only git is allowed ({sorted(GIT_READONLY)})"
        if tool not in ("deltafuse", "pytest", "git"):
            return "refused: allowed commands are deltafuse, pytest and read-only git"
        if tool == "deltafuse" and len(argv) > 1 and argv[1] in WORKER_FORBIDDEN_DELTAFUSE:
            trace.gate_attempts.append(" ".join(argv))
            return (
                f"refused: `deltafuse {argv[1]}` records a Human Gate click; the Worker "
                "never makes it. Stop and report the halt instead."
            )
        for bad in hallucinated_argv_paths(argv, sandbox):
            trace.hallucinate(bad)
        if tool == "deltafuse":
            concrete = DELTAFUSE_ARGV + argv[1:]
        elif tool == "pytest":
            concrete = [sys.executable, "-m", "pytest", *argv[1:]]
        else:
            concrete = argv
        try:
            proc = subprocess.run(
                concrete,
                cwd=str(sandbox.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                env=sandbox.env,
            )
        except subprocess.TimeoutExpired:
            return "error: command timed out"
        out = (proc.stdout or "") + (proc.stderr or "")
        return f"exit={proc.returncode}\n{out[:12000]}"

    return f"error: unknown tool {name}"


def drive_step(
    worker: OpenRouterWorker,
    sandbox: Sandbox,
    trace: RunTrace,
    step_brief: str,
) -> None:
    """One lifecycle step: a fresh conversation, tool calls until the model stops."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": step_brief},
    ]
    for _ in range(MAX_STEP_CALLS):
        worker.check_budget()
        body = worker.complete(messages)
        usage = body.get("usage") or {}
        trace.calls.append(
            CallRecord(
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                framework_tokens=_framework_tokens(messages),
                unique_files=len(trace.files_in_context),
                cost_usd=worker.charge(usage),
            )
        )
        message = body["choices"][0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        messages.append(
            {
                "role": "assistant",
                "content": message.get("content") or "",
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
        )
        if not tool_calls:
            return
        for call in tool_calls:
            function = call.get("function") or {}
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(str(function.get("name")), args, sandbox, trace)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": result,
                }
            )


def step_brief(sandbox: Sandbox, snapshot: dict[str, Any]) -> str:
    """The bounded reads the Core selected, plus the skill that binds the step."""
    selected = snapshot.get("selected") or {}
    lines = [
        "`deltafuse next --json` selected this step. Execute it and stop.",
        "",
        json.dumps(selected, ensure_ascii=False, indent=2),
    ]
    envelope = snapshot.get("envelope")
    if envelope:
        lines += ["", "Write envelope (anything outside it is a violation):",
                  json.dumps(envelope, ensure_ascii=False, indent=2)]
    skill = selected.get("skill")
    if skill:
        skill_file = sandbox.root / ".agents" / "skills" / str(skill) / "SKILL.md"
        if skill_file.is_file():
            lines += ["", f"--- skill {skill} ---", skill_file.read_text(encoding="utf-8")]
    return "\n".join(lines)


def click_gate(sandbox: Sandbox, halt: dict[str, Any], trace: RunTrace) -> bool:
    """The runner is the standing human for DEC / spec gates. The Worker never is."""
    for choice in halt.get("choices") or []:
        cid = str(choice.get("id") or "")
        command = choice.get("command")
        if not command or not (cid.startswith("accept:") or cid.startswith("accept-spec:")):
            continue
        argv = command.split()
        proc = sandbox.cli(*argv[1:])
        trace.gates_clicked.append(f"{cid} exit={proc.returncode}")
        return proc.returncode == 0
    return False


# --------------------------------------------------------------------------
# one run
# --------------------------------------------------------------------------


def collect_metrics(report: dict[str, Any], trace: RunTrace) -> dict[str, Any]:
    """Run metrics named exactly as the thresholds block names them."""
    stages = report.get("stages") or {}
    prompt_peaks = [c.prompt_tokens for c in trace.calls if c.prompt_tokens is not None]
    framework_peaks = [c.framework_tokens for c in trace.calls if c.framework_tokens is not None]
    file_peaks = [c.unique_files for c in trace.calls]
    retries = report.get("retries") or {}
    by_stage = [int(row.get("gate_retries") or 0) for row in stages.values()]
    defense = report.get("defense_checks") or {}
    evidence_errors = sum(0 if row.get("pass") else 1 for row in defense.values())
    return {
        "correctness_failed_checks": int(report.get("checks_total") or 0)
        - int(report.get("checks_passed") or 0),
        "correctness_pct": float(report.get("correctness") or 0.0),
        "stages_incomplete": sum(1 for row in stages.values() if not row.get("pass")),
        "gate_retries_total": int(retries.get("check_gate") or 0),
        "gate_retries_max_stage": max(by_stage) if by_stage else 0,
        "context_peak_tokens": max(prompt_peaks) if prompt_peaks else None,
        "framework_input_peak_tokens": max(framework_peaks) if framework_peaks else None,
        "max_unique_files_per_call": max(file_peaks) if file_peaks else 0,
        "hallucinated_paths": len(trace.hallucinated),
        "envelope_violations": len(trace.envelope_violations),
        "evidence_errors": evidence_errors,
        # T9/T10 have no producing mechanism yet (roadmap items 2 and 1). They
        # are declared non-gating in thresholds.md and reported as unmeasured
        # rather than as a zero nobody computed.
        "under_routing_rate": None,
        "structural_formats_per_call": None,
    }


def execute_run(
    *,
    case: str,
    run_id: str,
    sandbox_dir: Path,
    pack: Path,
    worker: OpenRouterWorker,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    from deltafuse.bench.init_product import init_bench_product
    from deltafuse.bench.score import score_product

    init_bench_product(case, sandbox_dir, framework_root=REPO, pack_root=pack, force=True)
    sandbox = Sandbox(sandbox_dir, pack)
    sandbox.git_init()
    trace = RunTrace()

    for _ in range(MAX_STEPS):
        snapshot = sandbox.cli_json("next", ".", "--json")
        halt = snapshot.get("halt")
        if halt:
            kind = str(halt.get("kind") or "")
            if kind == "done":
                break
            if kind in ("decision", "spec"):
                if not click_gate(sandbox, halt, trace):
                    break
                continue
            break
        if not snapshot.get("selected"):
            break
        trace.steps += 1
        drive_step(worker, sandbox, trace, step_brief(sandbox, snapshot))
        for violation in sandbox.envelope_violations():
            if violation not in trace.envelope_violations:
                trace.envelope_violations.append(violation)
        sandbox.commit(f"worker step {trace.steps}")

    report = score_product(sandbox_dir, label=worker.model, pack_root=pack)
    metrics = collect_metrics(report, trace)
    metrics.update(budget_adjusted_score(thresholds, metrics, report.get("score")))
    failures, observed = evaluate(thresholds, metrics, "per_run")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "case": case,
        "verdict": "pass" if not failures else "fail",
        "failures": failures,
        "observed": observed,
        "metrics": metrics,
        "observed_only": [
            row["id"] for row in thresholds["thresholds"] if not row.get("gating")
        ],
        "tokenizer": tokenizer_config(),
        "calls": len(trace.calls),
        "cost_usd": round(sum(c.cost_usd or 0.0 for c in trace.calls), 6),
        "tokens": {
            "prompt": sum(c.prompt_tokens or 0 for c in trace.calls),
            "completion": sum(c.completion_tokens or 0 for c in trace.calls),
        },
        "steps": trace.steps,
        "gates_clicked": trace.gates_clicked,
        "worker_gate_attempts": trace.gate_attempts,
        "hallucinated_paths": trace.hallucinated,
        "envelope_violations": trace.envelope_violations,
        "score": {
            "correctness": report.get("correctness"),
            "process": report.get("process"),
            "score": report.get("score"),
            "first_fail": report.get("first_fail"),
        },
    }


# --------------------------------------------------------------------------
# campaign
# --------------------------------------------------------------------------


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    tmp.replace(path)


def framework_commit() -> dict[str, Any]:
    head = _run(["git", "rev-parse", "HEAD"], REPO)
    status = _run(["git", "status", "--porcelain"], REPO)
    return {
        "commit": (head.stdout or "").strip() or None,
        "dirty": bool((status.stdout or "").strip()),
    }


def tokenizer_identity() -> dict[str, Any] | None:
    """GET <endpoint>/health from scripts/tokenize_server.py: which tokenizer counts."""
    url = os.environ.get(TOKENIZE_URL_ENV, "").strip()
    if not url:
        return None
    health = url.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def probe_tokenizer() -> str | None:
    """Count a fixed text through the required endpoint. Returns a blocker or None."""
    try:
        counted = count_tokens("DeltaFuse qualification tokenizer probe.")
    except Exception as ex:  # TokenizerUnavailableError and transport errors alike
        return f"tokenizer endpoint did not answer a probe: {ex}"
    if not counted.measured:
        return f"tokenizer probe was not measured (mode={counted.mode})"
    return None


def preflight(
    model: str, *, live: bool, diagnostic: bool = False
) -> tuple[str | None, list[str]]:
    """Fail-closed gate before the first Worker call. Returns (api_key, blockers).

    A diagnostic run may proceed without a measured tokenizer because it never
    carries a qualification verdict; a qualifying run may not.
    """
    blockers: list[str] = []
    if not diagnostic:
        os.environ[TOKENIZER_REQUIRED_ENV] = "1"
        if not os.environ.get(TOKENIZE_URL_ENV, "").strip():
            blockers.append(
                f"{TOKENIZE_URL_ENV} is not set: T4 framework-controlled input cannot be "
                "measured, and thresholds.md forbids a heuristic behind a qualification verdict"
            )
        else:
            problem = probe_tokenizer()
            if problem:
                blockers.append(problem)
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if live and not api_key:
        blockers.append(f"{API_KEY_ENV} is not set: no reference Worker to qualify")
    if not model:
        blockers.append("no model given")
    return (api_key or None), blockers


def run_campaign(
    *,
    cases: Sequence[str],
    model: str,
    pack: Path,
    runs_dir: Path,
    campaign_id: str,
    repeats: int,
    diagnostic: bool = False,
    max_cost_usd: float | None = None,
) -> tuple[dict[str, Any], int]:
    thresholds = load_thresholds()
    api_key, blockers = preflight(model, live=True, diagnostic=diagnostic)
    campaign_dir = runs_dir / campaign_id
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framework": framework_commit(),
        "model": {"id": model, "provider": "openrouter"},
        "tokenizer": {**tokenizer_config(), "identity": tokenizer_identity()},
        "thresholds": {"source": thresholds["source"], "revision": thresholds["revision"]},
        "cases": list(cases),
        "runs_per_case": repeats,
        "verdict": "pending",
        "diagnostic": diagnostic,
        "max_cost_usd": max_cost_usd,
        "blockers": blockers,
        "runs": [],
    }
    if blockers:
        _write_yaml(campaign_dir / "manifest.yaml", manifest)
        return manifest, EXIT_PENDING

    worker = OpenRouterWorker(model, str(api_key), max_cost_usd=max_cost_usd)
    reports: list[dict[str, Any]] = []
    for case in cases:
        for index in range(1, repeats + 1):
            run_id = f"{campaign_id}-{case}-{index}"
            sandbox_dir = campaign_dir / run_id / "sandbox"
            try:
                report = execute_run(
                    case=case,
                    run_id=run_id,
                    sandbox_dir=sandbox_dir,
                    pack=pack,
                    worker=worker,
                    thresholds=thresholds,
                )
            except QualificationError as ex:
                report = {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": run_id,
                    "case": case,
                    "verdict": "fail",
                    "failures": [f"run aborted: {ex}"],
                    "metrics": {},
                }
            if diagnostic:
                # Thresholds are still evaluated and shown, but a diagnostic run
                # is not a qualification result and never reads as `pass`.
                report["threshold_result"] = report["verdict"]
                report["verdict"] = "diagnostic"
            _write_yaml(campaign_dir / run_id / "report.yaml", report)
            reports.append(report)
            manifest["runs"].append(
                {"run_id": run_id, "case": case, "verdict": report["verdict"]}
            )
            print(f"{run_id}: {report['verdict']}")
            for line in report.get("failures") or []:
                print(f"  - {line}")

    medians = median_metrics(reports)
    median_failures, median_observed = evaluate(thresholds, medians, "median")
    manifest["medians"] = {"metrics": medians, "failures": median_failures,
                           "observed": median_observed}
    manifest["spent_usd"] = round(worker.spent_usd, 6)
    if diagnostic:
        manifest["verdict"] = "diagnostic"
        _write_yaml(campaign_dir / "manifest.yaml", manifest)
        return manifest, EXIT_PENDING
    per_run_failed = any(r["verdict"] != "pass" for r in reports)
    manifest["verdict"] = "fail" if (per_run_failed or median_failures) else "pass"
    _write_yaml(campaign_dir / "manifest.yaml", manifest)
    return manifest, EXIT_PASS if manifest["verdict"] == "pass" else EXIT_FAIL


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="+", required=True, help="Bench case ids")
    parser.add_argument(
        "--model",
        default="qwen/qwen3.8-27b",
        help="OpenRouter model id (default: the reference from the contract)",
    )
    parser.add_argument(
        "--pack",
        default=os.environ.get("DELTAFUSE_BENCH_PACK") or str(REPO.parent / "deltafuse-bench"),
        help="Judge pack (deltafuse-bench checkout)",
    )
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    parser.add_argument("--repeats", type=int, default=None, help="Runs per case")
    parser.add_argument(
        "--campaign-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help=(
            "Pipeline check on the live model without a measured tokenizer. "
            "Never yields a qualification verdict: the campaign is `diagnostic`."
        ),
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="USD ceiling for provider spend across the campaign (from usage.cost)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preflight only: thresholds, pack and environment; no Worker call",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        thresholds = load_thresholds()
    except QualificationError as ex:
        print(f"qualify: {ex}", file=sys.stderr)
        return EXIT_PENDING
    repeats = args.repeats or int(
        (thresholds.get("campaign") or {}).get("runs_per_case") or 3
    )
    pack = Path(args.pack).resolve()

    if args.dry_run:
        _, blockers = preflight(args.model, live=True, diagnostic=args.diagnostic)
        if not pack.is_dir():
            blockers.append(f"judge pack not found: {pack}")
        print(f"thresholds {thresholds['source']} revision={thresholds['revision']}")
        print(f"model={args.model}  cases={args.cases}  repeats={repeats}  pack={pack}")
        print(f"tokenizer={tokenizer_config()}")
        print(f"tokenizer identity={tokenizer_identity()}")
        if blockers:
            print("pending:", file=sys.stderr)
            for line in blockers:
                print(f"  - {line}", file=sys.stderr)
            return EXIT_PENDING
        print("preflight ok")
        return EXIT_PASS

    try:
        manifest, code = run_campaign(
            cases=args.cases,
            model=args.model,
            pack=pack,
            runs_dir=Path(args.runs_dir).resolve(),
            campaign_id=args.campaign_id,
            repeats=repeats,
            diagnostic=args.diagnostic,
            max_cost_usd=args.max_cost,
        )
    except QualificationError as ex:
        print(f"qualify: {ex}", file=sys.stderr)
        return EXIT_PENDING
    print(
        f"campaign {manifest['campaign_id']}: {manifest['verdict']}"
        f"  spent=${manifest.get('spent_usd', 0.0)}"
    )
    for line in manifest.get("blockers") or []:
        print(f"  - {line}", file=sys.stderr)
    for line in (manifest.get("medians") or {}).get("failures") or []:
        print(f"  median: {line}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
