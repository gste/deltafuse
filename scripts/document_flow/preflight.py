"""Preflight environment, dependency, and tool checks for J03 benchmark (J03-507)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    failures: list[str]
    diagnostics: dict[str, Any]


def run_preflight_checks(
    *,
    require_docker: bool = False,
    require_java: bool = False,
    require_worker: bool = False,
    worker_launcher: str = "little-coder",
) -> PreflightResult:
    """Execute preflight checks before launching a benchmark run."""
    failures: list[str] = []
    diag: dict[str, Any] = {}

    # 1. Python check
    diag["python"] = "available"

    # 2. Docker / container runtime check
    if require_docker:
        runtime = shutil.which("docker") or shutil.which("podman")
        if not runtime:
            failures.append("container runtime (docker/podman) not found in PATH")
            diag["docker"] = "missing"
        else:
            try:
                subprocess.check_output([runtime, "version"], stderr=subprocess.DEVNULL)
                diag["docker"] = "ok"
            except Exception as exc:
                failures.append(f"container runtime failed: {exc}")
                diag["docker"] = f"error: {exc}"

    # 3. Java 21 & Maven check
    if require_java:
        java = shutil.which("java")
        mvn = shutil.which("mvn")
        if not java:
            failures.append("java not found in PATH")
            diag["java"] = "missing"
        if not mvn:
            failures.append("mvn not found in PATH")
            diag["mvn"] = "missing"

    # 4. Worker launcher check
    if require_worker:
        worker_bin = shutil.which(worker_launcher)
        if not worker_bin:
            failures.append(f"worker launcher '{worker_launcher}' not found in PATH")
            diag["worker"] = "missing"
        else:
            diag["worker"] = "ok"

    return PreflightResult(
        ok=(len(failures) == 0),
        failures=failures,
        diagnostics=diag,
    )
