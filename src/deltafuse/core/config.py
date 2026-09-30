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

from deltafuse.core.gate_receipts import PROFILES, REMOVED_PROFILES

KNOWN_TOP_KEYS = {"schema_version", "framework", "paths", "context", "workflow", "project", "adapters"}
KNOWN_WORKFLOW_KEYS = {
    "schema_version",
    "leash",
    "integrity_profile",
    "test_commands",
    "code_roots",
    "call_width",
    "auto_accept_decisions",
    "trace_claims",
}
LEASH_MODES = {"off", "advisory", "enforce"}
# P12 (experiment): `warn` has `converged` name Expectation/Constraint claims coverage.yaml
# has no test for, as an advisory line - never a gate error. `off` (default) costs nothing:
# no extra read, no extra line. There is no `enforce` yet - a marker present but the test
# unrelated is not detectable by the Core; that stays the judge's job until layer 2 has run
# on enough models to show a low false-positive rate.
TRACE_CLAIMS_MODES = {"off", "warn"}
BASELINES = {"draft", "accepted"}
KNOWN_PROJECT_KEYS = {"baseline", "capability_catalog"}


class ConfigError(Exception):
    """Invalid or unknown product config content."""


def validate_active_code_roots(product_root: Path | str) -> list[str]:
    """Rule (a): `code_roots` of `active` capabilities do not overlap.

    The under-routing detector (q4) maps a diff to capabilities through their
    roots; when two active capabilities share one it cannot tell whose the change
    is (bench case M02: three capabilities, one `src/ratelimit`). Compared as
    directory prefixes, the way ownership reads them (`dir/*`, the files lying directly
    in `dir`, meets only the same `dir/*` and a tree root that is `dir` or above it). Draft, deprecated and
    removed capabilities are exempt, so a partial adoption is not blocked.
    """
    from deltafuse.core.integrity import load_capability_catalog
    from deltafuse.core.ownership import _root_prefix, roots_overlap

    catalog, load_errors = load_capability_catalog(Path(product_root))
    if load_errors or not isinstance(catalog, dict):
        return []  # a missing or unreadable catalog is reported by the checks that own it
    claims: list[tuple[str, str]] = []
    domains = catalog.get("domains") or {}
    for domain, dobj in sorted(domains.items()) if isinstance(domains, dict) else []:
        caps = dobj.get("capabilities") if isinstance(dobj, dict) else None
        for name, cap in sorted(caps.items()) if isinstance(caps, dict) else []:
            if not isinstance(cap, dict) or str(cap.get("status") or "active").lower() != "active":
                continue
            for raw in cap.get("code_roots") or []:
                prefix = _root_prefix(raw) if isinstance(raw, str) else ""
                if prefix:
                    claims.append((f"{domain}.{name}", prefix))
    errors: list[str] = []
    for i, (cap_a, root_a) in enumerate(claims):
        for cap_b, root_b in claims[i + 1:]:
            if cap_a != cap_b and roots_overlap(root_a, root_b):
                errors.append(
                    f"catalog: active capabilities '{cap_a}' and '{cap_b}' overlap in code_roots "
                    f"('{root_a}' and '{root_b}'): a change cannot be routed back to one owner; "
                    "make the roots disjoint or mark one of them draft"
                )
    return errors


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
            trace_mode = workflow.get("trace_claims")
            # Unquoted YAML 1.1 `off` loads as boolean False, same as workflow.leash.
            if trace_mode is False:
                trace_mode = "off"
            if trace_mode is not None and trace_mode not in TRACE_CLAIMS_MODES:
                errors.append(
                    f"config.yaml: workflow.trace_claims {trace_mode!r} must be one of "
                    f"{sorted(TRACE_CLAIMS_MODES)}"
                )
            profile = workflow.get("integrity_profile")
            if profile in REMOVED_PROFILES:
                errors.append(f"config.yaml: {REMOVED_PROFILES[profile]}")
            elif profile is not None and profile not in PROFILES:
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
    errors.extend(validate_active_code_roots(root))
    return errors


def load_trace_claims_mode(product_root: Path | str, *, missing: str = "off") -> str:
    """`workflow.trace_claims`: off (default) or warn. See TRACE_CLAIMS_MODES."""
    path = Path(product_root) / ".deltafuse" / "config.yaml"
    if not path.is_file():
        return missing
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return missing
    if not isinstance(data, dict):
        return missing
    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        return missing
    mode = workflow.get("trace_claims")
    return mode if mode in TRACE_CLAIMS_MODES else missing
