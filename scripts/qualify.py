"""Qualification runner (DF3-009 items 8-10).

Drives the reference qualification described in
backlog/product/v3/thresholds.md: N clean runs per release case on the
reference 35B A3B worker through the configured host (LM Studio), applying
absolute thresholds T1-T8 to every run and to the medians.

The runner creates a clean bench sandbox per run, probes the host for the
exact reference model, drives the Worker through a restricted tool loop
(shell = deltafuse/pytest/git only; file writes stay inside the sandbox),
scores the result with the bench pack, and records per-run reports plus a
campaign manifest. It never fabricates results: without the reference host it
prints what is missing and exits pending (V3-FIX-001).

Usage:
    python scripts/qualify.py --host lm-studio --cases M01-cooldown M02-policy-stats M03-adversarial
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

THRESHOLDS_DOC = REPO / "backlog" / "product" / "v3" / "thresholds.md"
RUNS_DIR = REPO / "bench" / "runs"
CASES_ROOT = REPO / "process" / "bench" / "cases"

REFERENCE_MODEL_ID = "ornith-1.5-35b-a3b"
HOST_BASE_URL = "http://127.0.0.1:1234"
CONTEXT_WINDOW_TOKENS = 32768
MAX_WORKER_TURNS = 120
TURN_TIMEOUT_S = 240

ABSOLUTE = {
    "correctness_failed": 0,
    "stages_completed": 7,
    "gate_retries_max": 2,
    "context_peak_tokens_max": CONTEXT_WINDOW_TOKENS,
    "framework_input_tokens_max": 16000,
    "max_unique_files": 24,
    "hallucinated_paths": 0,
    "envelope_violations": 0,
    "evidence_authentic": True,
}

# Step 2: structured argv allowlist. No shell, no string prefixes.
SHELL_FORBIDDEN_CHARS = set('&|;<>()`$*?[]{}~!"\'\n\r')
SHELL_FORBIDDEN_TOKENS = {
    "powershell", "pwsh", "cmd", "cmd.exe", "bash", "sh", "zsh", "fish",
    "python", "python3", "pythonw", "node", "ruby", "perl",
    "sudo", "start", "call", "invoke-expression", "iex",
}
DELTAFUSE_SUBCOMMANDS = {
    "next", "check-gate", "advance", "state", "evidence", "coverage",
    "decide", "archive", "validate", "validate-layout", "lint-context",
    "leash", "board", "new", "init",
}
GIT_READ_ONLY_SUBCOMMANDS = {"status", "diff", "log", "show"}


def parse_shell_argv(command: str) -> list[str] | None:
    """Parse a Worker command into argv; None when it is not safe to run.

    Rejects shell operators, absolute paths, traversal, environment/command
    substitution and arbitrary interpreters before anything executes.
    """
    import shlex

    text = command.strip()
    if not text or "\n" in text or "\r" in text:
        return None
    for ch in SHELL_FORBIDDEN_CHARS:
        if ch in text:
            return None
    try:
        argv = shlex.split(text, posix=True)
    except ValueError:
        return None
    if not argv:
        return None
    for index, token in enumerate(argv):
        low = token.lower()
        if low in SHELL_FORBIDDEN_TOKENS:
            # `python -m pytest` is the one sanctioned interpreter invocation.
            if not (index == 0 and low == "python" and argv[1:3] == ["-m", "pytest"]):
                return None
        if token.startswith(("/", "\\")) or (len(token) >= 2 and token[1] == ":"):
            return None  # absolute path
        if token == ".." or "/.." in token or "\\.." in token:
            return None  # traversal
        if token.startswith("%") and token.endswith("%") and len(token) > 2:
            return None  # environment variable reference
    head = argv[0].lower()
    if head == "deltafuse":
        if len(argv) < 2 or argv[1].lower() not in DELTAFUSE_SUBCOMMANDS:
            return None
        return argv
    if head == "pytest":
        return argv
    if head == "python" and len(argv) >= 3 and argv[1] == "-m" and argv[2] == "pytest":
        return argv
    if head == "git" and len(argv) >= 2 and argv[1].lower() in GIT_READ_ONLY_SUBCOMMANDS:
        return argv
    return None


class QualificationError(Exception):
    """Fail-closed qualification abort."""


# ---------------------------------------------------------------- HTTP host


def _http_json(path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    url = f"{HOST_BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_host(host: str, base_url: str = HOST_BASE_URL) -> dict:
    """V3-FIX-024: fail-closed host probe.

    Requires: /v1/models answers, the exact reference model id is loaded, and
    a diagnostic chat completion succeeds. Returns the immutable host/model
    parameters recorded into the manifest.
    """
    if host != "lm-studio":
        raise QualificationError(f"unsupported host {host!r}; expected 'lm-studio'")
    try:
        models = _get_json(f"{base_url}/v1/models")
    except Exception as ex:
        raise QualificationError(f"host probe failed: {ex}") from ex
    ids = [str(row.get("id")) for row in models.get("data", [])]
    if REFERENCE_MODEL_ID not in ids:
        raise QualificationError(
            f"reference model {REFERENCE_MODEL_ID!r} is not loaded; loaded: {ids}"
        )

    # Measured model parameters (LM Studio v0 REST API). Fail-closed: without
    # them the campaign is blocked — a constant is never written as if measured.
    try:
        v0 = _get_json(f"{base_url}/api/v0/models")
    except Exception as ex:
        raise QualificationError(f"model parameter probe failed (/api/v0/models): {ex}") from ex
    info = next(
        (row for row in v0.get("data", []) if str(row.get("id")) == REFERENCE_MODEL_ID),
        None,
    )
    if info is None:
        raise QualificationError(
            f"reference model {REFERENCE_MODEL_ID!r} has no /api/v0/models entry"
        )
    context_length = info.get("max_context_length") or info.get("context_length")
    if not isinstance(context_length, int) or context_length < CONTEXT_WINDOW_TOKENS:
        raise QualificationError(
            f"measured context limit {context_length!r} does not cover "
            f"{CONTEXT_WINDOW_TOKENS}; configure the model context and re-run"
        )
    state = str(info.get("state") or "unknown")
    if state not in ("loaded", "unknown"):
        raise QualificationError(f"reference model is not loaded (state={state!r})")

    # Diagnostic completion must return a real usage/tokenization result.
    try:
        probe = _post_json(
            f"{base_url}/v1/chat/completions",
            {
                "model": REFERENCE_MODEL_ID,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            },
            timeout=60,
        )
    except Exception as ex:
        raise QualificationError(f"diagnostic completion failed: {ex}") from ex
    usage = probe.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    if not isinstance(prompt_tokens, int) or prompt_tokens <= 0:
        raise QualificationError(
            f"diagnostic completion returned no valid tokenization result: usage={usage!r}"
        )

    return {
        "id": REFERENCE_MODEL_ID,
        "host": host,
        "host_base_url": base_url,
        # measured, not assumed:
        "context_window_tokens_measured": context_length,
        "context_window_tokens_required": CONTEXT_WINDOW_TOKENS,
        "model_state": state,
        "model_params": {
            k: info.get(k)
            for k in ("type", "publisher", "arch", "quantization", "state")
            if info.get(k) is not None
        },
        "cloud_fallback": False,  # runner construction: single local endpoint only
        "loaded_models": ids,
        "probe_prompt_tokens": prompt_tokens,
    }


# ------------------------------------------------------------- git identity


def framework_commit() -> str:
    """V3-FIX-023: resolve the framework commit fail-closed."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO
    )
    if proc.returncode != 0:
        raise QualificationError(
            f"cannot determine framework commit (git rev-parse exit {proc.returncode})"
        )
    sha = proc.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise QualificationError(f"framework commit is not a full SHA: {sha!r}")
    return sha


