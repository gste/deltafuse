"""Deterministic Supervisor / Controller for driving an external worker through the DeltaFuse Process.

This supervisor automates the closed control loop:
1. Runs `deltafuse next --json` on the sandbox to determine current step and state.
2. If ready, loads the appropriate skill prompt (`SKILL.md`) and passes it to the worker.
3. Automatically processes expected Human Gates (`spec` acceptance) without inventing decisions.
4. Validates gates with `deltafuse check-gate` and stamps transitions with `deltafuse advance`.
5. Continues stage by stage until `converged` / `verify` is achieved.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from deltafuse.core.queue import build_work_queue, load_product_root, queue_snapshot, select_next


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
        max_iterations: int = 50,
    ) -> None:
        self.sandbox = Path(sandbox_dir).resolve()
        self.worker_callback = worker_callback
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
            raise RuntimeError(f"deltafuse next failed ({proc.returncode}):\n{proc.stderr}")
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

    def step(self) -> SupervisorStepResult:
        """Execute one iteration of the supervision loop."""
        state = self.get_current_state()
        selected = state.get("selected")
        halt = state.get("halt")

        # 1. Handle Human Gates if halted
        if halt:
            halt_kind = halt.get("kind")
            if halt_kind == "spec":
                # Spec approval Human Gate: apply accept
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
                    )
            elif halt_kind == "done":
                return SupervisorStepResult(
                    step=None,
                    status="converged",
                    action_taken="product converged successfully",
                    halt=halt,
                )
            else:
                return SupervisorStepResult(
                    step=None,
                    status="halted",
                    action_taken=f"halted on kind={halt_kind}",
                    halt=halt,
                )

        if not selected:
            return SupervisorStepResult(
                step=None,
                status="no_ready_step",
                action_taken="no ready steps in work queue",
            )

        step_name = selected.get("step")
        gate_name = selected.get("gate") or step_name
        chg_path_str = selected.get("change") or str(self.find_change_dir() or "")
        chg_path = Path(chg_path_str) if chg_path_str else self.find_change_dir()

        # 2. Invoke worker if callback provided
        if self.worker_callback and step_name:
            skill_text = self.read_skill_prompt(step_name)
            worker_ok = self.worker_callback(step_name, skill_text)
            if not worker_ok:
                return SupervisorStepResult(
                    step=step_name,
                    status="worker_failed",
                    action_taken="worker callback reported failure",
                )

        # 3. Check gate and advance if ready
        if chg_path and chg_path.is_dir() and gate_name:
            # First check-gate
            chk = self._run_cmd([
                sys.executable, "-m", "deltafuse", "check-gate",
                str(chg_path), "--gate", gate_name
            ])
            if chk.returncode == 0:
                # Advance gate
                adv = self._run_cmd([
                    sys.executable, "-m", "deltafuse", "advance",
                    str(chg_path), "--gate", gate_name, "--json"
                ])
                return SupervisorStepResult(
                    step=step_name,
                    status="advanced",
                    action_taken=f"advanced gate '{gate_name}': {adv.stdout.strip()}",
                )
            else:
                return SupervisorStepResult(
                    step=step_name,
                    status="gate_blocked",
                    action_taken=f"check-gate '{gate_name}' failed:\n{chk.stderr or chk.stdout}",
                )

        return SupervisorStepResult(
            step=step_name,
            status="pending",
            action_taken=f"step {step_name} in progress",
        )

    def run_until_complete(self) -> list[SupervisorStepResult]:
        """Run control loop until convergence, blocked gate without worker, or max iterations."""
        results = []
        for i in range(self.max_iterations):
            res = self.step()
            results.append(res)
            self._history.append(res)
            if res.status in ("converged", "halted", "worker_failed", "no_ready_step"):
                break
            if res.status == "gate_blocked" and not self.worker_callback:
                # Without active worker to fix artifacts, stop loop
                break
            time.sleep(0.5)
        return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeltaFuse Benchmark Supervisor")
    parser.add_argument("sandbox_dir", help="Path to product sandbox directory")
    parser.add_argument("--step-once", action="store_true", help="Execute single supervisor step")
    parser.add_argument("--max-iterations", type=int, default=30, help="Maximum supervisor iterations")

    args = parser.parse_args(argv)
    supervisor = BenchmarkSupervisor(args.sandbox_dir, max_iterations=args.max_iterations)

    if args.step_once:
        res = supervisor.step()
        print(f"Step outcome: step={res.step}, status={res.status}, action={res.action_taken}")
        return 0 if res.status in ("advanced", "gate_accepted", "converged") else 1

    print(f"Supervising sandbox: {args.sandbox_dir}")
    outcomes = supervisor.run_until_complete()
    for idx, out in enumerate(outcomes, 1):
        print(f"[{idx}] step={out.step} status={out.status} -> {out.action_taken}")

    final = outcomes[-1] if outcomes else None
    return 0 if final and final.status == "converged" else 1


if __name__ == "__main__":
    sys.exit(main())
