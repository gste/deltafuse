"""Single config validator for DeltaFuse product contracts (DF3-009 item 5).

Validates `.deltafuse/config.yaml` as one unit: schema version, lifecycle
baseline, leash mode, integrity profile, runner allowlist and capability
roots. Unknown workflow keys are rejected so typos fail loudly instead of
silently disabling a contract.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
from pathlib import Path
from typing import Any, Iterator

import yaml

from deltafuse.core.gate_receipts import PROFILES, REMOVED_PROFILES

KNOWN_TOP_KEYS = {"schema_version", "framework", "paths", "context", "workflow", "project", "adapters"}
# Where the Core reads and writes the product's documents. Fixed in this version: the Core names
# these directories itself (`docs/changes` alone ~100 times), so another value would leave a
# product half-read - the queue followed `paths.changes`, the leash and the gates did not
# (codebase audit 2026-10-21, owner decision: refuse rather than half-support).
FIXED_PATHS = {
    "intake": "docs/intake",
    "changes": "docs/changes",
    "specification": "docs/spec",
    "decisions": "docs/decisions",
    "archive": "docs/archive",
}
KNOWN_WORKFLOW_KEYS = {
    "schema_version",
    "leash",
    "integrity_profile",
    "test_commands",
    "code_roots",
    "call_width",
    "auto_accept_decisions",
    "trace_claims",
    "evidence_timeout",
}
DEFAULT_EVIDENCE_TIMEOUT = 90
LEASH_MODES = {"off", "advisory", "enforce"}
# P12 (experiment): `warn` has `converged` name Expectation/Constraint claims coverage.yaml
# has no test for, as an advisory line - never a gate error. `off` (default) costs nothing:
# no extra read, no extra line. There is no `enforce` yet - a marker present but the test
# unrelated is not detectable by the Core; that stays the judge's job until layer 2 has run
# on enough models to show a low false-positive rate.
TRACE_CLAIMS_MODES = {"off", "warn"}
BASELINES = {"draft", "accepted"}
KNOWN_PROJECT_KEYS = {"baseline", "capability_catalog"}


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

    paths = data.get("paths")
    if paths is not None:
        if not isinstance(paths, dict):
            errors.append("config.yaml: paths must be a mapping")
        else:
            for key, value in sorted(paths.items()):
                fixed = FIXED_PATHS.get(key)
                if fixed is None:
                    errors.append(f"config.yaml: unknown paths key {key!r}; known: {sorted(FIXED_PATHS)}")
                elif str(value).strip("/").replace("\\", "/") != fixed:
                    errors.append(
                        f"config.yaml: paths.{key} is {value!r}, but this version of the Core reads and "
                        f"writes {fixed!r} only; set it to {fixed!r} or remove it"
                    )

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
            timeout = workflow.get("evidence_timeout")
            if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
                errors.append(
                    f"config.yaml: workflow.evidence_timeout {timeout!r} must be a positive number of seconds"
                )
            commands = workflow.get("test_commands")
            if commands is not None:
                if not isinstance(commands, list) or not all(
                    isinstance(c, str) and c.strip() for c in commands
                ):
                    errors.append("config.yaml: workflow.test_commands must be a list of non-empty strings")
            code_roots = workflow.get("code_roots")
            if code_roots is not None:
                # A file at the product root is a code root too (`pom.xml`): the leash judges every
                # path (audit 2026-11-17, R5), and this is how a Change comes to write one.
                from deltafuse.core.layout import product_path_error

                def is_root(r: Any) -> bool:
                    if not isinstance(r, str) or product_path_error(r.rstrip("/")) is not None:
                        return False
                    if "*" in r or "/" in r:
                        return True
                    # A bare name is one file (`pom.xml`); a bare directory (`src`) matches nothing.
                    return (root / r).is_file() or ("." in r and not (root / r).is_dir())

                if not isinstance(code_roots, list) or not all(is_root(r) for r in code_roots):
                    errors.append(
                        "config.yaml: workflow.code_roots must be a list of globs like 'src/**' or "
                        "files like 'pom.xml' (relative to the product root, no '..')"
                    )
    errors.extend(_catalog_schema_errors(root))
    errors.extend(validate_active_code_roots(root))
    return errors


def _catalog_schema_errors(product_root: Path) -> list[str]:
    """The capability catalog against its schema, when there is one (a product has none before
    Analyze or `fuseback catalog` writes it). The `specified` gate checks the same; this is the
    check on request that `deltafuse artifact validate --kind capability` was until 3.3.9."""
    from deltafuse.core.integrity import load_capability_catalog
    from deltafuse.core.schemas import SchemaRegistry

    if not (Path(product_root) / "docs" / "spec" / "_capabilities.yaml").is_file():
        return []
    catalog, load_errors = load_capability_catalog(Path(product_root))
    if load_errors or catalog is None:
        return [f"catalog: {e}" for e in load_errors]
    return [f"catalog: docs/spec/_capabilities.yaml: {e}" for e in SchemaRegistry().validate("capability", catalog)]


def load_evidence_timeout(product_root: Path | str) -> int:
    """Seconds `deltafuse evidence` lets the test command run: `workflow.evidence_timeout`, else 90.

    A Maven or Gradle build compiles the whole module before one test runs; on a service of a
    few hundred classes that alone outlasts 90 seconds, and the Worker passing `--timeout` on
    every call is a rule no skill states.
    """
    value = config_section(product_root, "workflow").get("evidence_timeout")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_EVIDENCE_TIMEOUT


_CONFIG_OVERRIDE: contextvars.ContextVar[tuple[str, Any] | None] = contextvars.ContextVar(
    "deltafuse_config_override", default=None
)


def _root_key(product_root: Path | str) -> str:
    return os.path.normcase(str(Path(product_root).resolve()))


@contextlib.contextmanager
def config_as_of(product_root: Path | str, data: Any) -> Iterator[None]:
    """Read *data* as the product's `.deltafuse/config.yaml` while the block runs.

    The leash judges a tree with the config of its base (df-leash #3): the mode and the code
    roots in the tree being judged are what that tree may not change for itself.
    """
    token = _CONFIG_OVERRIDE.set((_root_key(product_root), data))
    try:
        yield
    finally:
        _CONFIG_OVERRIDE.reset(token)


# The human's settings (audit 3, B-6): what decides how the Worker's own work is judged - the leash,
# what is product code, what the whole test suite is and how long it may run, and the task budget.
# `.deltafuse/**` is outside every Worker envelope as a whole, so these are read from the committed
# config, and the leash refuses a diff that changes them (leash.config_guard_errors).
HUMAN_WORKFLOW_KEYS = ("leash", "code_roots", "test_commands", "evidence_timeout")
HUMAN_TOP_KEYS = ("context",)


def with_human_settings(data: Any, base: Any) -> dict[str, Any]:
    """*data* (a config mapping) with every human setting taken from *base* instead."""
    out = dict(data) if isinstance(data, dict) else {}
    base = base if isinstance(base, dict) else {}
    for key in HUMAN_TOP_KEYS:
        if key in base:
            out[key] = base[key]
        else:
            out.pop(key, None)
    workflow = dict(out.get("workflow")) if isinstance(out.get("workflow"), dict) else {}
    base_workflow = base.get("workflow") if isinstance(base.get("workflow"), dict) else {}
    for key in HUMAN_WORKFLOW_KEYS:
        if key in base_workflow:
            workflow[key] = base_workflow[key]
        else:
            workflow.pop(key, None)
    out["workflow"] = workflow
    return out


@contextlib.contextmanager
def human_settings_as_committed(product_root: Path | str) -> Iterator[None]:
    """Read the human's settings from the config committed at HEAD while the block runs.

    Audit 3 (B-6): a regression narrowed with `-Dtest=` was refused, the refusal said to declare
    the command in `workflow.test_commands`, the Worker added it there, and the narrowed run was
    then authentic - the evidence was judged by a setting the Worker had just written. Evidence
    and gates now read those keys as committed (a human's commit; the leash refuses a Worker
    diff that changes them). Without a commit, or a config at HEAD, the file on disk is read.
    A config already put in place by `config_as_of` (the leash judging from its base) stands.
    """
    override = _CONFIG_OVERRIDE.get()
    if override is not None and override[0] == _root_key(product_root):
        yield
        return
    from deltafuse.core.leash import config_at  # leash imports this module

    try:
        committed = config_at(Path(product_root), "HEAD")
    except Exception:  # noqa: BLE001 - no git, no commit: the file on disk is all there is
        committed = None
    if committed is None:
        yield
        return
    try:
        current = yaml.safe_load((Path(product_root) / ".deltafuse" / "config.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - an unreadable config is reported by its validator
        current = None
    with config_as_of(product_root, with_human_settings(current, committed)):
        yield


def config_section(
    product_root: Path | str,
    key: str,
    *,
    tolerate: tuple[type[BaseException], ...] = (Exception,),
) -> dict:
    """One top-level mapping of `.deltafuse/config.yaml`, or {} when the file, its YAML or the
    key is missing or not a mapping. A read or parse error outside *tolerate* propagates.

    Inside `config_as_of`, the config given there stands in for the file."""
    override = _CONFIG_OVERRIDE.get()
    if override is not None and _root_key(product_root) == override[0]:
        data = override[1]
    else:
        try:
            data = yaml.safe_load((Path(product_root) / ".deltafuse" / "config.yaml").read_text(encoding="utf-8"))
        except tolerate:
            return {}
    section = data.get(key) if isinstance(data, dict) else None
    return section if isinstance(section, dict) else {}


def load_trace_claims_mode(product_root: Path | str, *, missing: str = "off") -> str:
    """`workflow.trace_claims`: off (default) or warn. See TRACE_CLAIMS_MODES."""
    mode = config_section(product_root, "workflow").get("trace_claims")
    return mode if mode in TRACE_CLAIMS_MODES else missing