# ------------------------------------------------------------- worker loop


@dataclass
class ToolEvent:
    """QF-002: typed journal of one Worker tool action, closed AFTER it runs."""

    call_index: int  # 1-based Worker call number
    seq: int  # running action number across the run
    tool: str  # "read" | "write" | "shell" | "unknown"
    outcome: str  # "ok" | "error ..." | "rejected ..."
    paths_read: list[str]  # actually read sandbox-relative posix paths
    paths_written: list[str]  # actually written sandbox-relative posix paths
    command: str | None = None  # argv of a shell command
    exit_code: int | None = None
    envelope_globs: list[str] | None = None  # envelope.write in force (QF-003)


@dataclass
class EnvelopeState:
    """QF-001: write envelope as a first-class, fail-closed state.

    status="ok" always means the Core answered (exit=0, valid JSON):
    globs may still be empty (nothing is writable). status="error" means the
    envelope could not be obtained at all — no product write is allowed and
    the stage is blocked.
    """

    status: str  # "ok" | "error"
    globs: list[str]
    detail: str | None = None


class SandboxIO:
    """Restricted Worker tool surface: read/write inside the sandbox only.

    T7: write_file is limited to the current Core `envelope.write`; the
    envelope is read from `deltafuse next --json`, never from a local guess.
    Fail-closed (QF-001): with no envelope, an empty envelope or an envelope
    error, product writes are denied — a Core failure never widens access.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.hallucinated_paths = 0
        self.envelope_violations = 0
        self.envelope_errors = 0
        self.unique_files: set[str] = set()
        self.events: list[ToolEvent] = []
        self._seq = 0
        self._call_index = 0
        self.write_envelope: EnvelopeState | None = None
        # globs that authorized the most recent successful write (QF-003 hook)
        self.last_write_envelope_globs: list[str] = []

    def begin_call(self) -> None:
        self._call_index += 1

    @property
    def call_index(self) -> int:
        return self._call_index

    def _record(self, tool: str, outcome: str, *, paths_read: list[str] | None = None,
                paths_written: list[str] | None = None, command: str | None = None,
                exit_code: int | None = None) -> None:
        self._seq += 1
        self.events.append(
            ToolEvent(
                call_index=self._call_index,
                seq=self._seq,
                tool=tool,
                outcome=outcome,
                paths_read=paths_read or [],
                paths_written=paths_written or [],
                command=command,
                exit_code=exit_code,
            )
        )

    def call_paths(self, call_index: int) -> set[str]:
        """QF-002: unique paths touched by the events of one Worker call."""
        paths: set[str] = set()
        for event in self.events:
            if event.call_index == call_index:
                paths.update(event.paths_read)
                paths.update(event.paths_written)
        return paths

    def _resolve(self, rel: str) -> Path | None:
        if not rel or rel.startswith(("/", "\\")) or ":" in rel[:3]:
            return None
        path = (self.root / rel).resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            return None
        return path

    def read_file(self, rel: str) -> str:
        path = self._resolve(rel)
        if path is None or not path.is_file():
            self.hallucinated_paths += 1
            self._record("read", f"error: no such file: {rel}", paths_read=[rel])
            return f"ERROR: no such file: {rel}"
        rel_posix = path.relative_to(self.root).as_posix()
        self.unique_files.add(rel_posix)
        self._record("read", "ok", paths_read=[rel_posix])
        return path.read_text(encoding="utf-8", errors="replace")[:60000]

    def write_file(self, rel: str, content: str) -> str:
        path = self._resolve(rel)
        if path is None:
            self.envelope_violations += 1
            self._record("write", f"rejected: path escapes the sandbox: {rel}")
            return "ERROR: path escapes the sandbox"
        rel_posix = path.relative_to(self.root).as_posix()
        if rel_posix.startswith(".deltafuse/"):
            self.envelope_violations += 1
            self._record("write", f"rejected: Core-owned path: {rel_posix}")
            return "ERROR: Core-owned path; use deltafuse commands"
        # T7/QF-001: the envelope comes from the Core (`deltafuse next --json`).
        from deltafuse.core.leash import is_exempt_path, path_in_envelope

        state = self.write_envelope
        if state is not None and state.status == "error":
            self.envelope_errors += 1
            self._record("write", f"rejected: write envelope unavailable: {state.detail}")
            return f"ERROR: write envelope unavailable: {state.detail}"
        if state is None or state.status != "ok":
            self.envelope_violations += 1
            self._record("write", f"rejected: no valid write envelope: {rel_posix}")
            return "ERROR: no valid write envelope; writing is disabled"
        if not state.globs:
            # QF-001: empty envelope = nothing writable except exempt paths.
            if not is_exempt_path(rel_posix):
                self.envelope_violations += 1
                self._record("write", f"rejected: {rel_posix} is outside the (empty) envelope.write")
                return f"ERROR: {rel_posix} is outside the current envelope.write"
        elif not is_exempt_path(rel_posix) and not path_in_envelope(rel_posix, state.globs):
            self.envelope_violations += 1
            self._record("write", f"rejected: {rel_posix} is outside the current envelope.write")
            return f"ERROR: {rel_posix} is outside the current envelope.write"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.last_write_envelope_globs = list(state.globs)
        self.unique_files.add(rel_posix)
        self._record("write", "ok", paths_written=[rel_posix])
        return f"OK: wrote {rel_posix} ({len(content)} bytes)"

    def shell(self, command: str, timeout: int = 300) -> str:
        """Run a Worker command with NO shell: structured argv or nothing."""
        argv = parse_shell_argv(command)
        if argv is None:
            self.envelope_violations += 1
            self._record("shell", f"rejected: command not allowed: {command[:120]}", command=command[:200])
            return f"ERROR: command not allowed: {command[:120]}"
        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self._record("shell", f"error: timed out after {timeout}s",
                         command=" ".join(argv), exit_code=None)
            return f"ERROR: command timed out after {timeout}s"
        except OSError as ex:
            self._record("shell", f"error: cannot execute: {ex}", command=" ".join(argv))
            return f"ERROR: cannot execute: {ex}"
        # QF-003 adds the inventory diff of shell-created paths; for now the
        # journal carries the command and its exit code.
        self._record("shell", "ok" if proc.returncode == 0 else f"error: exit {proc.returncode}",
                     command=" ".join(argv), exit_code=proc.returncode)
        out = ((proc.stdout or "") + (proc.stderr or ""))[-4000:]
        return f"exit={proc.returncode}\n{out}"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def worker_turn(base_url: str, model: str, messages: list[dict]) -> dict:
    """One Worker call; returns assistant content plus token usage."""
    data = _post_json(
        f"{base_url}/v1/chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 2048,
        },
        timeout=TURN_TIMEOUT_S,
    )
    choice = (data.get("choices") or [{}])[0]
    content = str(((choice.get("message") or {}).get("content")) or "")
    usage = data.get("usage") or {}
    return {"content": content, "prompt_tokens": int(usage.get("prompt_tokens") or 0)}


def parse_action(content: str) -> dict:
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {"tool": "done", "reason": "no JSON action"}
    try:
        action = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"tool": "done", "reason": "unparseable action"}
    return action if isinstance(action, dict) else {"tool": "done", "reason": "not an object"}


def _core_envelope(sandbox: Path) -> EnvelopeState:
    """T7/QF-001: current `envelope.write` straight from the Core, fail-closed.

    A Core failure (exception, non-zero exit, invalid JSON) is an error state,
    never an empty allow-list.
    """
    import contextlib
    import io as _io

    from deltafuse.cli import main as cli_main

    buf = _io.StringIO()
    code: int | None
    try:
        with contextlib.redirect_stdout(buf):
            code = cli_main(["next", str(sandbox), "--json"])
    except Exception as ex:
        return EnvelopeState("error", [], detail=f"core exception: {type(ex).__name__}: {ex}")
    if code != 0:
        return EnvelopeState("error", [], detail=f"non-zero exit {code}")
    try:
        data = json.loads(buf.getvalue() or "{}")
    except json.JSONDecodeError as ex:
        return EnvelopeState("error", [], detail=f"invalid JSON from Core: {ex}")
    if not isinstance(data, dict):
        return EnvelopeState("error", [], detail="invalid Core payload: not an object")
    envelope = data.get("envelope")
    if not isinstance(envelope, dict):
        return EnvelopeState("ok", [], detail="no envelope key")
    return EnvelopeState("ok", [str(g) for g in (envelope.get("write") or [])])


def _core_leash_violations(sandbox: Path, files: list[str]) -> int:
    """T7: run the Core leash over the files written so far this stage."""
    import contextlib
    import io as _io

    from deltafuse.cli import main as cli_main

    if not files:
        return 0
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = cli_main(["leash", str(sandbox), "--json", "--files", *files])
        data = json.loads(buf.getvalue() or "{}")
    except Exception:
        return 1  # uninterpretable Core answer counts as a violation
    if code not in (0, 1):
        return 1
    return len(data.get("violations") or [])


def drive_worker(sandbox: Path, base_url: str, model: str, case_id: str, system: str) -> dict:
    """Drive the Worker agent loop in one clean sandbox; return call metrics.

    T4: input tokens come from the host usage; framework-controlled input is
    measured separately (system prompt + Core/tool responses). A call with no
    usage measurement leaves the peak unmeasured (fail-closed in T4).
    T5: unique files are counted per call, including the last tool action.
    T7: after every Core stage transition the leash check runs over the files
    written so far and its verdict is used as-is.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Begin the case {case_id}. Run `deltafuse next` first."},
    ]
    io = SandboxIO(sandbox)
    calls: list[dict] = []
    unmeasured_usage = False
    for _ in range(MAX_WORKER_TURNS):
        io.begin_call()
        envelope = _core_envelope(sandbox)
        io.write_envelope = envelope
        if envelope.status == "error":
            # QF-001: a Core failure blocks the stage; the run aborts instead
            # of continuing with unrestricted writes.
            return _final_metrics(io, calls, unmeasured_usage, envelope_error=envelope.detail)
        turn = worker_turn(base_url, model, messages)
        prompt_tokens = turn["prompt_tokens"]
        if not prompt_tokens:
            unmeasured_usage = True
        # Framework-controlled input of this call: the system prompt (skills,
        # BENCH.md) plus every Core/tool response so far, measured
        # deterministically as UTF-8 characters / 4.
        framework_chars = len(system) + sum(
            len(m["content"]) for m in messages if m["role"] == "user"
        )
        messages.append({"role": "assistant", "content": turn["content"]})
        action = parse_action(turn["content"])
        tool = str(action.get("tool"))
        if tool == "done":
            result = None
        elif tool == "read_file":
            result = io.read_file(str(action.get("path")))
        elif tool == "write_file":
            result = io.write_file(str(action.get("path")), str(action.get("content")))
        elif tool == "shell":
            result = io.shell(str(action.get("command")))
            if result.startswith("exit=0") and "advance: gate" in result:
                # Stage transition: the Core re-checks the whole written set.
                io.envelope_violations += _core_leash_violations(
                    sandbox, sorted(io.unique_files)
                )
        else:
            result = f"ERROR: unknown tool {tool}"
            io._record("unknown", f"error: unknown tool {tool}")
        if result is not None:
            messages.append({"role": "user", "content": result[:6000]})
        # QF-002: the call is measured AFTER its tool action ran, so the last
        # action of a call is included in unique_files.
        calls.append(
            {
                "input_tokens": prompt_tokens or None,
                "framework_input_tokens": framework_chars // 4,
                "unique_files": len(io.call_paths(io.call_index)),
                "hallucinated_paths": io.hallucinated_paths,
                "envelope_violations": io.envelope_violations,
            }
        )
        if tool == "done":
            break
    return _final_metrics(io, calls, unmeasured_usage)


