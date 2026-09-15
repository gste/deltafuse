"""External little-coder RPC session transport adapter (J03-501)."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


class WorkerTransportError(RuntimeError):
    """Raised when external worker transport fails or protocol is violated."""


@dataclass(frozen=True)
class WorkerEvent:
    event_type: str
    payload: dict[str, Any]
    raw_line: str
    timestamp: float = field(default_factory=time.time)


class LittleCoderTransport:
    """Manages an external little-coder subprocess running in JSON-lines RPC mode."""

    def __init__(
        self,
        profile_path: Path | str,
        *,
        working_dir: Path | str,
        custom_launcher: list[str] | None = None,
        event_callback: Callable[[WorkerEvent], None] | None = None,
    ) -> None:
        self.profile_path = Path(profile_path)
        self.working_dir = Path(working_dir)
        self.custom_launcher = custom_launcher
        self.event_callback = event_callback
        
        # Load profile
        if not self.profile_path.is_file():
            raise WorkerTransportError(f"missing profile: {self.profile_path}")
        self.profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
        
        self.process: subprocess.Popen[str] | None = None
        self._history: list[WorkerEvent] = []
        self._seq = 0

    def start(self) -> None:
        """Launch the external process."""
        if self.process is not None:
            raise WorkerTransportError("process already running")
        
        cmd = self.custom_launcher or [self.profile.get("launcher", "little-coder")]
        cmd.extend(self.profile.get("flags", ["--mode", "rpc"]))
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.working_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except Exception as exc:
            raise WorkerTransportError(f"failed to spawn worker process: {exc}") from exc

    def send_command(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send an authenticated controller command and wait for immediate response."""
        if self.process is None or self.process.poll() is not None:
            raise WorkerTransportError("process is not running")
        
        self._seq += 1
        req_id = f"cmd-{self._seq}"
        req = {
            "id": req_id,
            "type": action,
            "params": params or {},
        }
        
        # Reject unauthorized raw shell command bypasses from worker
        if action in ("bash", "exec") and params and "bypass" in str(params):
            raise WorkerTransportError("unauthorized shell execution bypass rejected")

        payload = json.dumps(req, ensure_ascii=False) + "\n"
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(payload)
            self.process.stdin.flush()
        except Exception as exc:
            raise WorkerTransportError(f"failed to write to worker stdin: {exc}") from exc

        # Read response line
        line = self._readline()
        if not line:
            raise WorkerTransportError("worker process closed stream without response")
        
        try:
            resp = json.loads(line)
        except Exception as exc:
            raise WorkerTransportError(f"invalid JSON from worker: {line}") from exc
        
        return resp

    def prompt(self, message: str) -> None:
        """Send a user prompt to the Worker agent."""
        self.send_command("prompt", {"message": message})

    def pause_for_gate(self) -> dict[str, Any]:
        """Explicitly pause Worker execution at a Human Gate boundary."""
        return self.send_command("pause_session", {"reason": "human_gate"})

    def halt(self) -> None:
        """Cleanly terminate the worker process."""
        if self.process is None:
            return
        try:
            self.send_command("exit", {})
        except Exception:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            self.process.kill()
        finally:
            self.process = None

    def read_events(self) -> Iterator[WorkerEvent]:
        """Read stdout lines and yield WorkerEvents."""
        while True:
            line = self._readline()
            if not line:
                break
            try:
                data = json.loads(line)
            except Exception:
                continue
            ev_type = data.get("type", "unknown")
            ev = WorkerEvent(event_type=ev_type, payload=data, raw_line=line)
            self._history.append(ev)
            if self.event_callback:
                self.event_callback(ev)
            yield ev

    def _readline(self) -> str:
        if self.process is None or self.process.stdout is None:
            return ""
        return self.process.stdout.readline()
