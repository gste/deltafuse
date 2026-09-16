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


class Colors:
    """ANSI color sequences with graceful Windows console fallback."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


# Enable ANSI colors on Windows terminal
if os.name == "nt":
    os.system("")


def log_info(tag: str, message: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Colors.DIM}[{now}]{Colors.RESET} {Colors.BRIGHT_CYAN}{Colors.BOLD}[{tag}]{Colors.RESET} {message}", flush=True)


def log_step(iteration: int, max_iter: int, step: str | None, status: str, action: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_color = Colors.WHITE
    if status in ("advanced", "converged", "gate_accepted"):
        status_color = Colors.BRIGHT_GREEN
    elif status in ("gate_blocked", "worker_failed", "halted"):
        status_color = Colors.BRIGHT_RED
    elif status == "pending":
        status_color = Colors.BRIGHT_YELLOW

    step_label = f"{Colors.BRIGHT_MAGENTA}{Colors.BOLD}{step or 'none':^10}{Colors.RESET}"
    iter_label = f"{Colors.DIM}[{iteration:>2}/{max_iter:>2}]{Colors.RESET}"
    status_label = f"{status_color}{Colors.BOLD}{status:<14}{Colors.RESET}"

    print(f"{Colors.DIM}[{now}]{Colors.RESET} {iter_label} {step_label} | {status_label} | {action}", flush=True)


def log_worker_start(step: str, model: str, feedback: bool) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fb_label = f"{Colors.BRIGHT_YELLOW}(with gate feedback){Colors.RESET}" if feedback else ""
    print(f"{Colors.DIM}[{now}]{Colors.RESET} {Colors.BRIGHT_BLUE}⚙ [WORKER-START]{Colors.RESET} Launching little-coder for {Colors.BOLD}{step}{Colors.RESET} (model: {model}) {fb_label}", flush=True)


def log_worker_done(step: str, exit_code: int, duration_sec: float) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if exit_code == 0:
        res = f"{Colors.BRIGHT_GREEN}{Colors.BOLD}SUCCESS (code 0){Colors.RESET}"
    else:
        res = f"{Colors.BRIGHT_RED}{Colors.BOLD}FAILED (code {exit_code}){Colors.RESET}"
    print(f"{Colors.DIM}[{now}]{Colors.RESET} {Colors.BRIGHT_BLUE}⚙ [WORKER-END]  {Colors.RESET} Completed step {Colors.BOLD}{step}{Colors.RESET} in {duration_sec:.1f}s -> {res}", flush=True)


def log_gate_error(error_text: str) -> None:
    for line in error_text.strip().splitlines():
        print(f"    {Colors.RED}│{Colors.RESET} {line}", flush=True)


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
        thinking: str = "off",
        max_iterations: int = 50,
    ) -> None:
        self.sandbox = Path(sandbox_dir).resolve()
        self.worker_callback = worker_callback
        self.use_little_coder = use_little_coder
        self.model = model
        self.thinking = thinking
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
                "--thinking", self.thinking,
                "-p", prompt,
            ]
            log_worker_start(step, self.model, bool(feedback))
            t0 = time.time()
            proc = self._run_cmd(cmd)
            duration = time.time() - t0
            log_worker_done(step, proc.returncode, duration)

            # Persist full worker execution trace for analysis
            logs_dir = self.sandbox / ".bench" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_base = logs_dir / f"{ts}_{step}"
            try:
                (log_base.with_suffix(".prompt.txt")).write_text(prompt, encoding="utf-8")
                if proc.stdout:
                    (log_base.with_suffix(".stdout.log")).write_text(proc.stdout, encoding="utf-8")
                if proc.stderr:
                    (log_base.with_suffix(".stderr.log")).write_text(proc.stderr, encoding="utf-8")
            except Exception:
                pass

            if proc.returncode != 0:
                if proc.stdout.strip():
                    log_gate_error(proc.stdout)
                if proc.stderr.strip():
                    log_gate_error(proc.stderr)
            return proc.returncode == 0

        return True

    def _git_commit(self, message: str) -> None:
        """Commit current changes in sandbox git repo if git is present."""
        if (self.sandbox / ".git").is_dir():
            self._run_cmd(["git", "add", "."])
            # Check if there is anything to commit
            status = self._run_cmd(["git", "status", "--porcelain"])
            if status.stdout.strip():
                self._run_cmd(["git", "commit", "-m", message])

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
                    self._git_commit("gate(spec): accepted Human Gate for specify")
                    return SupervisorStepResult(
                        step="specify",
                        status="gate_accepted",
                        action_taken=f"accepted spec gate -> {dec_proc.stdout.strip()}",
                        halt=halt,
                    ), None
            elif halt_kind == "done":
                self._git_commit("converged: lifecycle completed successfully")
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
            # Commit worker changes (even if failed/partial, for debug trajectory)
            self._git_commit(f"worker({step_name}): iteration output (success={worker_ok})")
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
                self._git_commit(f"advance({gate_name}): gate passed and state advanced")
                return SupervisorStepResult(
                    step=step_name,
                    status="advanced",
                    action_taken=f"gate '{gate_name}' valid, stamped transition",
                ), None
            else:
                gate_err = chk.stderr.strip() or chk.stdout.strip()
                return SupervisorStepResult(
                    step=step_name,
                    status="gate_blocked",
                    action_taken=f"check-gate '{gate_name}' failed",
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
            log_step(i + 1, self.max_iterations, res.step, res.status, res.action_taken)
            if feedback:
                log_gate_error(feedback)
            
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
        log_step(1, 1, res.step, res.status, res.action_taken)
        return 0 if res.status in ("advanced", "gate_accepted", "converged") else 1

    log_info("SUPERVISOR", f"Starting supervised benchmark run on {Colors.BOLD}{args.sandbox_dir}{Colors.RESET}")
    log_info("CONFIG", f"Worker: little-coder | Model: {args.model} | Max Iterations: {args.max_iterations}")
    print("-" * 80)
    outcomes = supervisor.run_until_complete()
    print("-" * 80)
    final = outcomes[-1] if outcomes else None
    if final and final.status == "converged":
        log_info("SUCCESS", f"Benchmark run {Colors.BRIGHT_GREEN}CONVERGED{Colors.RESET} successfully!")
        return 0
    else:
        log_info("STOP", f"Benchmark run ended with status: {Colors.BRIGHT_RED}{final.status if final else 'unknown'}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
