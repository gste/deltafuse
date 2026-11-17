"""Product repository layout and integrity validator for DeltaFuse 2.0."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.adapters import validate_adapter_skills
from deltafuse.core.lock import lock_schema_version_errors, workflow_alignment_errors


CANONICAL_SKILL_NAMES = [
    "run",
    "intake",
    "analyze",
    "specify",
    "decompose",
    "declare",
    "implement",
    "verify",
]

LEGACY_FORBIDDEN_PATHS = ["docs/process", "docs/init", "docs/todo"]


class PathRefused(ValueError):
    """A path that does not name a place inside the product."""


_DRIVE = re.compile(r"^[A-Za-z]:")


def product_relpath(raw: Any, product_root: Path | str | None = None, *, resolve: bool = False) -> str:
    """The one normal form of a product path: relative to the product root, POSIX slashes, no
    empty, `.` or `..` segment, no drive.

    Audit 2026-11-17 (FW-1, FW-8): `deltafuse leash --file`, a task's `allowed_paths` and the
    Writer each read a path their own way. An absolute path or one with `..` matched no glob in
    the leash (so it was "not product code") and matched `src/**` at the decomposed gate (so
    `src/../.deltafuse/gate-password.yaml` was a path the task may write).

    Strict (the default; what a stored path must already be): an absolute path, a `..` segment or a
    path that is not written in its normal form is refused. ``resolve`` (what a human or a tool
    types: `leash --file`): `.`, `//` and `..` are resolved, an absolute path inside
    ``product_root`` is made relative, and a path that leaves the product is refused.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise PathRefused(f"{raw!r} is not a path")
    text = raw.strip().replace("\\", "/")
    absolute = text.startswith("/") or _DRIVE.match(text) is not None
    if absolute:
        if not resolve or product_root is None:
            raise PathRefused(f"'{raw}' is an absolute path; name it relative to the product root")
        root = Path(product_root).resolve()
        try:
            text = Path(text).resolve().relative_to(root).as_posix()
        except ValueError:
            raise PathRefused(f"'{raw}' is outside the product ({root})") from None
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            if not resolve:
                raise PathRefused(f"'{raw}' is not in normal form (an empty or '.' segment)")
            continue
        if part == "..":
            if not resolve:
                raise PathRefused(f"'{raw}' holds '..'; name the path itself, relative to the product root")
            if not parts:
                raise PathRefused(f"'{raw}' is outside the product")
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise PathRefused(f"'{raw}' names the product root, not a path in it")
    rel = "/".join(parts)
    if _DRIVE.match(rel):
        raise PathRefused(f"'{raw}' names a drive")
    if resolve and product_root is not None:
        # The name as the file system has it (a case-insensitive disk takes `SRC/app.py`); a link
        # that leads out of the product is outside it.
        root = Path(product_root).resolve()
        if (root / rel).exists():
            try:
                rel = (root / rel).resolve().relative_to(root).as_posix()
            except ValueError:
                raise PathRefused(f"'{raw}' is outside the product ({root})") from None
    return rel


def product_path_error(raw: Any) -> str | None:
    """Why a stored path (a task's `allowed_paths`, a Writer target) is not a product path, or None."""
    try:
        normal = product_relpath(raw)
    except PathRefused as ex:
        return str(ex)
    if normal != raw:
        return f"'{raw}' is not in normal form; write it as '{normal}'"
    return None


