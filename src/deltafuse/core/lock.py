"""Lock and workflow profile helpers for DeltaFuse product pins."""

from __future__ import annotations
from typing import Any

# `workflow.call_width` (narrow/medium/wide) was retired: nothing but the board snapshot
# ever read it (audit F14). A config or lock that still carries it is accepted and ignored.
LEASH_MODES = frozenset({"off", "advisory", "enforce"})
LOCK_SCHEMA_VERSION = 3


def lock_schema_version_errors(lock: dict[str, Any] | None) -> list[str]:
    """Fail-closed check that the lock pin uses a supported lock contract."""
    data = lock if isinstance(lock, dict) else {}
    version = data.get("schema_version")
    if version == LOCK_SCHEMA_VERSION:
        return []
    return [
        f"Unsupported lock schema_version {version!r}; this Core supports lock "
        f"schema_version {LOCK_SCHEMA_VERSION} only — re-run the installer"
    ]


def normalize_leash_mode(value: Any) -> str | None:
    """Return a valid leash mode or None if missing/invalid.

    Unquoted YAML 1.1 `off` loads as boolean False; treat that as `off`.
    """
    if value is None or value == "":
        return None
    if value is False:
        return "off"
    if isinstance(value, bool):
        return None
    mode = str(value).strip().lower()
    if mode in LEASH_MODES:
        return mode
    return None


def workflow_from_mapping(data: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Resolve (auto_accept_decisions, errors) from config or lock YAML."""
    errors: list[str] = []
    if not data:
        return False, errors
    workflow = data.get("workflow")
    if workflow is None:
        return False, errors
    if not isinstance(workflow, dict):
        return False, ["workflow must be a mapping"]

    raw_auto = workflow.get("auto_accept_decisions")
    auto = False
    if raw_auto is None:
        auto = False
    elif isinstance(raw_auto, bool):
        auto = raw_auto
    else:
        errors.append("auto_accept_decisions must be a boolean")

    raw_leash = workflow.get("leash")
    if raw_leash is not None and normalize_leash_mode(raw_leash) is None:
        errors.append(
            f"leash must be one of {', '.join(sorted(LEASH_MODES))}; got {raw_leash!r}"
        )

    return auto, errors


def format_lock_yaml(
    *,
    version: str,
    source: str,
    content_hash: str,
    auto_accept_decisions: bool = False,
) -> str:
    """Canonical lock.yaml text written by the installer."""
    auto = "true" if auto_accept_decisions else "false"
    hash_value = content_hash if content_hash.startswith("sha256:") else f"sha256:{content_hash}"
    return (
        f"schema_version: {LOCK_SCHEMA_VERSION}\n"
        f"framework:\n"
        f"  version: {version}\n"
        f"  source: {source}\n"
        f"  content_hash: {hash_value}\n"
        f"workflow:\n"
        f"  auto_accept_decisions: {auto}\n"
    )


def workflow_alignment_errors(config: dict[str, Any] | None, lock: dict[str, Any] | None) -> list[str]:
    """Layout errors for invalid or mismatched workflow profiles."""
    errors: list[str] = []
    config = config if isinstance(config, dict) else {}
    lock = lock if isinstance(lock, dict) else {}

    cfg_auto, cfg_errors = workflow_from_mapping(config)
    if lock.get("workflow") is not None and not isinstance(lock.get("workflow"), dict):
        errors.append("Lock file workflow must be a mapping")
        return errors

    lock_auto, lock_errors = workflow_from_mapping(lock)
    for message in cfg_errors:
        errors.append(f"Config file {message}")
    for message in lock_errors:
        errors.append(f"Lock file {message}")

    config_declared = isinstance(config.get("workflow"), dict) and (
        "auto_accept_decisions" in config["workflow"]
    )
    lock_declared = isinstance(lock.get("workflow"), dict)

    if config_declared and lock_declared:
        if (
            "auto_accept_decisions" in config["workflow"]
            and "auto_accept_decisions" in lock["workflow"]
            and isinstance(config["workflow"].get("auto_accept_decisions"), bool)
            and isinstance(lock["workflow"].get("auto_accept_decisions"), bool)
            and cfg_auto != lock_auto
        ):
            errors.append(
                "Requested auto_accept_decisions does not match locked auto_accept_decisions"
            )

    return errors
