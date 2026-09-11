"""Lock and workflow profile helpers for DeltaFuse product pins."""

from __future__ import annotations
from typing import Any

CALL_WIDTHS = frozenset({"narrow", "medium", "wide"})
DEFAULT_CALL_WIDTH = "wide"
LEASH_MODES = frozenset({"off", "advisory", "enforce"})


def normalize_call_width(value: Any) -> str | None:
    """Return a valid call_width or None if missing/invalid."""
    if value is None:
        return None
    width = str(value).strip().lower()
    if width in CALL_WIDTHS:
        return width
    return None


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


def workflow_from_mapping(data: dict[str, Any] | None) -> tuple[str, bool, list[str]]:
    """Resolve (call_width, auto_accept_decisions, errors) from config or lock YAML."""
    errors: list[str] = []
    if not data:
        return DEFAULT_CALL_WIDTH, False, errors
    workflow = data.get("workflow")
    if workflow is None:
        return DEFAULT_CALL_WIDTH, False, errors
    if not isinstance(workflow, dict):
        return DEFAULT_CALL_WIDTH, False, ["workflow must be a mapping"]

    raw_width = workflow.get("call_width")
    if raw_width is None:
        width = DEFAULT_CALL_WIDTH
    else:
        width = normalize_call_width(raw_width)
        if width is None:
            errors.append(
                f"call_width must be one of {', '.join(sorted(CALL_WIDTHS))}; got {raw_width!r}"
            )
            width = DEFAULT_CALL_WIDTH

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

    return width, auto, errors


def format_lock_yaml(
    *,
    version: str,
    source: str,
    content_hash: str,
    call_width: str = DEFAULT_CALL_WIDTH,
    auto_accept_decisions: bool = False,
) -> str:
    """Canonical lock.yaml text written by the installer."""
    width = normalize_call_width(call_width) or DEFAULT_CALL_WIDTH
    auto = "true" if auto_accept_decisions else "false"
    hash_value = content_hash if content_hash.startswith("sha256:") else f"sha256:{content_hash}"
    return (
        f"schema_version: 2\n"
        f"framework:\n"
        f"  version: {version}\n"
        f"  source: {source}\n"
        f"  content_hash: {hash_value}\n"
        f"workflow:\n"
        f"  call_width: {width}\n"
        f"  auto_accept_decisions: {auto}\n"
    )


def workflow_alignment_errors(config: dict[str, Any] | None, lock: dict[str, Any] | None) -> list[str]:
    """Layout errors for invalid or mismatched workflow profiles."""
    errors: list[str] = []
    config = config if isinstance(config, dict) else {}
    lock = lock if isinstance(lock, dict) else {}

    cfg_width, cfg_auto, cfg_errors = workflow_from_mapping(config)
    if lock.get("workflow") is not None and not isinstance(lock.get("workflow"), dict):
        errors.append("Lock file workflow must be a mapping")
        return errors

    lock_width, lock_auto, lock_errors = workflow_from_mapping(lock)
    for message in cfg_errors:
        errors.append(f"Config file {message}")
    for message in lock_errors:
        errors.append(f"Lock file {message}")

    config_declared = isinstance(config.get("workflow"), dict) and (
        "call_width" in config["workflow"] or "auto_accept_decisions" in config["workflow"]
    )
    lock_declared = isinstance(lock.get("workflow"), dict)

    if config_declared and lock_declared:
        if "call_width" in config["workflow"] and "call_width" in lock["workflow"]:
            if cfg_width != lock_width and not cfg_errors and not lock_errors:
                errors.append(
                    f"Requested call_width {cfg_width} does not match locked call_width {lock_width}"
                )
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