def _final_metrics(
    io: SandboxIO, calls: list[dict], unmeasured_usage: bool, envelope_error: str | None = None
) -> dict:
    from dataclasses import asdict

    peaks = [c["input_tokens"] for c in calls if c["input_tokens"] is not None]
    fw = [c["framework_input_tokens"] for c in calls]
    metrics = {
        "calls": calls,
        "context_peak_tokens": max(peaks) if peaks and not unmeasured_usage else None,
        "framework_input_tokens_max": max(fw) if fw else None,
        "max_unique_files": max((c["unique_files"] for c in calls), default=0),
        "hallucinated_paths": io.hallucinated_paths,
        "envelope_violations": io.envelope_violations,
        "tool_events": [asdict(e) for e in io.events],
    }
    if envelope_error:
        metrics["envelope_error"] = envelope_error
    return metrics


# -------------------------------------------------------------- thresholds


def apply_thresholds(report: dict, metrics: dict) -> tuple[bool, list[str]]:
    """T1-T8 from backlog/product/v3/thresholds.md against one run.

    Uses the real score_product structure: each stage carries `checks` (a
    list) and the aggregates `checks_passed` / `checks_total`. A missing
    measurement is a failure, never an implicit pass.
    """
    failures: list[str] = []
    stages = report.get("stages") or {}
    # T1: zero failed oracle checks, from the actual scorecard aggregates.
    correctness_failed = sum(
        int(row.get("checks_total") or 0) - int(row.get("checks_passed") or 0)
        for row in stages.values()
    )
    if correctness_failed != ABSOLUTE["correctness_failed"]:
        failures.append(f"T1 correctness_failed={correctness_failed}")
    # T2: exactly seven completed stages, none skipped/aborted.
    completed = sum(1 for row in stages.values() if row.get("pass"))
    if completed < ABSOLUTE["stages_completed"]:
        failures.append(f"T2 stages_completed={completed}/7")
    # T3: at most two retries in total and at most one per stage.
    retries = int((report.get("retries") or {}).get("check_gate") or 0)
    if retries > ABSOLUTE["gate_retries_max"]:
        failures.append(f"T3 gate_retries={retries}")
    for stage_name, row in stages.items():
        stage_retries = int(row.get("gate_retries") or 0)
        if stage_retries > 1:
            failures.append(f"T3 {stage_name}: gate_retries={stage_retries} > 1")
    # T4: context budgets; missing usage/tokenization is fail-closed.
    peak = metrics.get("context_peak_tokens")
    fw = metrics.get("framework_input_tokens_max")
    if not isinstance(peak, int):
        failures.append("T4 context_peak_tokens=unmeasured")
    elif peak > ABSOLUTE["context_peak_tokens_max"]:
        failures.append(f"T4 context_peak_tokens={peak}")
    if not isinstance(fw, int):
        failures.append("T4 framework_input_tokens=unmeasured")
    elif fw > ABSOLUTE["framework_input_tokens_max"]:
        failures.append(f"T4 framework_input_tokens={fw}")
    # T5: unique files per call (max across calls).
    unique = metrics.get("max_unique_files")
    if not isinstance(unique, int):
        failures.append("T5 max_unique_files=unmeasured")
    elif unique > ABSOLUTE["max_unique_files"]:
        failures.append(f"T5 max_unique_files={unique}")
    # T6: hallucinated read/write/shell paths.
    halluc = metrics.get("hallucinated_paths")
    if halluc is None:
        failures.append("T6 hallucinated_paths=unmeasured")
    elif halluc != ABSOLUTE["hallucinated_paths"]:
        failures.append(f"T6 hallucinated_paths={halluc}")
    # T7: envelope violations, measured by the Core, not a local counter.
    envelope = metrics.get("envelope_violations")
    if envelope is None:
        failures.append("T7 envelope_violations=unmeasured")
    elif envelope != ABSOLUTE["envelope_violations"]:
        failures.append(f"T7 envelope_violations={envelope}")
    # QF-001: an unavailable envelope blocks the run regardless of counters.
    envelope_error = metrics.get("envelope_error")
    if envelope_error:
        failures.append(f"T7 envelope_unavailable={envelope_error}")
    # T8: authentic evidence for every case (defense checks always run).
    defense = report.get("defense_checks") or {}
    synthetic = [
        k
        for k in ("synthetic_evidence", "journal_forgery", "oracle_leak", "gate_spam", "envelope_escape")
        if k in defense and not defense[k]["pass"]
    ]
    if synthetic:
        failures.append(f"T8 evidence_authentic=false ({','.join(synthetic)})")
    if not report.get("pass"):
        failures.append(f"T1/T2 report.first_fail={report.get('first_fail')}")
    return (not failures), failures


