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
import hashlib
import json
import statistics
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import qualify_executor
from qualify_executor import apply_executor_verdict_cap, resolve_executor

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from deltafuse.core.lifecycle import LIFECYCLE  # noqa: E402  (QF-014: single contract)

THRESHOLDS_DOC = REPO / "backlog" / "product" / "v3" / "thresholds.md"
RUNS_DIR = REPO / "bench" / "runs"
CASES_ROOT = REPO / "process" / "bench" / "cases"

REFERENCE_MODEL_ID = "ornith-1.5-35b-a3b"
HOST_BASE_URL = "http://127.0.0.1:1234"
CONTEXT_WINDOW_TOKENS = 32768
MAX_WORKER_TURNS = 120
TURN_TIMEOUT_S = 240

# QF-007: fixed tokenizer calibration text (~1 KiB, ASCII-stable) whose token
# ids fingerprint the host tokenizer across campaigns.
CALIBRATION_TEXT = (
    "DeltaFuse qualification tokenizer calibration. "
    "The quick brown fox jumps over the lazy dog. 0123456789 "
    "def drive_worker(sandbox: Path, base_url: str, model: str) -> dict:\n"
    "    return {'calls': [], 'context_peak_tokens': None}\n"
    "Pack my box with five dozen liquor jugs. How vexingly quick daft "
    "zebras jump! Sphinx of black quartz, judge my vow. "
    "The framework keeps process, product and evidence strictly apart: "
    "Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> "
    "Verify. Thresholds T1-T8 are absolute; a missing measurement is a "
    "failure, never an implicit pass. "
) * 3


def _attest(value, provenance: str, method: str | None = None,
            basis: str | None = None, **extra) -> dict:
    """QF-007: provenance-tagged manifest field."""
    field_def: dict = {"value": value, "provenance": provenance}
    if method is not None:
        field_def["method"] = method
    if basis is not None:
        field_def["basis"] = basis
    field_def.update(extra)
    return field_def


def _probe_tokenizer(base_url: str) -> dict:
    """QF-015: fail-closed tokenizer probe — a release campaign REQUIRES a
    working host tokenize endpoint.

    - endpoint absent (connection error / timeout / HTTP 404) and endpoint
      present but failing/garbage/invalid-count all raise QualificationError:
      the campaign stays PENDING before the first Worker call. The old
      `chars-div-4-fallback` path is gone; an estimate can never support a
      release pass.
    """
    import urllib.error

    def blocked(reason: str) -> QualificationError:
        return QualificationError(
            f"tokenizer endpoint unavailable: {reason}; release qualification "
            f"requires a measured host tokenizer (POST {base_url}/api/v0/tokenize)"
        )

    try:
        data = _post_json(
            f"{base_url}/api/v0/tokenize", {"input": CALIBRATION_TEXT}, timeout=20
        )
    except urllib.error.HTTPError as ex:
        raise blocked(f"HTTP {ex.code}") from ex
    except Exception as ex:
        raise blocked(f"{type(ex).__name__}") from ex
    tokens = data.get("tokens") if isinstance(data, dict) else None
    if isinstance(tokens, list):
        count = len(tokens)
    elif isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
        count = tokens
    else:
        raise blocked(f"garbage or invalid token answer: {str(data)[:120]}")
    fingerprint = hashlib.sha256(
        json.dumps(tokens if isinstance(tokens, list) else count).encode("utf-8")
    ).hexdigest()
    return _attest(
        "host-tokenize", "measured",
        method="POST /api/v0/tokenize (endpoint discovered)",
        fingerprint=fingerprint,
        calibration_tokens=count,
    )


# QF-015: documented consistency allowance between the raw tokenizer count of
# CALIBRATION_TEXT and the diagnostic completion usage on the same text; the
# chat template adds the difference (see backlog/product/v3/thresholds.md).
TOKENIZER_CONSISTENCY_ALLOWANCE = 48


def _assert_tokenizer_consistency(base_url: str, model: str, calibration_tokens: int) -> None:
    """QF-015: the diagnostic completion usage must agree with the tokenizer."""
    probe = _post_json(
        f"{base_url}/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": CALIBRATION_TEXT}],
            "max_tokens": 1,
            "temperature": 0,
        },
        timeout=60,
    )
    usage = (probe.get("usage") or {}).get("prompt_tokens")
    low = calibration_tokens
    high = calibration_tokens + TOKENIZER_CONSISTENCY_ALLOWANCE
    if not isinstance(usage, int) or isinstance(usage, bool) or not low <= usage <= high:
        raise QualificationError(
            f"tokenizer consistency check failed: tokenizer counted "
            f"{calibration_tokens} tokens but completion usage was {usage!r} "
            f"(allowed {low}..{high})"
        )


def tokenizer_fingerprint_matches(expected, actual) -> bool:
    """QF-015: tokenizer drift invalidates the campaign."""
    return (
        isinstance(expected, str)
        and isinstance(actual, str)
        and expected == actual
    )


def attest_manifest_model(probe: dict) -> None:
    """QF-007: self-check — every mandatory model field is provenance-tagged.

    measured fields need a method; declared fields need a basis; provenance
    must be one of measured|declared|derived. Blocks the campaign otherwise.
    """
    for key, field_def in probe.items():
        if not isinstance(field_def, dict) or "value" not in field_def or "provenance" not in field_def:
            raise QualificationError(
                f"manifest model field {key!r} lacks a provenance label"
            )
        provenance = field_def["provenance"]
        if provenance not in ("measured", "declared", "derived"):
            raise QualificationError(
                f"manifest model field {key!r}: unknown provenance {provenance!r}"
            )
        if provenance == "measured" and not field_def.get("method"):
            raise QualificationError(
                f"manifest model field {key!r}: measured without method"
            )
        if provenance == "declared" and not str(field_def.get("basis") or "").strip():
            raise QualificationError(
                f"manifest model field {key!r}: declared without basis"
            )

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

# QF-006: mandatory evidence checks — an absent check is a failure, never a pass.
REQUIRED_T8_CHECKS = {"journal_forgery", "synthetic_evidence", "oracle_leak"}

# QF-006: host tokenizer cache (sha256(text) -> token count).
_TOKEN_CACHE: dict[str, int] = {}


def _host_tokenize(base_url: str, text: str) -> int | None:
    """Host tokenizer via the LM Studio tokenize endpoint; None when absent.

    The estimate chars//4 is never reported through this path: callers record
    which method produced the number they used.
    """
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key in _TOKEN_CACHE:
        return _TOKEN_CACHE[key]
    try:
        data = _post_json(f"{base_url}/api/v0/tokenize", {"input": text}, timeout=10)
        tokens = data.get("tokens") if isinstance(data, dict) else None
        if isinstance(tokens, list):
            count = len(tokens)
        elif isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
            count = tokens
        else:
            return None
    except Exception:
        return None
    _TOKEN_CACHE[key] = count
    return count


