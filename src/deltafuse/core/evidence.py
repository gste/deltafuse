"""Run a product command and write Change evidence YAML (kernel, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shlex
import subprocess
from typing import Any

import yaml

from deltafuse.core.context import load_change_route, posix_relpath
from deltafuse.core.fsm import find_repo_root
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.integrity import scan_changed_paths_for_private_test_access
from deltafuse.core.runners import runner_is_authorized
from deltafuse.core.leash import git_dirty_paths, is_exempt_path, LeashError

AUTHENTIC_RED_CATEGORY = "behavioral-mismatch"
RECORDED_BY = "deltafuse-evidence"
STAMP_KEYS = frozenset({"recorded_by", "recorded_sha256"})
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
    if phase in {"green", "regression", "verification"}:
        return result == "passed"
    return False


def _lock_pin(product_root: Path) -> str:
    lock = Path(product_root) / ".deltafuse" / "lock.yaml"
    if not lock.is_file():
        return ""
    try:
        data = yaml.safe_load(lock.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    framework = data.get("framework")
    if not isinstance(framework, dict):
        return ""
    pin = framework.get("content_hash")
    return pin if isinstance(pin, str) else ""


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    return value


def stamp_digest(payload: dict[str, Any], product_root: Path) -> str:
    body = {key: payload[key] for key in payload if key not in STAMP_KEYS}
    material = {"pin": _lock_pin(product_root), "evidence": _jsonable(body)}
    raw = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def stamp_evidence(payload: dict[str, Any], product_root: Path) -> dict[str, Any]:
    """Return a copy of *payload* with the kernel evidence stamp."""
    out = {key: value for key, value in payload.items() if key not in STAMP_KEYS}
    out["recorded_by"] = RECORDED_BY
    out["recorded_sha256"] = stamp_digest(out, product_root)
    return out


def evidence_stamp_error(payload: dict[str, Any], product_root: Path) -> str | None:
    """None when the kernel stamp matches the payload."""
    if not isinstance(payload, dict):
        return "evidence is not a mapping"
    if payload.get("recorded_by") != RECORDED_BY:
        return "evidence is not stamped by deltafuse evidence"
    want = stamp_digest(payload, product_root)
    if payload.get("recorded_sha256") != want:
        return "evidence stamp does not match the recorded payload"
    return None


def write_stamped_evidence(
    path: Path,
    payload: dict[str, Any],
    product_root: Path,
    lock_timeout: float = 5.0,
) -> dict[str, Any]:
    """Stamp *payload* and write YAML under ProductMutationLock using atomic storage."""
    from deltafuse.core.artifact_registry import ArtifactRegistry
    from deltafuse.core.artifact_lock import ProductMutationLock
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace

    registry = ArtifactRegistry()
    val_res = registry.validate_storage_schema("evidence", payload)
    if not val_res.valid:
        diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
        raise EvidenceRunError(f"Evidence storage schema validation failed: {'; '.join(diag_msgs)}")

    stamped = stamp_evidence(payload, product_root)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    yaml_bytes = yaml.safe_dump(stamped, sort_keys=False, allow_unicode=True).encode("utf-8")

    with ProductMutationLock(product_root, timeout=lock_timeout):
        if dest.is_file():
            atomic_replace(dest, yaml_bytes)
        else:
            atomic_create(dest, yaml_bytes)

    return stamped



_GENERATED_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def _core_computed_changed_paths(repo_root: Path) -> list[str]:
    """Core-derived dirty paths the Worker is accountable for.

    Worker lists are an expected subset of this set, so it must hold only the
    Worker's own changes. q0 run 20260921T081038Z: the raw git diff also held
    the Core's journals (`.deltafuse/**`), interpreter caches (`__pycache__`)
    and the evidence file this very command had just written, and the Worker
    was told to list them - the same class of defect the leash had.
    """
    try:
        paths = git_dirty_paths(repo_root)
    except LeashError:
        # No git repository (bench sandbox, fresh install): nothing to derive.
        return []
    out: list[str] = []
    for raw in paths:
        rel = posix_relpath(raw)
        parts = rel.split("/")
        if is_exempt_path(rel):
            continue  # .deltafuse/** and the other leash exemptions
        if _GENERATED_DIRS.intersection(parts) or rel.endswith(".pyc"):
            continue
        if len(parts) > 3 and parts[:2] == ["docs", "changes"] and parts[3] == "evidence":
            continue  # written by `deltafuse evidence` itself
        out.append(raw)
    return out

def run_evidence(
    change_dir: Path | str,
    *,
    phase: str,
    task: str | None = None,
    argv: list[str],
    changed_paths: list[str] | None = None,
    timeout: int = 90,
) -> EvidenceOutcome:
    """Execute *argv* at the product root and write evidence/<phase>/<task|run>.yaml."""
    if phase not in {"red", "green", "regression", "verification"}:
        raise EvidenceRunError(f"Unsupported evidence phase '{phase}'")
    if not argv:
        raise EvidenceRunError("Command argv is required after '--'")

    if phase == "verification":
        if task is not None and task != "null" and task != "":
            raise EvidenceRunError(f"Verification phase requires task=None, got '{task}'")
        task = None
    else:
        if not task:
            raise EvidenceRunError(f"Evidence phase '{phase}' requires task ID (e.g. TASK-001)")

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
        "schema_version": 3,
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
    if phase in {"green", "regression", "verification"}:
        payload["base_revision"] = compute_product_baseline_revision(repo_root)

    if phase == "verification":
        dest = change_path / "evidence" / "verification" / "run.yaml"
    else:
        dest = change_path / "evidence" / phase / f"{task}.yaml"

    payload = write_stamped_evidence(dest, payload, repo_root)

    errors = list(route_errs)
    runner_ok = runner_is_authorized(argv, route=route, product_root=repo_root)
    if not runner_ok:
        errors.append(
            f"evidence: command {argv[:3]} is not an authorized runner for route '{route}'; "
            "configure workflow.test_commands in .deltafuse/config.yaml (DF3-006/B-04)"
        )
    computed = _core_computed_changed_paths(repo_root)
    if computed:
        worker_paths = set(rel_paths)
        missing = sorted(p for p in computed if p not in worker_paths)
        if missing:
            errors.append(
                "evidence: changed_paths must include the Core-computed dirty set; "
                f"missing {missing}"
            )
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
    if runner_ok is False:
        authentic = False
    if not authentic and not errors:
        errors.append(f"{phase} evidence is not authentic (result '{result}')")

    return EvidenceOutcome(
        payload=payload,
        dest=dest,
        authentic=authentic,
        errors=errors,
        command_exit_code=exit_code,
    )
