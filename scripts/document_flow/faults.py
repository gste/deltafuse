"""Measured, run-scoped fault controls for the external J03 judge."""

from __future__ import annotations

from dataclasses import dataclass
import re


class FaultDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class BarrierReceipt:
    barrier_id: str
    acknowledged: bool
    measured_sequence: int


class FaultController:
    def __init__(self, executor, run_id: str):
        self._executor = executor
        self._run_id = run_id

    def kill(self, container_id: str, barrier: BarrierReceipt) -> dict:
        if not barrier.acknowledged or barrier.measured_sequence < 0:
            raise FaultDenied("fault barrier was not acknowledged")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", container_id):
            raise FaultDenied("unsafe container identity")
        inspect = self._executor(
            ["docker", "inspect", "--format", "{{ index .Config.Labels \"dev.deltafuse.run\" }}", container_id],
            cwd=".", timeout=10)
        if inspect.exit_code != 0 or inspect.stdout.strip() != self._run_id:
            raise FaultDenied("container is not owned by this run")
        killed = self._executor(["docker", "kill", container_id], cwd=".", timeout=15)
        if killed.exit_code != 0:
            raise FaultDenied("run-owned fault command failed")
        return {"barrier_id": barrier.barrier_id, "measured_sequence": barrier.measured_sequence,
                "container_id": container_id, "run_id": self._run_id}