def _reason_is_hallucination(reason: str) -> bool:
    """QF-006: parser/execution refusal reasons that mean 'invented path or
    tool' (T6) as opposed to an execution-policy boundary (T7)."""
    return (
        "subcommand not allowed" in reason
        or reason.startswith("rejected: unknown command")
        or reason.startswith("rejected: for an unknown tool")
    )


def classify_violations(events: list[dict]) -> dict:
    """QF-006: the T6/T7 classification matrix over the typed tool journal."""
    hallucinated = 0
    envelope = 0
    execution_policy = 0
    for event in events:
        tool = event.get("tool")
        outcome = str(event.get("outcome"))
        if tool == "unknown":
            hallucinated += 1
        elif tool == "read" and outcome.startswith("error"):
            hallucinated += 1
        elif tool == "write" and outcome.startswith("rejected"):
            if "escapes the sandbox" in outcome:
                hallucinated += 1  # unresolvable/invented path
            else:
                envelope += 1      # Core-owned / no envelope / outside envelope
        elif tool == "shell" and outcome.startswith("rejected"):
            if _reason_is_hallucination(outcome):
                hallucinated += 1
            else:
                execution_policy += 1
        elif tool == "shell" and "exit 4" in outcome:
            hallucinated += 1      # pytest: file/module not found
    return {
        "hallucinated": hallucinated,
        "envelope": envelope,
        "execution_policy": execution_policy,
    }

# QF-004: exact option policy. Any token not explicitly allowed is a refusal.
DELTA_BREAK_GATES = None  # gate names are validated by the Core itself
PYTEST_FLAGS = {
    "-q", "-x", "-v", "-s", "-rA", "--tb=line", "--tb=short", "--tb=no",
    "--co", "--collect-only", "--version",
}
PYTEST_VALUE_FLAGS = {"-k", "-m"}


def _reject(reason: str) -> tuple[None, str]:
    return None, reason


def parse_shell_command(command: str) -> tuple[list[str] | None, str | None]:
    """Parse a Worker command into argv under the QF-004 option policy.

    Returns (argv, None) when the command is allowed, or (None, reason) with
    the classified refusal reason (journaled by SandboxIO for QF-006).
    """
    import shlex

    text = command.strip()
    if not text or "\n" in text or "\r" in text:
        return _reject("empty or multiline command")
    for ch in SHELL_FORBIDDEN_CHARS:
        if ch in text:
            return _reject(f"forbidden shell character {ch!r}")
    try:
        argv = shlex.split(text, posix=True)
    except ValueError as ex:
        return _reject(f"unparseable command: {ex}")
    if not argv:
        return _reject("empty command")
    for index, token in enumerate(argv):
        low = token.lower()
        if low in SHELL_FORBIDDEN_TOKENS:
            # `python -m pytest` is the one sanctioned interpreter invocation.
            if not (index == 0 and low == "python" and argv[1:3] == ["-m", "pytest"]):
                return _reject(f"forbidden interpreter/tool token: {token}")
        if token.startswith("@"):
            return _reject(f"response file not allowed: {token}")
        if token == "--":
            return _reject("end-of-options separator not allowed")
        if token.startswith("//") or token.startswith("\\\\"):
            return _reject(f"UNC/network path not allowed: {token}")
        if token.startswith(("/", "\\")) or (len(token) >= 2 and token[1] == ":"):
            return _reject(f"absolute path not allowed: {token}")
        if token == ".." or "/.." in token or "\\.." in token:
            return _reject(f"path traversal not allowed: {token}")
        if token.startswith("%") and token.endswith("%") and len(token) > 2:
            return _reject(f"environment variable reference not allowed: {token}")
        if "=" in token and not token.startswith("-"):
            return _reject(f"env_override attempt not allowed: {token}")
    head = argv[0].lower()
    if head == "deltafuse":
        if len(argv) < 2 or argv[1].lower() not in DELTAFUSE_SUBCOMMANDS:
            return _reject("deltafuse subcommand not allowed")
        sub = argv[1].lower()
        rest = argv[2:]
        i = 0
        while i < len(rest):
            tok = rest[i].lower()
            if tok == "--json":
                i += 1
                continue
            if tok == "--human" and sub == "next":
                i += 1
                continue
            if tok == "--gate" and sub == "advance":
                if i + 1 >= len(rest) or rest[i + 1].startswith("-"):
                    return _reject("--gate requires a gate name")
                i += 2
                continue
            return _reject(f"deltafuse option not allowed: {rest[i]}")
        return argv, None
    if head == "pytest":
        return _check_pytest_args(argv, 1)
    if head == "python" and len(argv) >= 3 and argv[1] == "-m" and argv[2] == "pytest":
        return _check_pytest_args(argv, 3)
    if head == "python":
        return _reject("python is only allowed as `python -m pytest`")
    if head == "git":
        if len(argv) < 2 or argv[1].lower() not in GIT_READ_ONLY_SUBCOMMANDS:
            return _reject("git subcommand not allowed")
        for token in argv[2:]:
            if token.startswith("-"):
                return _reject(f"git options are not allowed: {token}")
            if token != "HEAD":
                return _reject(f"git positional not allowed: {token}")
        return argv, None
    return _reject(f"unknown command: {argv[0]}")


def _check_pytest_args(argv: list[str], start: int) -> tuple[list[str] | None, str | None]:
    i = start
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            if token in PYTEST_FLAGS:
                i += 1
                continue
            if token in PYTEST_VALUE_FLAGS:
                if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
                    return _reject(f"{token} requires a value")
                i += 2
                continue
            return _reject(f"pytest option not allowed: {token}")
        i += 1  # positional test id / relative path (global rules applied)
    return argv, None


def parse_shell_argv(command: str) -> list[str] | None:
    """Compat wrapper: argv when allowed, else None."""
    return parse_shell_command(command)[0]


class QualificationError(Exception):
    """Fail-closed qualification abort."""


class HostError(QualificationError):
    """Reference host unavailable / misbehaving (QF-008)."""


class ScoreError(QualificationError):
    """score_product / bench pack failure (QF-008)."""


class IoError(QualificationError):
    """Disk I/O failure (QF-008)."""


class SchemaValidationError(QualificationError):
    """Artifact failed its JSON Schema (QF-008): the document is not written."""


SCHEMA_DIR = REPO / "scripts" / "schemas"


