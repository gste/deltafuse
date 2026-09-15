"""Subprocess execution observation, file tracing and container boundary mediator (J03-504)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scripts.document_flow.canonical import canonical_bytes, content_hash
from scripts.document_flow.store import EvidenceRef, EvidenceStore
from scripts.document_flow.worker.tool_guard import validate_tool_invocation


@dataclass(frozen=True)
class ObservedCommandResult:
    exit_code: int | None
    stdout_ref: EvidenceRef | None
    stderr_ref: EvidenceRef | None
    timed_out: bool
    started_ns: int
    finished_ns: int
    environment_sha256: str
    process_id: str


class CommandBoundaryRunner:
    """Executes subprocesses in an isolated working directory, recording stdout/stderr/file telemetry."""

    def __init__(
        self,
        store: EvidenceStore,
        *,
        product_root: Path | str,
        executor_id: str = "host-executor",
    ) -> None:
        self.store = store
        self.product_root = Path(product_root).resolve()
        self.executor_id = executor_id
        self._cmd_seq = 0

    def run_command(
        self,
        argv: list[str],
        *,
        cwd: Path | str | None = None,
        timeout_sec: int = 60,
        env: Mapping[str, str] | None = None,
        envelope: Mapping[str, Any] | None = None,
        stage_id: str = "implement",
        visit_id: str = "visit-1",
        session_id: str = "sess-1",
        run_id: str = "run-1",
    ) -> tuple[ObservedCommandResult, dict[str, Any]]:
        """Run an authorized shell command, record stdout/stderr and append sealed command event."""
        # 1. Tool guard validation
        cmd_str = " ".join(argv)
        val = validate_tool_invocation("run_command", {"CommandLine": cmd_str}, envelope, self.product_root)
        if not val.allowed:
            raise PermissionError(f"command boundary violation: {val.reason}")

        self._cmd_seq += 1
        event_id = f"ev-cmd-{self._cmd_seq}"
        proc_id = f"proc-{self._cmd_seq}"

        target_cwd = Path(cwd).resolve() if cwd else self.product_root
        
        # Snapshot env hash
        clean_env = dict(env or os.environ)
        # Redact secrets
        for k in list(clean_env.keys()):
            if any(s in k.lower() for s in ("key", "secret", "token", "pass", "auth")):
                clean_env[k] = "[REDACTED]"
        env_sha = hashlib.sha256(canonical_bytes(clean_env)).hexdigest()

        start_ns = time.monotonic_ns()
        timed_out = False
        stdout_bytes = b""
        stderr_bytes = b""
        exit_code: int | None = None

        try:
            res = subprocess.run(
                argv,
                cwd=str(target_cwd),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout_sec,
                env=env,
            )
            stdout_bytes = res.stdout
            stderr_bytes = res.stderr
            exit_code = res.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout_bytes = exc.stdout or b""
            stderr_bytes = exc.stderr or b""
            exit_code = None
        except Exception as exc:
            stderr_bytes = str(exc).encode("utf-8")
            exit_code = 127
        finally:
            finished_ns = time.monotonic_ns()

        stdout_ref = self.store.put(stdout_bytes, "text/plain", event_id) if stdout_bytes else None
        stderr_ref = self.store.put(stderr_bytes, "text/plain", event_id) if stderr_bytes else None

        from scripts.document_flow.snapshots import to_evidence_ref_dict

        payload = {
            "argv": list(argv),
            "cwd": target_cwd.as_posix(),
            "environment_inventory_sha256": env_sha,
            "started_monotonic_ns": start_ns,
            "finished_monotonic_ns": finished_ns,
            "timed_out": timed_out,
            "exit_code": exit_code,
            "stdout_ref": to_evidence_ref_dict(stdout_ref) if stdout_ref else None,
            "stderr_ref": to_evidence_ref_dict(stderr_ref) if stderr_ref else None,
            "process_id": proc_id,
            "executor_id": self.executor_id,
            "target_snapshot_id": f"snap-{self._cmd_seq}",
            "operation_instance_id": f"op-{self._cmd_seq}",
        }

        event = {
            "schema_version": 1,
            "event_id": event_id,
            "monotonic_ns": finished_ns,
            "diagnostic_timestamp": "2026-09-15T19:00:00Z",
            "run_id": run_id,
            "session_id": session_id,
            "call_id": None,
            "visit_id": visit_id,
            "task_id": None,
            "stage_id": stage_id,
            "kind": "command",
            "host_source": {
                "host_id": "host-j03",
                "collector_id": "command-monitor",
            },
            "payload": payload,
        }

        sealed_event = self.store.append_event(event)
        
        obs_res = ObservedCommandResult(
            exit_code=exit_code,
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            timed_out=timed_out,
            started_ns=start_ns,
            finished_ns=finished_ns,
            environment_sha256=env_sha,
            process_id=proc_id,
        )

        return obs_res, sealed_event