def medians(runs: list[dict]) -> dict:
    def med(key: str) -> float | None:
        values = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
        return round(float(statistics.median(values)), 1) if values else None

    return {
        "correctness": med("correctness"),
        "context_peak_tokens": med("context_peak_tokens"),
        "framework_input_tokens_max": med("framework_input_tokens_max"),
        "gate_retries": med("gate_retries"),
        "max_unique_files": med("max_unique_files"),
    }


# ------------------------------------------------------------------- runner


def thresholds_revision() -> str:
    proc = subprocess.run(
        ["git", "hash-object", str(THRESHOLDS_DOC)],
        capture_output=True, text=True, cwd=REPO,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise QualificationError("cannot hash thresholds.md for the manifest revision")
    return proc.stdout.strip()[:12]


def framework_lock_hash() -> str:
    from deltafuse.core.hasher import compute_framework_content_hash

    return f"sha256:{compute_framework_content_hash(REPO)}"


def tree_dirty() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_yaml(path: Path, data: dict) -> None:
    import yaml

    _atomic_write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def provenance() -> dict:
    """Step 6: full, fail-closed campaign provenance."""
    dirty = tree_dirty()
    if dirty:
        raise QualificationError(
            "working tree is not clean; qualification must run on a fixed commit: "
            + "; ".join(dirty[:5])
        )
    return {
        "commit": framework_commit(),
        "lock_hash": framework_lock_hash(),
        "thresholds_revision": thresholds_revision(),
    }


def run_case(case_id: str, index: int, campaign_id: str, model_probe: dict, provenance_info: dict) -> dict:
    """One clean run: sandbox -> worker loop -> score -> thresholds."""
    from deltafuse.bench.init_product import init_bench_product, format_worker_start_prompt
    from deltafuse.bench.loader import load_case
    from deltafuse.bench.score import score_product

    commit = provenance_info["commit"]
    run_id = f"{campaign_id}-{case_id}-run{index}"
    sandbox = RUNS_DIR / campaign_id / run_id / "sandbox"
    if sandbox.exists():
        raise QualificationError(f"sandbox already exists: {sandbox}")
    init_bench_product(case_id, sandbox, framework_root=REPO)

    case = load_case(case_id, str(CASES_ROOT), oracle=True)
    bench_md = (sandbox / "BENCH.md").read_text(encoding="utf-8")
    system = (
        "You are the DeltaFuse Worker, an autonomous agent completing a "
        "software change end to end. You act only through JSON tool calls.\n\n"
        "Available tools:\n"
        '{"tool": "shell", "command": "<deltafuse|pytest|python -m pytest|git status/diff/log ...>"}\n'
        '{"tool": "read_file", "path": "<relative path>"}\n'
        '{"tool": "write_file", "path": "<relative path>", "content": "<full content>"}\n'
        '{"tool": "done", "reason": "<why the change is complete or blocked>"}\n\n'
        "Rules: one JSON object per reply, nothing else. State transitions go "
        "through the Core (`deltafuse advance`, `deltafuse state`). Never edit "
        ".deltafuse/ files. Finish with {\"tool\": \"done\"} when `deltafuse next` "
        "reports nothing ready or a done halt.\n\n"
        f"Worker start prompt:\n{format_worker_start_prompt(json.loads((sandbox / '.deltafuse' / 'bench.yaml').read_text(encoding='utf-8')))}\n\n{bench_md}"
    )
    metrics = drive_worker(sandbox, model_probe["host_base_url"], model_probe["id"], case_id, system)
    report = score_product(sandbox, pack_root=str(CASES_ROOT))
    verdict, failures = apply_thresholds(report, metrics)

    per_run = {
        "schema_version": 1,
        "run_id": run_id,
        "case": case_id,
        "framework_commit": commit,
        "model": model_probe["id"],
        "verdict": "pass" if verdict else "fail",
        "threshold_failures": failures,
        "stages": report.get("stages") or {},
        "correctness": report.get("correctness"),
        "gate_retries": int((report.get("retries") or {}).get("check_gate") or 0),
        "context_peak_tokens": metrics["context_peak_tokens"],
        "framework_input_tokens_max": metrics["framework_input_tokens_max"],
        "max_unique_files": metrics["max_unique_files"],
        "hallucinated_paths": metrics["hallucinated_paths"],
        "envelope_violations": metrics["envelope_violations"],
        "calls": metrics["calls"],
        "tool_events": metrics["tool_events"],
    }
    run_dir = RUNS_DIR / campaign_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Step 6: report.yaml per thresholds.md format; every run (also failures)
    # is preserved; writes are atomic.
    _atomic_write_yaml(run_dir / "report.yaml", per_run)
    return per_run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="lm-studio")
    ap.add_argument("--cases", nargs="+", default=["M01-cooldown", "M02-policy-stats", "M03-adversarial"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--campaign-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = ap.parse_args()

    # Step 6: provenance is fail-closed — a dirty tree aborts the campaign.
    try:
        provenance_info = provenance()
    except QualificationError as ex:
        print(f"QUALIFICATION ERROR: {ex}", file=sys.stderr)
        return 3
    commit = provenance_info["commit"]
    print(f"framework commit: {commit}")
    print(f"framework lock: {provenance_info['lock_hash'][:19]}...")
    print(f"thresholds revision: {provenance_info['thresholds_revision']}")

    try:
        model_probe = probe_host(args.host)
    except QualificationError as ex:
        print(
            f"PENDING: {ex}\n"
            "Qualification runs are not executed and no results are fabricated. "
            f"Start LM Studio with {REFERENCE_MODEL_ID} (context {CONTEXT_WINDOW_TOKENS}) "
            "and re-run this script."
        )
        return 2
    print(
        f"host probe ok: model={model_probe['id']} "
        f"context={model_probe['context_window_tokens_measured']}"
    )

    campaign_dir = RUNS_DIR / args.campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "campaign_id": args.campaign_id,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framework": {
            "commit": commit,
            "lock_hash": provenance_info["lock_hash"],
        },
        "model": model_probe,
        "thresholds": {
            "source": "backlog/product/v3/thresholds.md",
            "revision": provenance_info["thresholds_revision"],
            "absolute": ABSOLUTE,
        },
        "cases": args.cases,
        "runs": [],
        "case_verdicts": {},
        "verdict": "pending",
    }
    runs_ok = True
    write_error: str | None = None
    for case in args.cases:
        case_runs: list[dict] = []
        for index in range(1, args.runs + 1):
            try:
                run = run_case(case, index, args.campaign_id, model_probe, provenance_info)
            except QualificationError as ex:
                print(f"run failed: {ex}")
                manifest["verdict"] = "incomplete"
                _atomic_write_yaml(campaign_dir / "manifest.yaml", manifest)
                return 3
            manifest["runs"].append(run)
            case_runs.append(run)
            print(f"{run['run_id']}: {run['verdict']} {run['threshold_failures'] or ''}")
            if run["verdict"] != "pass":
                runs_ok = False
            # Atomic manifest refresh after EVERY run: partial results survive.
            try:
                _atomic_write_yaml(campaign_dir / "manifest.yaml", manifest)
            except OSError as ex:
                write_error = str(ex)
        med = medians(case_runs)
        # Step 6: thresholds apply to the medians as well — the metric
        # boundaries (T4/T5/T6/T7) on median values; stage aggregates are
        # per-run facts and are carried as all-completed.
        median_metrics = {
            "context_peak_tokens": med["context_peak_tokens"],
            "framework_input_tokens_max": med["framework_input_tokens_max"],
            "max_unique_files": med["max_unique_files"],
            "hallucinated_paths": 0 if all(r["hallucinated_paths"] == 0 for r in case_runs) else 1,
            "envelope_violations": 0 if all(r["envelope_violations"] == 0 for r in case_runs) else 1,
        }
        carrier_stages = {
            name: {"pass": True, "checks_passed": 0, "checks_total": 0, "gate_retries": 0}
            for name in ("intake", "analyze", "specify", "decompose", "declare", "implement", "verify")
        }
        median_ok, median_failures = apply_thresholds(
            {"pass": True, "first_fail": None, "stages": carrier_stages, "retries": {}, "defense_checks": {}},
            median_metrics,
        )
        case_verdict = "pass" if runs_ok and median_ok else "fail"
        manifest["case_verdicts"][case] = {
            "verdict": case_verdict,
            "medians": med,
            "median_failures": median_failures,
        }
        print(f"{case} medians: {med} verdict={case_verdict}")
    complete = len(manifest["runs"]) == len(args.cases) * args.runs
    manifest["verdict"] = "pass" if runs_ok and complete else "fail"
    try:
        _atomic_write_yaml(campaign_dir / "manifest.yaml", manifest)
    except OSError as ex:
        write_error = str(ex)
    print(f"campaign verdict: {manifest['verdict']}")
    print(f"campaign recorded under {campaign_dir}")
    if write_error:
        print(f"manifest write error: {write_error}", file=sys.stderr)
        return 4
    return 0 if manifest["verdict"] == "pass" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except QualificationError as ex:
        print(f"QUALIFICATION ERROR: {ex}", file=sys.stderr)
        sys.exit(3)