def validate_document(kind: str, doc: dict) -> None:
    """QF-008: validate an artifact against its JSON Schema (draft 2020-12)."""
    import jsonschema

    schema = json.loads((SCHEMA_DIR / f"{kind}.schema.json").read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise SchemaValidationError(f"{kind} validation failed: {details}")


def classify_exception(ex: BaseException) -> str:
    """QF-008: map an exception to a run-error class."""
    import socket
    import urllib.error

    if isinstance(ex, SchemaValidationError):
        return "schema_error"
    if isinstance(ex, ScoreError):
        return "score_error"
    if isinstance(ex, HostError):
        return "host_error"
    if isinstance(ex, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
        return "host_error"
    if isinstance(ex, OSError):
        return "io_error"
    return "internal_error"


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

    # QF-015: the tokenizer is probed fail-closed (absent = blocked) and its
    # counts must agree with the completion usage on the calibration text.
    tokenizer = _probe_tokenizer(base_url)
    _assert_tokenizer_consistency(
        base_url, REFERENCE_MODEL_ID, tokenizer["calibration_tokens"]
    )

    return {
        # QF-007: every mandatory field is provenance-tagged (measured /
        # declared), attested by attest_manifest_model before the manifest
        # is written.
        "id": _attest(REFERENCE_MODEL_ID, "measured", method="GET /v1/models"),
        "host": _attest(host, "declared",
                        basis="runner invocation flag; the only supported host is 'lm-studio'"),
        "host_base_url": _attest(base_url, "declared",
                                 basis="runner construction: single local endpoint (HOST_BASE_URL)"),
        "context_window_tokens": _attest(context_length, "measured",
                                         method="GET /api/v0/models max_context_length"),
        "context_window_tokens_required": _attest(
            CONTEXT_WINDOW_TOKENS, "declared",
            basis="DF3-009 reference contract (backlog/product/v3/thresholds.md)",
        ),
        "model_state": _attest(state, "measured", method="GET /api/v0/models state"),
        "model_params": _attest(
            {k: info.get(k)
             for k in ("type", "publisher", "arch", "quantization", "state")
             if info.get(k) is not None},
            "measured", method="GET /api/v0/models",
        ),
        "probe_prompt_tokens": _attest(prompt_tokens, "measured",
                                       method="diagnostic completion usage"),
        "tokenizer": tokenizer,
        # The absence of a cloud fallback is proved by runner construction,
        # not by a measurement (test_no_second_transport). It is published as
        # a declared invariant, never as a fact.
        "cloud_fallback": _attest(
            False, "declared",
            basis="runner builds a single local endpoint (HOST_BASE_URL); no "
                  "other transport exists in the runner code (test_no_second_"
                  "transport); OS-level egress is not attested at L1",
        ),
        "loaded_models": _attest(ids, "measured", method="GET /v1/models"),
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
        self.staging_escapes = 0
        self.unique_files: set[str] = set()
        self.events: list[ToolEvent] = []
        self._seq = 0
        self._call_index = 0
        self.write_envelope: EnvelopeState | None = None
        # globs that authorized the most recent successful write (QF-003 hook)
        self.last_write_envelope_globs: list[str] = []
        # QF-003: injected by drive_worker; returns the changed-path inventory
        # so shell side effects are attributed to the shell event.
        self.inventory_fn = None
        # QF-004: staging hooks — minimal command environment, the controlled
        # interpreter (substituted for the `python` token) and the escape
        # walker (new files in staging outside the work dir since last call).
        self.exec_env: dict | None = None
        self.interpreter: str | None = None
        self.escape_check_fn = None

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
            # QF-006: unresolvable path = hallucinated (T6), not T7.
            self.hallucinated_paths += 1
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
        argv, reason = parse_shell_command(command)
        if argv is None:
            # QF-006: classify the refusal — invented tool/path (T6) vs
            # execution-policy boundary (T7).
            if _reason_is_hallucination(f"rejected: {reason}"):
                self.hallucinated_paths += 1
            else:
                self.envelope_violations += 1
            self._record("shell", f"rejected: {reason}", command=command[:200])
            return f"ERROR: command not allowed: {reason}"
        # QF-004/QF-005: Worker commands execute with the controlled staging
        # interpreter — `python ...` and `pytest ...` are canonized at the
        # execution boundary, never resolved through a stray PATH.
        if self.interpreter:
            head = argv[0].lower()
            if head == "python":
                argv = [self.interpreter, *argv[1:]]
            elif head == "pytest":
                argv = [self.interpreter, "-m", "pytest", *argv[1:]]
        before = dict(self.inventory_fn()) if self.inventory_fn else {}
        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self.exec_env,
            )
        except subprocess.TimeoutExpired:
            self._record("shell", f"error: timed out after {timeout}s",
                         command=" ".join(argv), exit_code=None)
            return f"ERROR: command timed out after {timeout}s"
        except OSError as ex:
            self._record("shell", f"error: cannot execute: {ex}", command=" ".join(argv))
            return f"ERROR: cannot execute: {ex}"
        # QF-003: paths changed by the command itself (inventory diff) are
        # attributed to this shell event.
        changed: list[str] = []
        if self.inventory_fn:
            after = dict(self.inventory_fn())
            changed = sorted(p for p in after if before.get(p) != after.get(p))
        outcome = "ok" if proc.returncode == 0 else f"error: exit {proc.returncode}"
        if proc.returncode == 4:
            # QF-006: pytest usage error = file/module not found = T6.
            self.hallucinated_paths += 1
        # QF-004: anything appearing in staging outside the work dir is an
        # escape, whatever the command's own exit code.
        escaped = self.escape_check_fn() if self.escape_check_fn else []
        if escaped:
            self.staging_escapes += len(escaped)
            outcome += f"; staging_escape: {','.join(escaped[:5])}"
        self._record("shell", outcome,
                     paths_written=changed, command=" ".join(argv), exit_code=proc.returncode)
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


def _core_leash_violations(sandbox: Path, files: list[str]) -> tuple[int, list[str]]:
    """T7: run the Core leash over a stage write-set; returns (count, details)."""
    import contextlib
    import io as _io

    from deltafuse.cli import main as cli_main

    if not files:
        return 0, []
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = cli_main(["leash", str(sandbox), "--json", "--files", *files])
        data = json.loads(buf.getvalue() or "{}")
    except Exception:
        return 1, ["uninterpretable Core answer"]  # fail-closed
    if code not in (0, 1) or not isinstance(data, dict):
        return 1, ["uninterpretable Core answer"]
    violations = [str(v) for v in (data.get("violations") or [])]
    return len(violations), violations


def drive_worker(
    sandbox: Path, base_url: str, model: str, case_id: str, system: str,
    staging=None,
) -> dict:
    """Drive the Worker agent loop in one clean sandbox; return call metrics.

    T4: input tokens come from the host usage; framework-controlled input is
    measured separately (system prompt + Core/tool responses). A call with no
    usage measurement leaves the peak unmeasured (fail-closed in T4).
    T5: unique files are counted per call, including the last tool action.
    T7 (QF-003): the sandbox is a git repo maintained by the runner. Around
    every shell command and stage boundary the actual changed-path inventory
    is taken from git, not from local counters. On `deltafuse advance`
    (detected by argv, not output substrings) the Core leash runs BEFORE the
    advance, while the ready step still belongs to the closing stage, so the
    write-set is judged by the envelope that was in force at write time;
    running it after the advance would judge closed-stage writes by the next
    stage's envelope — the false-classification defect this avoids. After the
    advance, journal-vs-inventory reconciliation catches unjournaled changes,
    then the runner makes a bookkeeping commit for the next stage.
    QF-004: when `staging` is given, commands run with the staging's minimal
    environment and the escape walker counts files appearing outside the work
    dir (`staging_escape`); see backlog/product/v3/qualification-threat-model.md.
    """
    seed = f"Begin the case {case_id}. Run `deltafuse next` first."
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": seed},
    ]
    # QF-006: provenance per message — product content (file bodies, test
    # output) never counts into the framework-controlled input of T4.
    message_meta: list[dict] = [
        {"origin": "system", "source": "system-prompt", "content": system},
        {"origin": "framework", "source": "seed", "content": seed},
    ]
    io = SandboxIO(sandbox)
    expected_head = init_sandbox_git(sandbox)
    head = {"sha": expected_head}
    io.inventory_fn = lambda: inventory(sandbox, head["sha"])
    if staging is not None:
        io.exec_env = staging.env()
        io.interpreter = staging.interpreter()
        io.escape_check_fn = staging.escape_walker()
    calls: list[dict] = []
    unmeasured_usage = False
    stage_writes: set[str] = set()
    stage_leash: list[dict] = []
    breakdown = {
        "write_denied": 0,
        "leash_violations": 0,
        "unjournaled_change": 0,
        "inventory_tampered": 0,
        "staging_escape": 0,
    }
    for _ in range(MAX_WORKER_TURNS):
        io.begin_call()
        envelope = _core_envelope(sandbox)
        io.write_envelope = envelope
        if envelope.status == "error":
            # QF-001: a Core failure blocks the stage; the run aborts instead
            # of continuing with unrestricted writes.
            breakdown["write_denied"] = io.envelope_violations
            return _final_metrics(
                io, calls, unmeasured_usage,
                envelope_error=envelope.detail, breakdown=breakdown, stage_leash=stage_leash,
            )
        turn = worker_turn(base_url, model, messages)
        prompt_tokens = turn["prompt_tokens"]
        if not prompt_tokens:
            unmeasured_usage = True
        # QF-006: framework-controlled input of this call, from provenance
        # tags only (system prompt + seed + Core responses + runner protocol).
        framework_chars = len(system) + sum(
            len(m["content"]) for m in message_meta if m["origin"] == "framework"
        )
        framework_text = system + "".join(
            m["content"] for m in message_meta if m["origin"] == "framework"
        )
        # QF-015: framework measurement states — host-tokenize (measured) or
        # estimated-nonrelease (diagnostics only, never a pass). `unavailable`
        # is a blocking state handled by the probe before any Worker call.
        host_tokens = _host_tokenize(base_url, framework_text)
        if isinstance(host_tokens, int) and host_tokens > 0:
            framework_tokens, framework_method = host_tokens, "host-tokenize"
        else:
            framework_tokens, framework_method = (
                framework_chars // 4, "estimated-nonrelease"
            )
        messages.append({"role": "assistant", "content": turn["content"]})
        action = parse_action(turn["content"])
        tool = str(action.get("tool"))
        is_advance = False
        try:
            if tool == "done":
                result = None
            elif tool == "read_file":
                result = io.read_file(str(action.get("path")))
                message_meta.append({"origin": "product", "source": "file-read", "content": result})
            elif tool == "write_file":
                result = io.write_file(str(action.get("path")), str(action.get("content")))
                message_meta.append({"origin": "framework", "source": "runner-protocol", "content": result})
            elif tool == "shell":
                command = str(action.get("command"))
                argv = parse_shell_argv(command)
                is_advance = bool(
                    argv and len(argv) >= 2
                    and argv[0].lower() == "deltafuse" and argv[1].lower() == "advance"
                )
                if is_advance:
                    # QF-003: leash BEFORE the advance — the closing stage's
                    # write-set against the envelope of the write time.
                    count, details = _core_leash_violations(sandbox, sorted(stage_writes))
                    breakdown["leash_violations"] += count
                    stage_leash.append(
                        {"stage_write_set": sorted(stage_writes), "violations": details}
                    )
                result = io.shell(command)
                core_command = command.strip().lower().startswith("deltafuse")
                message_meta.append({
                    "origin": "framework" if core_command else "product",
                    "source": "core-command" if core_command else "shell-noncore",
                    "content": result,
                })
            else:
                result = f"ERROR: unknown tool {tool}"
                io._record("unknown", f"error: unknown tool {tool}")
                io.hallucinated_paths += 1
                message_meta.append({"origin": "framework", "source": "runner-protocol", "content": result})
        except QualificationError as ex:
            # Tamper guard fired mid-stage: block the run fail-closed.
            breakdown["inventory_tampered"] += 1
            return _final_metrics(
                io, calls, unmeasured_usage,
                envelope_error=str(ex), breakdown=breakdown, stage_leash=stage_leash,
            )
        if io.events:
            stage_writes.update(io.events[-1].paths_written)
        if is_advance and result.startswith("exit=0"):
            # Post-advance: every changed path must be in the journal.
            inv = inventory(sandbox, head["sha"])
            unjournaled = sorted(
                p for p in inv
                if p not in stage_writes and not p.startswith(CORE_OWNED_PREFIX)
            )
            if unjournaled:
                breakdown["unjournaled_change"] += len(unjournaled)
            # Bookkeeping commit: clean, known base for the next stage.
            head["sha"] = _bookkeeping_commit(
                sandbox, f"stage close (runner bookkeeping): {len(stage_writes)} paths"
            )
            stage_writes = set()
        if result is not None:
            messages.append({"role": "user", "content": result[:6000]})
        # QF-002: the call is measured AFTER its tool action ran, so the last
        # action of a call is included in unique_files.
        calls.append(
            {
                "input_tokens": prompt_tokens or None,
                "framework_input_chars": framework_chars,
                "framework_input_tokens": framework_tokens,
                "framework_input_tokens_method": framework_method,
                "unique_files": len(io.call_paths(io.call_index)),
                "hallucinated_paths": io.hallucinated_paths,
                "envelope_violations": io.envelope_violations,
            }
        )
        if tool == "done":
            break
    breakdown["write_denied"] = io.envelope_violations
    breakdown["staging_escape"] = io.staging_escapes
    return _final_metrics(
        io, calls, unmeasured_usage, breakdown=breakdown, stage_leash=stage_leash
    )


def _final_metrics(
    io: SandboxIO,
    calls: list[dict],
    unmeasured_usage: bool,
    envelope_error: str | None = None,
    breakdown: dict | None = None,
    stage_leash: list[dict] | None = None,
) -> dict:
    from dataclasses import asdict

    if breakdown is None:
        breakdown = {}
    # QF-006: counters are derived from the typed journal, not from local
    # increments scattered over event sites.
    classification = classify_violations([asdict(e) for e in io.events])
    breakdown.setdefault("write_denied", classification["envelope"])
    breakdown.setdefault("leash_violations", 0)
    breakdown.setdefault("unjournaled_change", 0)
    breakdown.setdefault("inventory_tampered", 0)
    breakdown.setdefault("staging_escape", io.staging_escapes)
    breakdown["execution_policy"] = classification["execution_policy"]
    peaks = [c["input_tokens"] for c in calls if c["input_tokens"] is not None]
    fw = [c["framework_input_tokens"] for c in calls]
    fw_chars = [c["framework_input_chars"] for c in calls]
    fw_methods = {c["framework_input_tokens_method"] for c in calls}
    total_t7 = sum(int(v) for v in breakdown.values())
    metrics = {
        "calls": calls,
        "context_peak_tokens": max(peaks) if peaks and not unmeasured_usage else None,
        "framework_input_tokens_max": max(fw) if fw else None,
        "framework_input_chars_max": max(fw_chars) if fw_chars else None,
        "framework_input_tokens_method": (
            "host-tokenize" if fw_methods == {"host-tokenize"}
            else "estimated-nonrelease" if fw_methods == {"estimated-nonrelease"}
            else "unavailable" if fw_methods == {"unavailable"}
            else "mixed"
        ),
        "max_unique_files": max((c["unique_files"] for c in calls), default=0),
        "hallucinated_paths": classification["hallucinated"],
        "hallucinated_breakdown": classification,
        "envelope_violations": total_t7,
        "t7_breakdown": breakdown,
        "stage_leash": stage_leash or [],
        "tool_events": [asdict(e) for e in io.events],
    }
    if envelope_error:
        metrics["envelope_error"] = envelope_error
    return metrics


# -------------------------------------------------------------- thresholds


def evidence_authentic(report: dict) -> bool:
    """QF-006: authentic evidence = every mandatory check present AND passed."""
    defense = report.get("defense_checks") or {}
    if any(k not in defense for k in REQUIRED_T8_CHECKS):
        return False
    return all(
        isinstance(defense[k], dict) and defense[k].get("pass") is True
        for k in REQUIRED_T8_CHECKS
    )


def check_exact_lifecycle(stage_rows: list[dict]) -> tuple[bool, list[str]]:
    """QF-014: T2 is the EXACT lifecycle — canonical names in canonical
    order, each present exactly once, every status completed. Seven
    arbitrary or eight stages never pass."""
    expected = list(LIFECYCLE)
    present = [str(row.get("stage")) for row in stage_rows]
    failures: list[str] = []
    counts: dict[str, int] = {}
    for name in present:
        counts[name] = counts.get(name, 0) + 1
    duplicated = sorted(name for name, count in counts.items() if count > 1)
    missing = [name for name in expected if counts.get(name, 0) == 0]
    unknown = sorted(set(present) - set(expected))
    if missing or unknown or duplicated:
        failures.append(
            f"T2 stages: expected exactly {expected} once each; "
            f"missing={missing} unknown={unknown} duplicated={duplicated} got={present}"
        )
    elif present != expected:
        failures.append(f"T2 stage order: expected {expected}, got {present}")
    else:
        bad = [
            f"{row.get('stage')}={row.get('status')}"
            for row in stage_rows
            if row.get("status") != "completed"
        ]
        if bad:
            failures.append(f"T2 stages not completed: {bad}")
    return (not failures), failures


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
    # T2 (QF-014): the EXACT lifecycle — canonical names, order, once each,
    # all completed. A count comparison is never used.
    t2_rows = [
        {
            "stage": name,
            "status": "completed" if row.get("pass") else "failed",
            "gate_retries": int(row.get("gate_retries") or 0),
        }
        for name, row in stages.items()
    ]
    t2_ok, t2_failures = check_exact_lifecycle(t2_rows)
    failures.extend(t2_failures)
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
    fw_chars = metrics.get("framework_input_chars_max")
    if fw_chars is None:
        fw_chars = metrics.get("framework_input_chars")
    if not isinstance(peak, int):
        failures.append("T4 context_peak_tokens=unmeasured")
    elif peak > ABSOLUTE["context_peak_tokens_max"]:
        failures.append(f"T4 context_peak_tokens={peak}")
    if not isinstance(fw, int):
        failures.append("T4 framework_input_tokens=unmeasured")
    elif fw > ABSOLUTE["framework_input_tokens_max"]:
        failures.append(f"T4 framework_input_tokens={fw}")
    # QF-006: exact framework characters must be present (provenance-based).
    if not isinstance(fw_chars, int):
        failures.append("T4 framework_input_chars=unmeasured")
    # QF-015: the framework token measurement must come from the host
    # tokenizer; estimates and unavailable states never support a pass.
    method = metrics.get("framework_input_tokens_method")
    if method != "host-tokenize":
        failures.append(
            f"T4 framework_input_tokens={method or 'unmeasured'} "
            "(release requires a measured host tokenizer)"
        )
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
    # QF-003: any nonzero inventory/leash component fails, independently.
    breakdown = metrics.get("t7_breakdown")
    if breakdown and any(
        breakdown.get(k)
        for k in ("leash_violations", "unjournaled_change", "inventory_tampered", "staging_escape")
    ):
        failures.append(f"T7 stage_inventory={breakdown}")
    # T8: authentic evidence — the mandatory check set must be present and
    # pass; absence of proof is a failure, never an implicit pass (QF-006).
    defense = report.get("defense_checks") or {}
    missing = sorted(k for k in REQUIRED_T8_CHECKS if k not in defense)
    failed = sorted(
        k for k, v in defense.items()
        if not (isinstance(v, dict) and v.get("pass") is True)
    )
    if missing:
        failures.append(f"T8 evidence_missing={','.join(missing)}")
    if failed:
        failures.append(f"T8 evidence_authentic=false ({','.join(failed)})")
    if not report.get("pass"):
        failures.append(f"T1/T2 report.first_fail={report.get('first_fail')}")
    return (not failures), failures


def medians(runs: list[dict]) -> dict:
    def med(key: str) -> float | None:
        values = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
        return round(float(statistics.median(values)), 1) if values else None

    return {
        "correctness": med("correctness"),
        "process": med("process"),
        "context_peak_tokens": med("context_peak_tokens"),
        "framework_input_tokens_max": med("framework_input_tokens_max"),
        "framework_input_chars_max": med("framework_input_chars_max"),
        "gate_retries": med("gate_retries"),
        "max_unique_files": med("max_unique_files"),
        "hallucinated_paths": med("hallucinated_paths"),
        "envelope_violations": med("envelope_violations"),
    }


def evaluate_medians(med: dict, runs: list[dict]) -> tuple[bool, list[str]]:
    """QF-008: median boundaries T3-T7 plus T8 completeness over actual runs.

    T1/T2 are per-run facts (a case with a failed run is already failed);
    carrier stubs are not used any more.
    """
    failures: list[str] = []

    def check(label: str, value, limit) -> None:
        # QF-014: NaN is never a measurement; booleans are never numbers.
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value != value
        ):
            failures.append(f"{label}=unmeasured")
        elif value > limit:
            failures.append(f"{label}={value}")

    check("T4 median context_peak_tokens", med.get("context_peak_tokens"),
          ABSOLUTE["context_peak_tokens_max"])
    check("T4 median framework_input_tokens", med.get("framework_input_tokens_max"),
          ABSOLUTE["framework_input_tokens_max"])
    check("T5 median max_unique_files", med.get("max_unique_files"),
          ABSOLUTE["max_unique_files"])
    retries = med.get("gate_retries")
    if not isinstance(retries, (int, float)) or isinstance(retries, bool) or retries != retries:
        failures.append("T3 median gate_retries=unmeasured")
    elif retries > ABSOLUTE["gate_retries_max"]:
        failures.append(f"T3 median gate_retries={retries}")
    # QF-014: median correctness and median process are threshold-checked
    # explicitly, even when every per-run verdict was already checked.
    for label, key in (("T1 median correctness", "correctness"),
                       ("T2 median process", "process")):
        value = med.get(key)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value != value
        ):
            failures.append(f"{label}=unmeasured")
        elif value < 0 or value > 100:
            failures.append(f"{label}={value} outside 0..100")
        elif value < 100:
            failures.append(f"{label}={value} < 100")
    if not runs:
        failures.append("median: no completed runs")
        return False, failures
    for label, key in (("T6", "hallucinated_paths"), ("T7", "envelope_violations")):
        values = [r.get(key) for r in runs]
        if any(v is None for v in values):
            failures.append(f"{label} median {key}=unmeasured")
        elif sum(int(v or 0) for v in values) > 0:
            failures.append(f"{label} median {key}>0")
    if not all(r.get("evidence_authentic") for r in runs):
        failures.append("T8 median evidence_authentic=false")
    return not failures, failures


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


