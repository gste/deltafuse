"""Single config validator for DeltaFuse product contracts (DF3-009 item 5).

Validates `.deltafuse/config.yaml` as one unit: schema version, lifecycle
baseline, leash mode, integrity profile, runner allowlist and capability
roots. Unknown workflow keys are rejected so typos fail loudly instead of
silently disabling a contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.receipts import PROFILES

KNOWN_TOP_KEYS = {"schema_version", "framework", "paths", "context", "workflow", "project", "adapters"}
KNOWN_WORKFLOW_KEYS = {
    "schema_version",
    "leash",
    "integrity_profile",
    "test_commands",
    "code_roots",
    "call_width",
    "auto_accept_decisions",
}
LEASH_MODES = {"off", "advisory", "enforce"}
BASELINES = {"draft", "accepted"}
KNOWN_PROJECT_KEYS = {"baseline", "capability_catalog"}


class ConfigError(Exception):
    """Invalid or unknown product config content."""


def validate_config(product_root: Path | str) -> list[str]:
    """Return a list of config problems; empty means valid."""
    root = Path(product_root)
    path = root / ".deltafuse" / "config.yaml"
    if not path.is_file():
        return ["config.yaml is missing in .deltafuse/"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as ex:
        return [f"config.yaml is not valid YAML: {ex}"]
    if not isinstance(data, dict):
        return ["config.yaml must be a mapping"]
    errors: list[str] = []

    version = data.get("schema_version")
    if version != 3:
        errors.append(
            f"config.yaml: schema_version {version!r} is not supported (v3); "
            "migrate manually — no automatic conversion"
        )
    unknown_top = set(data) - KNOWN_TOP_KEYS
    if unknown_top:
        errors.append(f"config.yaml: unknown top-level keys {sorted(unknown_top)}")

    project = data.get("project")
    if project is not None:
        if not isinstance(project, dict):
            errors.append("config.yaml: project must be a mapping")
        else:
            baseline = project.get("baseline")
            if baseline is not None and baseline not in BASELINES:
                errors.append(
                    f"config.yaml: project.baseline {baseline!r} must be one of {sorted(BASELINES)}"
                )
            unknown_project = set(project) - KNOWN_PROJECT_KEYS
            if unknown_project:
                errors.append(f"config.yaml: unknown project keys {sorted(unknown_project)}")

    workflow = data.get("workflow")
    if workflow is not None:
        if not isinstance(workflow, dict):
            errors.append("config.yaml: workflow must be a mapping")
        else:
            unknown = set(workflow) - KNOWN_WORKFLOW_KEYS
            if unknown:
                errors.append(f"config.yaml: unknown workflow keys {sorted(unknown)}")
            mode = workflow.get("leash")
            if mode is not None and mode not in LEASH_MODES:
                errors.append(
                    f"config.yaml: workflow.leash {mode!r} must be one of {sorted(LEASH_MODES)}"
                )
            profile = workflow.get("integrity_profile")
            if profile is not None and profile not in PROFILES:
                errors.append(
                    f"config.yaml: workflow.integrity_profile {profile!r} must be one of {sorted(PROFILES)}"
                )
            commands = workflow.get("test_commands")
            if commands is not None:
                if not isinstance(commands, list) or not all(
                    isinstance(c, str) and c.strip() for c in commands
                ):
                    errors.append("config.yaml: workflow.test_commands must be a list of non-empty strings")
            code_roots = workflow.get("code_roots")
            if code_roots is not None:
                if not isinstance(code_roots, list) or not all(
                    isinstance(r, str) and ("*" in r or r.endswith("/") or "/" in r)
                    for r in code_roots
                ):
                    errors.append(
                        "config.yaml: workflow.code_roots must be a list of glob paths like 'src/**'"
                    )
    return errors
