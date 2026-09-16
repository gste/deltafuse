"""Deterministic Supervisor / Controller for driving an external worker through the DeltaFuse Process.

This supervisor automates the closed control loop:
1. Runs `deltafuse next --json` on the sandbox to determine current step and state.
2. If ready, passes the step prompt and SKILL.md to the worker (little-coder or callback).
3. Automatically processes expected Human Gates (`spec` acceptance) without inventing decisions.
4. Validates gates with `deltafuse check-gate` and stamps transitions with `deltafuse advance`.
5. Continues stage by stage until `converged` / `verify` is achieved.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def _log(msg: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


@dataclass
class SupervisorStepResult:
    step: str | None
    status: str
    action_taken: str
    halt: dict[str, Any] | None = None
    error: str | None = None


class BenchmarkSupervisor:
    """Supervises a product sandbox through the full DeltaFuse lifecycle."""

    def __init__(
        self,
        sandbox_dir: Path | str,
        *,
        worker_callback: Callable[[str, str], bool] | None = None,
        use_little_coder: bool = False,
        model: str = "poolside/laguna-xs-2.1",
        max_iterations: int = 50,
    ) -> None:
        self.sandbox = Path(sandbox_dir).resolve()
        self.worker_callback = worker_callback
        self.use_little_coder = use_little_coder
        self.model = model
        self.max_iterations = max_iterations
        self._history: list[SupervisorStepResult] = []

    def _run_cmd(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(self.sandbox),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def get_current_state(self) -> dict[str, Any]:
        """Query deltafuse next --json on the sandbox."""
        proc = self._run_cmd([sys.executable, "-m", "deltafuse", "next", "--json"])
        if proc.returncode != 0:
            raise RuntimeError(f"deltafuse next failed ({proc.returncode}):\n{proc.stderr or proc.stdout}")
        try:
            return json.loads(proc.stdout)
        except Exception as ex:
            raise RuntimeError(f"invalid JSON from deltafuse next: {proc.stdout}") from ex

    def find_change_dir(self) -> Path | None:
        """Locate the active Change package directory under docs/changes/."""
        changes_root = self.sandbox / "docs" / "changes"
        if not changes_root.is_dir():
            return None
        candidates = [p for p in changes_root.iterdir() if p.is_dir() and (p / "change.yaml").is_file()]
        return candidates[0] if candidates else None

    def read_skill_prompt(self, step: str) -> str:
        """Load installed SKILL.md for the step."""
        skill_file = self.sandbox / ".agents" / "skills" / step / "SKILL.md"
        if skill_file.is_file():
            return skill_file.read_text(encoding="utf-8")
        return f"Execute lifecycle step: {step}"

    def run_worker_for_step(self, step: str, feedback: str | None = None) -> bool:
        """Invoke the configured worker for the current step with optional gate feedback."""
        skill_text = self.read_skill_prompt(step)
        
        if self.worker_callback:
            return self.worker_callback(step, skill_text)
        
        if self.use_little_coder:
            launcher = "little-coder.cmd" if os.name == "nt" else "little-coder"
            prompt_parts = [
                f"You are the Worker in this DeltaFuse product at {self.sandbox}.",
                f"Working directory: {self.sandbox}",
                f"Current lifecycle step to execute: {step}",
            ]
            if feedback:
                prompt_parts.append(
                    f"\nATTENTION: The previous attempt failed validation with the following gate errors:\n"
                    f"{feedback}\n"
                    f"Please fix all errors strictly according to the schema and instructions below.\n"
                )
            prompt_parts.append(f"Follow the skill instructions below strictly:\n\n{skill_text}\n")
            prompt = "\n".join(prompt_parts)

            cmd = [
                launcher,
                "--model", self.model,
                "--thinking", "medium",
                "-p", prompt,
            ]
            _log(f"[SUPERVISOR] Launching little-coder for step '{step}' (feedback={'yes' if feedback else 'no'})...")
            proc = self._run_cmd(cmd)
            _log(f"[SUPERVISOR] little-coder completed step '{step}' with exit code {proc.returncode}")
            if proc.returncode != 0:
                _log(f"[SUPERVISOR] little-coder stdout:\n{proc.stdout}")
                _log(f"[SUPERVISOR] little-coder stderr:\n{proc.stderr}")
            return proc.returncode == 0

        return True

    def step(self, last_gate_feedback: str | None = None) -> tuple[SupervisorStepResult, str | None]:
        """Execute one iteration of the supervision loop."""
        state = self.get_current_state()
        selected = state.get("selected")
        halt = state.get("halt")

        # 1. Handle Human Gates if halted
        if halt:
            halt_kind = halt.get("kind")
            if halt_kind == "spec":
                chg = self.find_change_dir()
                if chg:
                    dec_proc = self._run_cmd([
                        sys.executable, "-m", "deltafuse", "decide",
                        str(chg), "--spec", "--status", "accepted", "--json"
                    ])
                    return SupervisorStepResult(
                        step="specify",
                        status="gate_accepted",
                        action_taken=f"accepted spec gate: {dec_proc.stdout.strip()}",
                        halt=halt,
                    ), None
            elif halt_kind == "done":
                return SupervisorStepResult(
                    step=None,
                    status="converged",
                    action_taken="product converged successfully",
                    halt=halt,
                ), None
            else:
                return SupervisorStepResult(
                    step=None,
                    status="halted",
                    action_taken=f"halted on kind={halt_kind}",
                    halt=halt,
                ), None

        if not selected:
            return SupervisorStepResult(
                step=None,
                status="no_ready_step",
                action_taken="no ready steps in work queue",
            ), None

        step_name = selected.get("step")
        gate_name = selected.get("gate") or step_name
        chg_path_str = selected.get("change") or str(self.find_change_dir() or "")
        chg_path = Path(chg_path_str) if chg_path_str else self.find_change_dir()

        # 2. Invoke worker
        if step_name and (self.worker_callback or self.use_little_coder):
            worker_ok = self.run_worker_for_step(step_name, feedback=last_gate_feedback)
            if not worker_ok:
                return SupervisorStepResult(
                    step=step_name,
                    status="worker_failed",
                    action_taken="worker execution failed",
                ), last_gate_feedback

        # 3. Check gate and advance if ready
        if chg_path and chg_path.is_dir() and gate_name:
            chk = self._run_cmd([
                sys.executable, "-m", "deltafuse", "check-gate",
                str(chg_path), "--gate", gate_name
            ])
            if chk.returncode == 0:
                adv = self._run_cmd([
                    sys.executable, "-m", "deltafuse", "advance",
                    str(chg_path), "--gate", gate_name, "--json"
                ])
                return SupervisorStepResult(
                    step=step_name,
                    status="advanced",
                    action_taken=f"advanced gate '{gate_name}': {adv.stdout.strip()}",
                ), None
            else:
                gate_err = chk.stderr or chk.stdout
                return SupervisorStepResult(
                    step=step_name,
                    status="gate_blocked",
                    action_taken=f"check-gate '{gate_name}' failed:\n{gate_err}",
                ), gate_err

        return SupervisorStepResult(
            step=step_name,
            status="pending",
            action_taken=f"step {step_name} in progress",
        ), None

    def run_until_complete(self) -> list[SupervisorStepResult]:
        """Run control loop until convergence, unrecoverable stop, or max iterations."""
        results = []
        last_feedback: str | None = None
        for i in range(self.max_iterations):
            res, feedback = self.step(last_gate_feedback=last_feedback)
            results.append(res)
            self._history.append(res)
            _log(f"[{i+1}/{self.max_iterations}] step={res.step} status={res.status} -> {res.action_taken}")
            
            if res.status in ("converged", "halted", "worker_failed", "no_ready_step"):
                break
            if res.status == "gate_blocked" and not (self.worker_callback or self.use_little_coder):
                break
            last_feedback = feedback
            time.sleep(1.0)
        return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeltaFuse Benchmark Supervisor")
    parser.add_argument("sandbox_dir", help="Path to product sandbox directory")
    parser.add_argument("--step-once", action="store_true", help="Execute single supervisor step")
    parser.add_argument("--little-coder", action="store_true", help="Drive local little-coder worker")
    parser.add_argument("--model", default="poolside/laguna-xs-2.1", help="Worker model ID")
    parser.add_argument("--max-iterations", type=int, default=50, help="Maximum supervisor iterations")

    args = parser.parse_args(argv)
    supervisor = BenchmarkSupervisor(
        args.sandbox_dir,
        use_little_coder=args.little_coder,
        model=args.model,
        max_iterations=args.max_iterations,
    )

    if args.step_once:
        res, _ = supervisor.step()
        _log(f"Step outcome: step={res.step}, status={res.status}, action={res.action_taken}")
        return 0 if res.status in ("advanced", "gate_accepted", "converged") else 1

    _log(f"Supervising sandbox: {args.sandbox_dir} (little_coder={args.little_coder}, model={args.model})")
    outcomes = supervisor.run_until_complete()
    final = outcomes[-1] if outcomes else None
    return 0 if final and final.status == "converged" else 1


if __name__ == "__main__":
    sys.exit(main())
