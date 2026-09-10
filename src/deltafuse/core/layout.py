"""Product repository layout and integrity validator for DeltaFuse 2.0."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.adapters import validate_adapter_skills
from deltafuse.core.lock import workflow_alignment_errors


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
