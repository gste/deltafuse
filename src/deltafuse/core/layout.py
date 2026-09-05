"""Product repository layout and integrity validator for DeltaFuse 2.0."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml


CANONICAL_SKILL_NAMES = [
    "intake",
    "analyze-change",
    "specify-change",
    "decompose-change",
    "target-task",
    "implement-task",
    "verify-change",
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

    if config_file.is_file():
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
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
            lock = yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}
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
        adapter_path = root / rel_adapter
        if not adapter_path.is_dir():
            errors.append(f"Missing configured adapter root: {rel_adapter}")
            continue

        for skill in CANONICAL_SKILL_NAMES:
            skill_dir = adapter_path / skill
            skill_md = skill_dir / "SKILL.md"
            marker = skill_dir / ".deltafuse-generated.yaml"

            if not skill_md.is_file():
                errors.append(f"Missing generated skill: {rel_adapter}/{skill}/SKILL.md")
                continue
            if not marker.is_file():
                errors.append(f"Missing generated metadata: {rel_adapter}/{skill}")
                continue

            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            if "# DO NOT EDIT: generated by DeltaFuse installer." not in content:
                errors.append(f"Generated skill is not marked DO NOT EDIT: {rel_adapter}/{skill}")

            meta_content = marker.read_text(encoding="utf-8", errors="ignore")
            if lock_version and f"generated_by: deltafuse@{lock_version}" not in meta_content:
                errors.append(f"Generated skill version mismatch: {rel_adapter}/{skill}")
            if lock_hash and f"content_hash: {lock_hash}" not in meta_content:
                errors.append(f"Generated skill hash mismatch: {rel_adapter}/{skill}")

    return errors