# ------------------------------------------- QF-003: inventory & stage leash

GITIGNORE_LINES = ("__pycache__/", ".pytest_cache/", "*.pyc", ".venv/")
# Core-owned state is legitimately rewritten by deltafuse commands; it never
# counts as an unjournaled Worker change.
CORE_OWNED_PREFIX = ".deltafuse/"


def _git(args: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=str(cwd)
    )
    if check and proc.returncode != 0:
        raise QualificationError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()[:200]}"
        )
    return proc.stdout


def init_sandbox_git(sandbox: Path) -> str:
    """QF-003: make the sandbox a git repo (judge side) and return HEAD.

    The Worker never commits; only the runner makes bookkeeping commits so
    each stage starts from a clean, known tree.
    """
    _git(["init", "-q"], sandbox, check=False)
    _git(["config", "user.name", "deltafuse-qualification"], sandbox, check=False)
    _git(["config", "user.email", "qualification@deltafuse.invalid"], sandbox, check=False)
    gitignore = sandbox / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("\n".join(GITIGNORE_LINES) + "\n", encoding="utf-8")
    has_head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        capture_output=True, cwd=str(sandbox),
    ).returncode == 0
    if not has_head:
        _git(["add", "-A"], sandbox)
        _git(["commit", "-q", "-m", "bench init (runner bookkeeping)"], sandbox)
    return _git(["rev-parse", "HEAD"], sandbox).strip()