def validate_product_layout(product_dir: Path | str) -> list[str]:
    """
    Validates a product repository layout against DeltaFuse 2.0 layout standards.
    Replaces and expands upon tests/validate-layout.ps1 / .sh.
    """
    root = Path(product_dir).resolve()
    errors: list[str] = []

    if not root.is_dir():
        return [f"Product root directory not found: {root}"]

    # 1. Config & Lock files
    config_file = root / ".deltafuse" / "config.yaml"
    lock_file = root / ".deltafuse" / "lock.yaml"

    if not config_file.is_file():
        errors.append("Missing required path: .deltafuse/config.yaml")
    if not lock_file.is_file():
        errors.append("Missing required path: .deltafuse/lock.yaml")

    config_version: str | None = None
    config_source: str | None = None
    adapter_roots: list[str] = []
    cfg: dict[str, Any] = {}
    lock: dict[str, Any] = {}

    if config_file.is_file():
        try:
            loaded_cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            if isinstance(loaded_cfg, dict):
                cfg = loaded_cfg
            config_version = cfg.get("framework", {}).get("version")
            config_source = cfg.get("framework", {}).get("source")
            adapters_sec = cfg.get("adapters", {})
            if isinstance(adapters_sec, dict) and "roots" in adapters_sec:
                adapter_roots = adapters_sec["roots"]
            if not config_version:
                errors.append("Config file has no requested framework version")
            if not config_source:
                errors.append("Config file has no requested framework source")
        except Exception as ex:
            errors.append(f"Error parsing .deltafuse/config.yaml: {ex}")

    if not adapter_roots:
        adapter_roots = [".agents/skills", ".cursor/skills", ".gemini/skills"]

    lock_version: str | None = None
    lock_source: str | None = None
    lock_hash: str | None = None

    if lock_file.is_file():
        try:
            loaded_lock = yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}
            if isinstance(loaded_lock, dict):
                lock = loaded_lock
            lock_version = lock.get("framework", {}).get("version") or lock.get("version")
            lock_source = lock.get("framework", {}).get("source") or lock.get("source")
            lock_hash = lock.get("framework", {}).get("content_hash")
            if not lock_version:
                errors.append("Lock file has no framework version")
            if not lock_source:
                errors.append("Lock file has no framework source")
            if not lock_hash or not re.match(r"^sha256:[a-fA-F0-9]{64}$", str(lock_hash)):
                errors.append("Lock file has no valid framework content hash")
        except Exception as ex:
            errors.append(f"Error parsing .deltafuse/lock.yaml: {ex}")

    errors.extend(lock_schema_version_errors(lock))

    # V3-FIX-014: validate the full lock pin against the canonical lock contract
    # when the schema registry can resolve it; the fail-closed version check above
    # always applies.
    try:
        from deltafuse.core.schemas import SchemaRegistry

        lock_schema_errors = SchemaRegistry().validate("lock", lock)
    except Exception:  # noqa: BLE001 — registry unavailable or schema missing
        lock_schema_errors = []
    errors.extend(lock_schema_errors)

    errors.extend(workflow_alignment_errors(cfg, lock))

    # Version / source alignment
    if config_version and lock_version and config_version != lock_version:
        errors.append(f"Requested framework version {config_version} does not match locked version {lock_version}")

    if config_source and lock_source:
        norm_source = f"deltafuse://v{config_version}" if config_source == "deltafuse" else config_source
        if norm_source != lock_source:
            errors.append(f"Requested framework source '{config_source}' does not match locked source '{lock_source}'")

    # 2. Required directories
    required_dirs = [
        "docs/intake",
        "docs/changes",
        "docs/spec",
        "docs/decisions",
        "docs/archive/intake",
        "docs/archive/changes",
    ]
    for rd in required_dirs:
        if not (root / rd).is_dir():
            errors.append(f"Missing required path: {rd}")

    # 3. Forbidden legacy paths
    for forbidden in LEGACY_FORBIDDEN_PATHS:
        if (root / forbidden).exists():
            errors.append(f"Legacy product path must be migrated: {forbidden}")

    # FW-13 / FW-2: how the product sits in git. A missing hook is a warning, not an error - a CI
    # checkout never has one.
    import os
    import sys

    from deltafuse.core.leash import hook_warning, repository_layout_error

    layout_error = repository_layout_error(root)
    if layout_error is not None:
        errors.append(layout_error)
    elif config_file.is_file() and not os.environ.get("CI"):
        warning = hook_warning(root)
        if warning is not None:
            print(f"deltafuse: warning: {warning}", file=sys.stderr)

    # 4. Validate generated skills for each configured adapter root
    for rel_adapter in adapter_roots:
        errors.extend(
            validate_adapter_skills(
                root,
                rel_adapter,
                CANONICAL_SKILL_NAMES,
                lock_version=lock_version,
                lock_hash=lock_hash,
                lock_source=lock_source,
            )
        )

    return errors
