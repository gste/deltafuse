"""Isolated Red test execution and classification for Declare stage."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


AUTHENTIC_RED = "behavioral-mismatch"
COMPILE_ERROR = "product-build-failure"
ALREADY_GREEN = "already-green"
SYNTAX_OR_IMPORT_ERROR = "syntax-or-import-error"
INFRASTRUCTURE_ERROR = "infrastructure-invalid"


@dataclass(frozen=True)
class RedExecutionResult:
    test_path: str
    test_name: str
    test_sha256: str
    exit_code: int
    authentic_red: bool
    failure_category: str
    failure_message: str | None
    duration_ms: int
    stdout: str
    stderr: str


def classify_test_output(exit_code: int, stdout: str, stderr: str) -> tuple[bool, str, str | None]:
    """Classify test output into authentic Red vs build/syntax/already-green."""
    combined = f"{stdout}\n{stderr}"
    
    if exit_code == 0:
        return False, ALREADY_GREEN, "Test passed unexpectedly on unchanged baseline"
    
    # Check compilation / build errors
    compile_markers = ("compilation error", "cannot find symbol", "maven-compiler-plugin", "BUILD FAILURE")
    if any(m.lower() in combined.lower() for m in compile_markers) and not any(f in combined for f in ("AssertionError", "Failed tests:", "FAILURE!")):
        return False, COMPILE_ERROR, "Compilation or build failure"
    
    # Check python syntax / import errors
    if any(m in combined for m in ("SyntaxError", "IndentationError", "ModuleNotFoundError", "ImportError")):
        return False, SYNTAX_OR_IMPORT_ERROR, "Syntax or module import error"
    
    # Check behavioral / assertion failures (Authentic Red)
    red_markers = ("AssertionError", "assertion failed", "assert ", "Failed tests:", "FAILURE!", "Expected:", "but was:")
    if any(m in combined for m in red_markers) or "Tests run:" in combined:
        return True, AUTHENTIC_RED, "Observed expected assertion failure on baseline"
    
    return False, INFRASTRUCTURE_ERROR, "Unclassified failure"


def run_declared_test(
    seed_root: Path | str,
    test_file_path: Path | str,
    *,
    command_builder: Callable[[Path, Path], list[str]] | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> RedExecutionResult:
    """Run declared test against seed root and classify outcome."""
    seed = Path(seed_root).resolve()
    tpath = Path(test_file_path).resolve()
    
    test_data = tpath.read_bytes() if tpath.is_file() else b""
    test_sha = hashlib.sha256(test_data).hexdigest()
    rel_path = tpath.name
    try:
        rel_path = tpath.relative_to(seed).as_posix()
    except Exception:
        pass

    if command_builder:
        argv = command_builder(seed, tpath)
    elif tpath.suffix == ".py":
        argv = ["python", "-m", "pytest", str(tpath), "--override-ini=addopts=", "-q"]
    else:
        # Default java/maven test
        argv = ["mvn", "--offline", "test", f"-Dtest={tpath.stem}"]

    started = time.monotonic_ns()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(seed),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env or os.environ.copy(),
        )
        duration_ms = (time.monotonic_ns() - started) // 1_000_000
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
    except Exception as exc:
        duration_ms = (time.monotonic_ns() - started) // 1_000_000
        stdout = ""
        stderr = str(exc)
        exit_code = 127

    authentic, category, msg = classify_test_output(exit_code, stdout, stderr)
    return RedExecutionResult(
        test_path=rel_path,
        test_name=tpath.stem,
        test_sha256=test_sha,
        exit_code=exit_code,
        authentic_red=authentic,
        failure_category=category,
        failure_message=msg,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
    )