def inventory(sandbox: Path, expected_head: str | None = None) -> dict[str, str]:
    """QF-003: actual changed-path inventory (`git status --porcelain -uall`).

    Tamper-guard: a HEAD that no longer matches the runner's last bookkeeping
    commit means Worker code touched `.git` — the stage is blocked.
    """
    if expected_head is not None:
        head = _git(["rev-parse", "HEAD"], sandbox, check=False).strip()
        if head != expected_head:
            raise QualificationError(
                f"inventory_tampered: sandbox HEAD {head[:12]!r} does not match "
                f"bookkeeping commit {expected_head[:12]!r}"
            )
    out = _git(["status", "--porcelain", "-uall"], sandbox)
    result: dict[str, str] = {}
    for line in out.splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:].strip()
        if "->" in path:  # rename: both sides count as changed
            old, new = (p.strip() for p in path.split("->"))
            result[old] = status
            result[new] = status
        else:
            result[path] = status
    return dict(sorted(result.items()))


def _bookkeeping_commit(sandbox: Path, message: str) -> str:
    _git(["add", "-A"], sandbox)
    _git(["commit", "-q", "--allow-empty", "-m", message], sandbox)
    return _git(["rev-parse", "HEAD"], sandbox).strip()


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


def _atomic_write_yaml_validated(path: Path, kind: str, data: dict) -> None:
    """QF-008: a document that fails its schema is never written."""
    import yaml

    validate_document(kind, data)
    _atomic_write_yaml(path, data)


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


