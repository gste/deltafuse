"""Run a product command and write Change evidence YAML (kernel, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
from typing import Any

import yaml

from deltafuse.core.context import load_change_route
from deltafuse.core.fsm import find_repo_root
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.integrity import scan_changed_paths_for_private_test_access

AUTHENTIC_RED_CATEGORY = "behavioral-mismatch"
_SYNTAX_MARKERS = ("SyntaxError", "IndentationError", "TabError")
_IMPORT_MARKERS = ("ImportError", "ModuleNotFoundError")


class EvidenceRunError(Exception):
    """Usage or package error before a command is classified."""


@dataclass
class EvidenceOutcome:
    payload: dict[str, Any]
    dest: Path
    authentic: bool
    errors: list[str] = field(default_factory=list)
    command_exit_code: int = 0


def classify_failure(log: str, exit_code: int) -> str | None:
    """Map command output to evidence failure_category. None if the command passed."""
    if exit_code == 0:
        return None
    if any(marker in log for marker in _SYNTAX_MARKERS):
        return "syntax-error"
    if any(marker in log for marker in _IMPORT_MARKERS):
        return "import-error"
    if "AssertionError" in log or "assert " in log or "Failed:" in log:
        return AUTHENTIC_RED_CATEGORY
    return "fixture-error"


def _posix_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        rel = raw.replace("\\", "/").lstrip("/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def _load_change_id(change_path: Path) -> str:
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        raise EvidenceRunError(f"Missing required change.yaml in {change_path}")
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
    except Exception as ex:
        raise EvidenceRunError(f"Failed to parse change.yaml: {ex}") from ex
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise EvidenceRunError("change.yaml must contain string id")
    return data["id"]


def _sanitize_command(argv: list[str]) -> str:
    try:
        return shlex.join(argv)
    except Exception:
        return " ".join(argv)


def _is_authentic(
    *,
    phase: str,
    result: str,
    failure_category: str | None,
    route: str,
    private_errors: list[str],
) -> bool:
    if phase == "red":
        if route == "code" and private_errors:
            return False
        if result == "already-green":
            return True
        if result != "expected-failure":
            return False
        if route == "code":
            return failure_category == AUTHENTIC_RED_CATEGORY
        return True
    if phase in {"green", "regression"}:
        return result == "passed"
    return False


def run_evidence(
    change_dir: Path | str,
    *,
    phase: str,
    task: str,
    argv: list[str],
    changed_paths: list[str] | None = None,
    timeout: int = 90,
) -> EvidenceOutcome:
    """Execute *argv* at the product root and write evidence/<phase>/<task>.yaml."""
    if phase not in {"red", "green", "regression"}:
        raise EvidenceRunError(f"Unsupported evidence phase '{phase}'")
    if not argv:
        raise EvidenceRunError("Command argv is required after '--'")
    change_path = Path(change_dir).resolve()
    if not change_path.is_dir():
        raise EvidenceRunError(f"Change package directory not found: {change_path}")

    repo_root = find_repo_root(change_path)
    change_id = _load_change_id(change_path)
    route, route_errs = load_change_route(change_path)
    rel_paths = _posix_paths(changed_paths or [])

    def _as_text(raw: object) -> str:
        if raw is None:
            return ""
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    timed_out = False
    try:
        proc = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code = int(proc.returncode)
        log = (_as_text(proc.stdout) + _as_text(proc.stderr)).strip()
    except FileNotFoundError as ex:
        exit_code = 127
        log = str(ex)
    except subprocess.TimeoutExpired as ex:
        exit_code = 124
        log = (_as_text(ex.stdout) + _as_text(ex.stderr)).strip()
        if not log:
            log = f"command timed out after {timeout}s"
        timed_out = True

    category = classify_failure(log, exit_code)
    summary = (log[-800:] if log else ("timed out" if timed_out else "no output"))
    private_errors: list[str] = []
    if phase == "red" and route == "code":
        private_errors = scan_changed_paths_for_private_test_access(repo_root, rel_paths)

    if timed_out:
        result = "blocked"
    elif phase == "red":
        result = "already-green" if exit_code == 0 else "expected-failure"
    else:
        result = "passed" if exit_code == 0 else "failed"

    payload: dict[str, Any] = {
        "schema_version": 2,
        "change": change_id,
        "task": task,
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": _sanitize_command(argv),
        "exit_code": exit_code,
        "result": result,
        "failure_category": category,
        "summary": summary,
        "changed_paths": rel_paths,
        "spec_status": "unchanged",
    }
    if phase in {"green", "regression"}:
        payload["base_revision"] = compute_product_baseline_revision(repo_root)

    dest = change_path / "evidence" / phase / f"{task}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    errors = list(route_errs)
    errors.extend(private_errors)
    if (
        phase == "red"
        and route == "code"
        and result == "expected-failure"
        and category != AUTHENTIC_RED_CATEGORY
    ):
        errors.append(
            f"Red failure_category is '{category}', not '{AUTHENTIC_RED_CATEGORY}'"
        )
    if phase in {"green", "regression"} and result != "passed":
        errors.append(f"{phase} command exited {exit_code}, expected 0")
    if timed_out:
        errors.append(f"command timed out after {timeout}s")

    authentic = _is_authentic(
        phase=phase,
        result=result,
        failure_category=category,
        route=route,
        private_errors=private_errors,
    )
    if not authentic and not errors:
        errors.append(f"{phase} evidence is not authentic (result '{result}')")

    return EvidenceOutcome(
        payload=payload,
        dest=dest,
        authentic=authentic,
        errors=errors,
        command_exit_code=exit_code,
    )