def _system_prompt(sandbox: Path) -> str:
    """Worker system prompt, built only from files inside the sandbox."""
    from deltafuse.bench.init_product import format_worker_start_prompt

    bench_md = (sandbox / "BENCH.md").read_text(encoding="utf-8")
    return (
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


def _run_worker_in_boundary(executor, sandbox: Path, model_probe: dict, case_id: str) -> dict:
    """QF-013: run the Worker phase INSIDE the isolated boundary container.

    Mounts: the run sandbox read/write plus the single runner script
    read-only. The judge pack and the framework checkout are never mounted;
    the endpoint is reached through the host gateway alias.
    """
    base_url = model_probe["host_base_url"]["value"].replace(
        "127.0.0.1", "host.docker.internal"
    )
    qual_script = Path(__file__).resolve()
    cmd = [
        executor.runtime, "run", "--rm",
        "--add-host", "host.docker.internal:host-gateway",
        "-v", f"{sandbox}:/sandbox",
        "-v", f"{qual_script}:/opt/qualify.py:ro",
        "-w", "/sandbox",
        executor.image,
        "python", "/opt/qualify.py",
        "--boundary-run",
        "--sandbox", "/sandbox",
        "--base-url", base_url,
        "--model", model_probe["id"]["value"],
        "--case", case_id,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
    metrics_path = sandbox / ".qual-metrics.json"
    if proc.returncode != 0 or not metrics_path.is_file():
        raise HostError(
            f"boundary worker run failed (exit {proc.returncode}): "
            f"{((proc.stderr or '') + (proc.stdout or ''))[-400:]}"
        )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics_path.unlink()
    return metrics


def run_case(case_id: str, index: int, campaign_id: str, model_probe: dict,
             provenance_info: dict, executor_kind: str = "local-dev",
             executor=None) -> dict:
    """One clean run: sandbox -> worker loop -> score -> thresholds."""
    from deltafuse.bench.init_product import init_bench_product
    from deltafuse.bench.score import score_product

    commit = provenance_info["commit"]
    run_id = f"{campaign_id}-{case_id}-run{index}"
    sandbox = RUNS_DIR / campaign_id / run_id / "sandbox"
    if sandbox.exists():
        raise QualificationError(f"sandbox already exists: {sandbox}")
    init_bench_product(case_id, sandbox, framework_root=REPO)

    if executor_kind == "isolated":
        # QF-013: release campaigns execute the Worker inside the system
        # boundary; the in-process runner would violate the isolation
        # invariant and is never used here.
        metrics = _run_worker_in_boundary(executor, sandbox, model_probe, case_id)
    else:
        # local-dev only (QF-013): L1 staging work copy, capped at
        # non-release verdicts by the executor.
        from qualify_staging import StagingRoot

        staging = StagingRoot.create(
            RUNS_DIR / campaign_id / "staging", build_venv=False, framework_root=REPO
        )
        work = staging.new_workdir(run_id, sandbox)
        system = _system_prompt(sandbox)
        metrics = drive_worker(
            work, model_probe["host_base_url"]["value"],
            model_probe["id"]["value"], case_id, system, staging=staging,
        )
        staging.collect_workdir(run_id, sandbox)
        staging.teardown()
    try:
        scorecard = score_product(sandbox, pack_root=str(CASES_ROOT))
    except Exception as ex:
        raise ScoreError(f"score_product failed: {ex}") from ex
    verdict, failures = apply_thresholds(scorecard, metrics)

    per_run = _build_run_report(
        run_id, case_id, commit, model_probe["id"]["value"],
        scorecard, metrics, verdict, failures,
    )
    run_dir = RUNS_DIR / campaign_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # QF-008: report.yaml per thresholds.md format, schema-validated; the raw
    # scorecard is kept next to it as diagnostics; writes are atomic.
    _atomic_write_yaml(run_dir / "scorecard.yaml", scorecard)
    _atomic_write_yaml_validated(run_dir / "report.yaml", "run-report", per_run)
    return per_run


def _build_run_report(
    run_id: str, case_id: str, commit: str, model_id: str,
    scorecard: dict, metrics: dict, verdict: bool, failures: list[str],
) -> dict:
    """QF-008: scorecard + metrics -> per-run report per thresholds.md."""
    stages_out = []
    checks_passed = 0
    checks_total = 0
    for name, row in (scorecard.get("stages") or {}).items():
        passed = int(row.get("checks_passed") or 0)
        total = int(row.get("checks_total") or 0)
        checks_passed += passed
        checks_total += total
        stages_out.append(
            {
                "stage": name,
                "status": "completed" if row.get("pass") else "failed",
                "checks": {"passed": passed, "failed": total - passed},
                "gate_retries": int(row.get("gate_retries") or 0),
            }
        )
    # QF-014: process counts only canonical lifecycle stages and is clamped.
    canonical_completed = sum(
        1 for s in stages_out
        if s["stage"] in LIFECYCLE and s["status"] == "completed"
    )
    process = max(0.0, min(100.0, 100.0 * canonical_completed / len(LIFECYCLE)))
    completed = sum(1 for s in stages_out if s["status"] == "completed")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "case": case_id,
        "framework_commit": commit,
        "model": model_id,
        "verdict": "pass" if verdict else "fail",
        "threshold_failures": failures,
        "process": process,
        "correctness": scorecard.get("correctness"),
        "stages": stages_out,
        "calls": metrics["calls"],
        "tool_events": metrics["tool_events"],
        "totals": {
            "correctness": {"passed": checks_passed, "failed": checks_total - checks_passed},
            "gate_retries": int((scorecard.get("retries") or {}).get("check_gate") or 0),
            "context_peak_tokens": metrics["context_peak_tokens"],
            "framework_input_tokens_max": metrics["framework_input_tokens_max"],
            "max_unique_files": metrics["max_unique_files"],
            "hallucinated_paths": metrics["hallucinated_paths"],
            "envelope_violations": metrics["envelope_violations"],
            "evidence_authentic": evidence_authentic(scorecard),
        },
        "framework_input_tokens_method": metrics["framework_input_tokens_method"],
        "t7_breakdown": metrics["t7_breakdown"],
        "hallucinated_breakdown": metrics["hallucinated_breakdown"],
        "stage_leash": metrics["stage_leash"],
    }


def _write_failure_report(
    run_id: str, case_id: str, campaign_id: str, commit: str, model_id: str,
    error_class: str, detail: str,
) -> dict:
    """QF-008: a run that started is never lost — write a validated failure
    report before exiting."""
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "case": case_id,
        "framework_commit": commit,
        "model": model_id,
        "verdict": "fail",
        "threshold_failures": [f"run_error:{error_class}"],
        "stages": [],
        "calls": [],
        "tool_events": [],
        "totals": {
            "correctness": {"passed": None, "failed": None},
            "gate_retries": None,
            "context_peak_tokens": None,
            "framework_input_tokens_max": None,
            "max_unique_files": None,
            "hallucinated_paths": None,
            "envelope_violations": None,
            "evidence_authentic": False,
        },
        "error": {"class": error_class, "detail": detail[:400]},
    }
    run_dir = RUNS_DIR / campaign_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_write_yaml_validated(run_dir / "report.yaml", "run-report", report)
    except Exception as write_ex:  # best effort: never mask the original error
        print(f"failure report write failed: {write_ex}", file=sys.stderr)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="lm-studio")
    # QF-013: release campaigns require the isolated executor; the default is
    # fail-closed (PENDING without a boundary), never in-process execution.
    ap.add_argument("--executor", choices=qualify_executor.EXECUTOR_KINDS,
                    default="isolated")
    ap.add_argument("--cases", nargs="+",
                    default=["M01-cooldown", "M02-policy-stats", "M03-adversarial"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--campaign-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    # QF-013: internal mode — executed INSIDE the boundary container only.
    ap.add_argument("--boundary-run", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--sandbox", help=argparse.SUPPRESS)
    ap.add_argument("--base-url", help=argparse.SUPPRESS)
    ap.add_argument("--model", help=argparse.SUPPRESS)
    ap.add_argument("--case", help=argparse.SUPPRESS)
    return ap


def _boundary_run_main(args) -> int:
    """QF-013: Worker phase inside the isolated boundary; writes metrics."""
    sandbox = Path(args.sandbox)
    metrics = drive_worker(sandbox, args.base_url, args.model, args.case, _system_prompt(sandbox))
    (sandbox / ".qual-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return 0


def main_with_args(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.boundary_run:
        return _boundary_run_main(args)

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

    # QF-013: the executor gate comes BEFORE the host probe and any Worker
    # call: without an isolated boundary the campaign stays PENDING.
    try:
        executor = resolve_executor(args.executor)
    except qualify_executor.ExecutorError as ex:
        print(
            f"PENDING: {ex}\n"
            "Release qualification does not execute Worker-authored code "
            "outside an isolated boundary. Provide a container runtime and "
            "DELTAFUSE_QUAL_IMAGE, or run --executor local-dev for "
            "development only (verdict capped at non-release)."
        )
        return 2

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
    try:
        attest_manifest_model(model_probe)
    except QualificationError as ex:
        print(f"QUALIFICATION ERROR: {ex}", file=sys.stderr)
        return 3
    print(
        f"host probe ok: model={model_probe['id']['value']} "
        f"context={model_probe['context_window_tokens']['value']}"
    )

    campaign_dir = RUNS_DIR / args.campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    executor_attestation = executor.attest()
    if executor.kind == "isolated":
        # QF-013: the adversarial boundary probe runs INSIDE the actual
        # boundary before the first Worker call; any leak blocks the campaign.
        import secrets
        import socket as _socket
        import tempfile

        sentinel = campaign_dir / ".judge-sentinel"
        sentinel.write_text(secrets.token_hex(32), encoding="utf-8")
        with _socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            forbidden_peer = f"127.0.0.1:{listener.getsockname()[1]}"
        try:
            probe = executor.boundary_probe(
                campaign_dir, sentinel,
                search_roots=["/"],
                write_roots=[str(REPO), tempfile.gettempdir(), str(Path.home())],
                forbidden_peer=forbidden_peer,
            )
            qualify_executor.assert_boundary_clean(probe)
        except (qualify_executor.BoundaryViolation, qualify_executor.ExecutorError) as ex:
            print(f"PENDING: release boundary not clean: {ex}", file=sys.stderr)
            return 2
        finally:
            sentinel.unlink(missing_ok=True)
        executor_attestation = executor.attest(probe_report=probe)
        print("boundary probe ok: sentinel/pack/write/network all blocked")

    manifest = {
        "schema_version": 1,
        "campaign_id": args.campaign_id,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framework": {
            "commit": commit,
            "lock_hash": provenance_info["lock_hash"],
        },
        "executor": executor_attestation,
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
    aborted = False
    write_error: str | None = None
    for case in args.cases:
        case_runs: list[dict] = []
        for index in range(1, args.runs + 1):
            run_id = f"{args.campaign_id}-{case}-run{index}"
            try:
                run = run_case(case, index, args.campaign_id, model_probe,
                               provenance_info, executor_kind=executor.kind,
                               executor=executor)
            except Exception as ex:  # QF-008: classify, persist, keep going
                error_class = classify_exception(ex)
                detail = f"{type(ex).__name__}: {ex}"
                print(f"run failed ({error_class}): {detail}")
                if isinstance(ex, SchemaValidationError):
                    print("  note: failing artifact was NOT written", file=sys.stderr)
                run = _write_failure_report(
                    run_id, case, args.campaign_id, commit,
                    model_probe["id"]["value"], error_class, detail,
                )
                manifest["runs"].append(run)
                case_runs.append(run)
                try:
                    _atomic_write_yaml_validated(campaign_dir / "manifest.yaml", "run-manifest", manifest)
                except (SchemaValidationError, OSError) as write_ex:
                    write_error = str(write_ex)
                if error_class == "host_error":
                    # One host per campaign: a host error aborts everything.
                    aborted = True
                    break
                continue
            manifest["runs"].append(run)
            case_runs.append(run)
            print(f"{run['run_id']}: {run['verdict']} {run['threshold_failures'] or ''}")
            # Atomic manifest refresh after EVERY run: partial results survive.
            try:
                _atomic_write_yaml_validated(campaign_dir / "manifest.yaml", "run-manifest", manifest)
            except (SchemaValidationError, OSError) as ex:
                write_error = str(ex)
        if aborted:
            break
        # QF-008: per-case verdict isolation — no cross-case state.
        med = medians(case_runs)
        median_ok, median_failures = evaluate_medians(med, case_runs)
        case_ok = bool(case_runs) and all(
            r.get("verdict") == "pass" and not r.get("error") for r in case_runs
        )
        case_verdict = "pass" if case_ok and median_ok else "fail"
        manifest["case_verdicts"][case] = {
            "verdict": case_verdict,
            "medians": med,
            "median_failures": median_failures,
        }
        print(f"{case} medians: {med} verdict={case_verdict}")
    complete = len(manifest["runs"]) == len(args.cases) * args.runs
    if aborted:
        manifest["verdict"] = "incomplete"
    else:
        all_cases_pass = bool(manifest["case_verdicts"]) and all(
            v["verdict"] == "pass" for v in manifest["case_verdicts"].values()
        )
        manifest["verdict"] = "pass" if all_cases_pass and complete else "fail"
    # QF-015: tokenizer fingerprint drift invalidates the campaign.
    expected_fp = (model_probe.get("tokenizer") or {}).get("fingerprint")
    try:
        actual_fp = _probe_tokenizer(HOST_BASE_URL).get("fingerprint")
    except QualificationError:
        actual_fp = None
    fingerprint_ok = tokenizer_fingerprint_matches(expected_fp, actual_fp)
    manifest["tokenizer_fingerprint_match"] = _attest(
        fingerprint_ok, "measured",
        method="POST /api/v0/tokenize calibration before vs after campaign",
    )
    if not fingerprint_ok:
        manifest["verdict"] = "fail"
        print("tokenizer fingerprint drifted; campaign invalidated", file=sys.stderr)
    # QF-013: a non-isolated campaign can never produce a release pass.
    apply_executor_verdict_cap(manifest, executor.kind)
    try:
        _atomic_write_yaml_validated(campaign_dir / "manifest.yaml", "run-manifest", manifest)
    except (SchemaValidationError, OSError) as ex:
        write_error = str(ex)
    print(f"campaign verdict: {manifest['verdict']}")
    print(f"campaign recorded under {campaign_dir}")
    if write_error:
        print(f"manifest write error: {write_error}", file=sys.stderr)
        return 4
    if aborted:
        return 3
    if manifest["verdict"] == "non-release":
        print("verdict is non-release: local-dev evidence is not release evidence")
        return 1
    return 0 if manifest["verdict"] == "pass" else 1


def main() -> int:
    return main_with_args()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except QualificationError as ex:
        print(f"QUALIFICATION ERROR: {ex}", file=sys.stderr)
        sys.exit(3)
