# Finite State Machine and Gatekeeper rules engine for DeltaFuse Change packages.

from __future__ import annotations
from pathlib import Path
from typing import Any
import re
import yaml
from deltafuse.core.frontmatter import parse_frontmatter, yaml_error_hint
from deltafuse.core.context import (
    validate_context_budget,
    validate_task_context_budget,
    validate_paths_against_globs,
    path_is_listed,
    phase_write_globs,
    task_write_globs,
    load_change_route,
    is_product_code_path,
)
from deltafuse.core.graph import topological_sort, DependencyCycleError
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.analyze import uncovered_primary_capabilities
from deltafuse.core.specify import spec_delta_outside_slice_files
from deltafuse.core.integrity import (
    extract_claims_from_request,
    validate_coverage_completeness,
    draft_spec_files,
    validate_spec_ref,
    validate_decision_ref,
    find_unresolved_decisions_for_change,
    find_unrecorded_terminal_decisions_for_change,
    load_capability_catalog,
    spec_ref_is_under_docs_spec,
    validate_catalog_capability_specs,
    scan_changed_paths_for_private_test_access,
)
from deltafuse.core.gate_receipts import TERMINAL_STATUSES, has_click
from deltafuse.core.schemas import SchemaRegistry, default_registry

VALID_CHANGE_STATUSES = {
    "normalized",
    "analyzing",
    "blocked-on-decision",
    "analyzed",
    "specification-proposed",
    "specified",
    "decomposed",
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
    "rejected",
    "duplicate",
    "superseded",
    "not-reproduced",
}

ALLOWED_CHANGE_TRANSITIONS: dict[str, set[str]] = {
    "normalized": {"analyzing", "rejected", "duplicate"},
    "analyzing": {"blocked-on-decision", "analyzed", "rejected", "duplicate", "superseded", "not-reproduced"},
    "blocked-on-decision": {"analyzing"},
    # decomposed: the bugfix path with the spec unchanged - the queue sends a
    # bugfix from analyzed to decompose, GATE_ALLOWED_FROM and the receipt
    # chain already allowed it, and the specified gate needs a spec-delta a
    # bugfix does not write. Without it every bugfix Change stopped at
    # `advance --gate decomposed` (found 2026-09-22 by a Core-only walk).
    "analyzed": {"specification-proposed", "specified", "decomposed"},
    "specification-proposed": {"specified", "analyzed"},  # analyzed: DF3-004 spec rejection loop
    "specified": {"decomposed"},
    "decomposed": {"declaring"},
    "declaring": {"declared", "not-reproduced"},
    "declared": {"implementing"},
    "implementing": {"implemented"},
    "implemented": {"verifying"},
    "verifying": {"converged", "analyzing", "not-reproduced"},
    "converged": {"archived"},
    "archived": set(),
    "rejected": set(),
    "duplicate": set(),
    "superseded": set(),
    "not-reproduced": set(),
}


def can_transition(from_status: str, to_status: str) -> bool:
    """Checks if a transition between two Change lifecycle statuses is canonically allowed."""
    return to_status in ALLOWED_CHANGE_TRANSITIONS.get(from_status, set())


def find_repo_root(start_path: Path) -> Path:
    """Finds repository root by searching upward for .deltafuse or docs directory."""
    cur = start_path.resolve()
    if cur.is_file():
        cur = cur.parent
    while cur != cur.parent:
        if (cur / "change.yaml").is_file():
            cur = cur.parent
            continue
        if (cur / ".deltafuse").is_dir() or ((cur / "docs").is_dir() and cur.name != "docs"):
            return cur
        cur = cur.parent
    resolved = start_path.resolve()
    if "docs" in resolved.parts:
        idx = resolved.parts.index("docs")
        return Path(*resolved.parts[:idx])
    return start_path.parent


class GateValidationError(Exception):
    def __init__(self, gate: str, errors: list[str]):
        err_list = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"Gate {gate} validation failed with {len(errors)} error(s):\n{err_list}")
        self.gate = gate
        self.errors = errors


CONTRACT_VERSION = 3
LEGACY_TOKENS = ("target-confirmed", "targeting")  # v2 vocabulary, never auto-converted


def _contract_version_errors(change_path: Path) -> list[str]:
    """DF3-008: unknown or partial versions stop with exact diagnostics."""
    errors: list[str] = []
    for rel in ("change.yaml",):
        path = change_path / rel
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        version = data.get("schema_version")
        if version is not None and version != CONTRACT_VERSION:
            errors.append(
                f"change.yaml: schema_version {version!r} is not supported by this "
                f"Core (v{CONTRACT_VERSION}); migrate the artifact manually — no "
                "automatic conversion is performed"
            )
    legacy_files = ["change.yaml"] + [
        str(p.relative_to(change_path)).replace("\\", "/")
        for p in sorted((change_path / "tasks").glob("*.md"))
        if (change_path / "tasks").is_dir()
    ] + [
        str(p.relative_to(change_path)).replace("\\", "/")
        for p in sorted((change_path / "slices").glob("*.md"))
        if (change_path / "slices").is_dir()
    ]
    for rel in legacy_files:
        path = change_path / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in LEGACY_TOKENS:
            if re.search(rf"{token}", text):
                errors.append(
                    f"{rel}: legacy v2 vocabulary '{token}' is not valid in v3; "
                    "rewrite the artifact for schema v3 (no automatic conversion)"
                )
    return errors


def validate_change_package(
    change_dir: Path | str,
    registry: SchemaRegistry | None = None,
) -> list[str]:
    if registry is None:
        registry = default_registry

    change_path = Path(change_dir).resolve()
    errors: list[str] = []

    if not change_path.is_dir():
        return [f"Change package directory not found: {change_path}"]

    # DF3-008: fail-closed contract version and legacy-vocabulary checks.
    version_errors = _contract_version_errors(change_path)
    if version_errors:
        return version_errors

    repo_root = find_repo_root(change_path)
    spec_dir_exists = (repo_root / "docs" / "spec").is_dir()
    draft_specs = draft_spec_files(repo_root)

    change_id: str | None = None
    change_status: str | None = None

    # 1. Validate change.yaml
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        errors.append("Missing required change.yaml in Change directory")
    else:
        try:
            change_data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
            errs = registry.validate("change", change_data)
            errors.extend(f"change.yaml: {e}" for e in errs)
            if isinstance(change_data, dict):
                change_id = change_data.get("id")
                change_status = change_data.get("status")
                if change_status and change_status not in VALID_CHANGE_STATUSES:
                    errors.append(f"change.yaml: invalid status '{change_status}'")

                # Lock hash verification (P7.3)
                lock_file = repo_root / ".deltafuse" / "lock.yaml"
                if lock_file.is_file():
                    try:
                        lock_data = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
                        if isinstance(lock_data, dict):
                            expected_hash = lock_data.get("framework", {}).get("content_hash")
                            change_fw = change_data.get("framework")
                            if expected_hash and isinstance(change_fw, dict):
                                change_hash = change_fw.get("content_hash")
                                if change_hash and change_hash != expected_hash:
                                    errors.append(
                                        f"Framework content hash mismatch: change.yaml has '{change_hash}' but .deltafuse/lock.yaml has '{expected_hash}'"
                                    )
                    except Exception:
                        pass

                # Status vs Artifacts consistency check (P1 / T5)
                has_tasks = (change_path / "tasks").is_dir() and any((change_path / "tasks").glob("*.md"))
                has_evidence = (change_path / "evidence").is_dir() and any((change_path / "evidence").rglob("*.yaml"))

                if change_status == "normalized" and (has_tasks or has_evidence):
                    errors.append(
                        "Status mismatch: change.yaml has status 'normalized' but package already contains decomposed tasks or evidence"
                    )
                elif change_status == "decomposed" and not has_tasks:
                    errors.append(
                        "Status mismatch: change.yaml has status 'decomposed' but no task files exist in tasks/"
                    )
        except Exception as ex:
            errors.append(f"change.yaml parsing error: {ex}{yaml_error_hint(ex)}")

    route, route_errs = load_change_route(change_path)
    errors.extend(route_errs)

    # 1b. Validate request.md presence (P7.5)
    request_file = change_path / "request.md"
    if not request_file.is_file():
        errors.append("Missing required request.md in Change directory")

    # 2. Validate routing.yaml if present
    routing_file = change_path / "routing.yaml"
    if routing_file.is_file():
        try:
            routing_data = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
            errs = registry.validate("routing", routing_data)
            errors.extend(f"routing.yaml: {e}" for e in errs)
            if any("claims" in e for e in errs):
                errors.append(
                    "routing.yaml: "
                    + registry.shape_hint("routing", ("claims", "*"), noun="keys for each claim")
                )
        except Exception as ex:
            errors.append(f"routing.yaml parsing error: {ex}{yaml_error_hint(ex)}")

    # 3. Validate coverage.yaml if present
    coverage_file = change_path / "coverage.yaml"
    if coverage_file.is_file():
        try:
            cov_data = yaml.safe_load(coverage_file.read_text(encoding="utf-8"))
            errs = registry.validate("coverage", cov_data)
            errors.extend(f"coverage.yaml: {e}" for e in errs)

            req_file = change_path / "request.md"
            if req_file.is_file():
                req_claims = extract_claims_from_request(req_file.read_text(encoding="utf-8"))
                cov_errs = validate_coverage_completeness(req_claims, cov_data)
                errors.extend(f"coverage.yaml: {e}" for e in cov_errs)
        except Exception as ex:
            errors.append(f"coverage.yaml error: {ex}{yaml_error_hint(ex)}")

    # 4. Validate slices/
    slices_dir = change_path / "slices"
    if slices_dir.is_dir():
        for slice_file in slices_dir.glob("*.md"):
            try:
                meta, _ = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
                errs = registry.validate("slice", meta)
                errors.extend(f"{slice_file.name}: {e}" for e in errs)
                if errs:
                    errors.append(f"{slice_file.name}: {registry.shape_hint('slice')}")

                # Check spec_refs anchors and context budget (N10, P7.6)
                if isinstance(meta, dict):
                    srefs = meta.get("spec_refs", [])
                    if srefs:
                        if not spec_dir_exists:
                            errors.append(f"{slice_file.name}: Specification root directory 'docs/spec' not found")
                        else:
                            for sref in srefs:
                                s_err = validate_spec_ref(sref, repo_root, drafts=draft_specs)
                                if s_err:
                                    errors.append(f"{slice_file.name}: {s_err}")

                    context_budget = meta.get("context_budget")
                    if context_budget and isinstance(context_budget, dict):
                        ref_files = []
                        for sref in srefs:
                            sp_rel = sref.split("#")[0]
                            ref_files.append(repo_root / sp_rel)
                        b_errs = validate_context_budget(
                            context_budget, ref_files, repo_root=repo_root
                        )
                        errors.extend(f"{slice_file.name}: {be}" for be in b_errs)
            except Exception as ex:
                errors.append(f"{slice_file.name} frontmatter error: {ex}")

    # 5. Validate tasks/ and DAG
    tasks_dir = change_path / "tasks"
    existing_task_ids: set[str] = set()
    if tasks_dir.is_dir():
        task_graph: dict[str, list[str]] = {}
        for task_file in tasks_dir.glob("*.md"):
            try:
                meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
                errs = registry.validate("task", meta)
                errors.extend(f"{task_file.name}: {e}" for e in errs)
                if errs:
                    errors.append(f"{task_file.name}: {registry.shape_hint('task')}")
                if isinstance(meta, dict):
                    task_id = meta.get("id")
                    if task_id:
                        existing_task_ids.add(task_id)
                        task_graph[task_id] = meta.get("depends_on", [])
                    existing_task_ids.add(task_file.stem)

                    # Validate spec_refs anchors (P4 / T7, N10)
                    srefs = meta.get("spec_refs", [])
                    if srefs:
                        if not spec_dir_exists:
                            errors.append(f"{task_file.name}: Specification root directory 'docs/spec' not found")
                        else:
                            for sref in srefs:
                                s_err = validate_spec_ref(sref, repo_root, drafts=draft_specs)
                                if s_err:
                                    errors.append(f"{task_file.name}: {s_err}")

                    # Validate design_ref (P3)
                    design_ref = meta.get("design_ref")
                    if design_ref:
                        d_errs = validate_decision_ref(design_ref, repo_root)
                        errors.extend(f"{task_file.name}: {de}" for de in d_errs)

                    allowed = meta.get("allowed_paths") or []
                    forbidden = meta.get("forbidden_paths") or []
                    if not isinstance(allowed, list):
                        allowed = []
                    if not isinstance(forbidden, list):
                        forbidden = []
                    errors.extend(
                        f"{task_file.name}: {e}"
                        for e in validate_paths_against_globs(
                            [p for p in allowed if isinstance(p, str)],
                            task_write_globs(route),
                            label="allowed_paths",
                        )
                    )
                    if route in {"docs", "ops"}:
                        for apath in allowed:
                            if isinstance(apath, str) and is_product_code_path(apath):
                                errors.append(
                                    f"{task_file.name}: {route} route must not list "
                                    f"src/** or tests/** in allowed_paths ('{apath}')"
                                )
                    for apath in allowed:
                        if isinstance(apath, str) and path_is_listed(apath, forbidden):
                            errors.append(
                                f"{task_file.name}: allowed_paths '{apath}' is also in forbidden_paths"
                            )
                    # On a code route a task proves itself through tests: declare
                    # writes the Red test under tests/**. Forbidding it made declare
                    # impossible, and it surfaced only at the declaring gate, where
                    # the task file is outside the envelope and the Worker cannot
                    # fix it (q0 run 20260921T081038Z). Refuse it here, where
                    # decompose still can.
                    if route not in {"docs", "ops"}:
                        for probe in ("tests/test_probe.py", "tests/unit/test_probe.py"):
                            if path_is_listed(probe, [p for p in forbidden if isinstance(p, str)]):
                                errors.append(
                                    f"{task_file.name}: forbidden_paths covers tests/**, which "
                                    "declare must write for the Red test; remove it from "
                                    "forbidden_paths"
                                )
                                break

                    context_budget = meta.get("context_budget")
                    if not context_budget or not isinstance(context_budget, dict):
                        errors.append(
                            f"{task_file.name}: context_budget is required "
                            "(max_tokens/max_files) for Declare and Implement"
                        )
                    else:
                        b_errs = validate_task_context_budget(
                            context_budget,
                            srefs if isinstance(srefs, list) else [],
                            allowed,
                            repo_root,
                        )
                        errors.extend(f"{task_file.name}: {be}" for be in b_errs)
            except Exception as ex:
                errors.append(f"{task_file.name} frontmatter error: {ex}")

        if task_graph:
            try:
                topological_sort(task_graph)
            except DependencyCycleError as cyc:
                errors.append(f"Task DAG cycle error: {cyc}")

    # 6. Validate spec-delta.md if present
    spec_delta_file = change_path / "spec-delta.md"
    if spec_delta_file.is_file():
        try:
            meta, _ = parse_frontmatter(spec_delta_file.read_text(encoding="utf-8"))
            errs = registry.validate("spec-delta", meta)
            errors.extend(f"spec-delta.md: {e}" for e in errs)
            if errs:
                errors.append(f"spec-delta.md: {registry.shape_hint('spec-delta')}")
            if isinstance(meta, dict):
                added_mod = list(meta.get("added") or []) + list(meta.get("modified") or [])
                if added_mod:
                    if not spec_dir_exists:
                        errors.append("spec-delta.md: Specification root directory 'docs/spec' not found")
                    else:
                        for sref in added_mod:
                            if not isinstance(sref, str):
                                errors.append("spec-delta.md: added/modified entries must be strings")
                                continue
                            if not spec_ref_is_under_docs_spec(sref, repo_root):
                                errors.append(
                                    f"spec-delta.md: '{sref}' must resolve under docs/spec/"
                                )
                                continue
                            s_err = validate_spec_ref(sref, repo_root, drafts=draft_specs)
                            if s_err:
                                errors.append(f"spec-delta.md: {s_err}")
        except Exception as ex:
            errors.append(f"spec-delta.md frontmatter error: {ex}")
            errors.append(
                "spec-delta.md: the file starts with a '---' line, then the frontmatter, "
                f"then '---'; {registry.shape_hint('spec-delta')}"
            )

    # 7. Validate evidence/ (Semantic Validation - P0 / T1, T2, T4)
    evidence_dir = change_path / "evidence"
    if evidence_dir.is_dir():
        for ev_file in evidence_dir.rglob("*.yaml"):
            try:
                ev_data = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
                errs = registry.validate("evidence", ev_data)
                errors.extend(f"{ev_file.relative_to(change_path)}: {e}" for e in errs)

                if not isinstance(ev_data, dict):
                    continue

                from deltafuse.core.evidence import evidence_stamp_error

                stamp_err = evidence_stamp_error(ev_data, repo_root)
                if stamp_err:
                    errors.append(f"{ev_file.relative_to(change_path)}: {stamp_err}")

                rel_path = ev_file.relative_to(evidence_dir)
                parent_phase_dir = rel_path.parts[0] if len(rel_path.parts) > 1 else None

                phase = ev_data.get("phase")
                result = ev_data.get("result")
                exit_code = ev_data.get("exit_code")
                ev_task = ev_data.get("task")
                ev_change = ev_data.get("change")

                # Cross-check Change ID
                if ev_change and change_id and ev_change != change_id:
                    errors.append(
                        f"{ev_file.relative_to(change_path)}: change id mismatch (evidence has '{ev_change}', expected '{change_id}')"
                    )

                # Cross-check Task ID (T4)
                if ev_task:
                    if ev_task not in existing_task_ids:
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: references nonexistent task '{ev_task}'"
                        )
                elif phase in {"red", "green", "regression"}:
                    errors.append(
                        f"{ev_file.relative_to(change_path)}: missing required 'task' field for phase '{phase}'"
                    )

                # Phase directory alignment (T1)
                if parent_phase_dir in {"red", "green", "regression", "verification"}:
                    if phase != parent_phase_dir:
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: phase mismatch (file in '{parent_phase_dir}/' has phase '{phase}')"
                        )

                # Phase-specific result & exit_code rules (T2)
                if phase == "red":
                    if result not in {"expected-failure", "not-reproduced", "already-green"}:
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: red evidence must have result "
                            f"'expected-failure', 'not-reproduced', or 'already-green' (got '{result}')"
                        )
                    if result == "already-green":
                        if exit_code != 0:
                            errors.append(
                                f"{ev_file.relative_to(change_path)}: already-green evidence "
                                f"must have exit_code 0 (got {exit_code})"
                            )
                    elif exit_code == 0 and result != "not-reproduced":
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: red evidence must have "
                            f"non-zero exit_code (got 0)"
                        )
                    if result == "expected-failure" and route == "code":
                        category = ev_data.get("failure_category")
                        if category != "behavioral-mismatch":
                            errors.append(
                                f"{ev_file.relative_to(change_path)}: red expected-failure "
                                f"must have failure_category 'behavioral-mismatch' "
                                f"(got '{category}')" + _red_category_hint(ev_data)
                            )
                        changed = ev_data.get("changed_paths") or []
                        if isinstance(changed, list):
                            errors.extend(
                                f"{ev_file.relative_to(change_path)}: {pe}"
                                for pe in scan_changed_paths_for_private_test_access(
                                    repo_root, changed
                                )
                            )
                elif phase in {"green", "regression"}:
                    if result != "passed":
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: {phase} evidence must have result 'passed' (got '{result}')"
                        )
                    if exit_code != 0:
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: {phase} evidence must have exit_code 0 (got {exit_code})"
                        )
                elif phase == "verification":
                    if exit_code != 0:
                        errors.append(
                            f"{ev_file.relative_to(change_path)}: verification evidence must have exit_code 0 (got {exit_code})"
                        )

                if phase in {"green", "regression", "verification"}:
                    recorded = ev_data.get("base_revision")
                    current = compute_product_baseline_revision(repo_root)
                    rel_ev = ev_file.relative_to(change_path)
                    if not recorded:
                        errors.append(
                            f"{rel_ev}: missing base_revision; Green/regression/verification "
                            "must stamp the docs/spec/** and src/** content hash"
                        )
                    elif recorded != current:
                        rerun = (
                            f"deltafuse evidence <change> --phase {phase} --task {ev_file.stem}"
                            if phase != "verification"
                            else "deltafuse evidence <change> --phase verification"
                        )
                        errors.append(
                            f"{rel_ev}: stale evidence: base_revision '{recorded}' does not "
                            f"match current docs/spec/** and src/** tree '{current}'; a later "
                            f"change moved the tree - re-run it on the current tree: {rerun}"
                        )
            except Exception as ex:
                errors.append(f"{ev_file.relative_to(change_path)} parsing error: {ex}")

    return errors


def _iter_slice_frontmatter(change_path: Path) -> list[tuple[str, dict[str, Any]]]:
    slices_dir = change_path / "slices"
    result: list[tuple[str, dict[str, Any]]] = []
    if not slices_dir.is_dir():
        return result
    for slice_file in slices_dir.glob("*.md"):
        try:
            meta, _ = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(meta, dict):
            result.append((slice_file.name, meta))
    return result


def _validate_specified_live_spec(
    change_path: Path,
    repo_root: Path,
    change_status: str | None,
    spec_delta_file: Path,
    registry: SchemaRegistry,
) -> list[str]:
    """RM-010: specified requires live docs/spec files, a valid catalog, and exact none-refs."""
    errors: list[str] = []
    allowed_status = {"specified", "specification-proposed"}
    if change_status not in allowed_status:
        errors.append(
            "Gate specified: change.yaml status must be 'specified' or "
            f"'specification-proposed' (got {change_status!r})"
        )

    catalog, catalog_load_errs = load_capability_catalog(repo_root)
    errors.extend(f"Gate specified: {e}" for e in catalog_load_errs)
    catalog_schema_ok = False
    if catalog is not None:
        catalog_schema_errs = registry.validate("capability", catalog)
        errors.extend(
            f"Gate specified: docs/spec/_capabilities.yaml: {e}" for e in catalog_schema_errs
        )
        catalog_schema_ok = not catalog_schema_errs

    added: list[str] = []
    modified: list[str] = []
    if spec_delta_file.is_file():
        try:
            meta, _ = parse_frontmatter(spec_delta_file.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                added = [s for s in (meta.get("added") or []) if isinstance(s, str)]
                modified = [s for s in (meta.get("modified") or []) if isinstance(s, str)]
        except Exception as ex:
            errors.append(f"Gate specified: spec-delta.md frontmatter error: {ex}")

    slices = _iter_slice_frontmatter(change_path)
    primary_caps_str: list[str] = []
    for _, meta in slices:
        cap = meta.get("primary_capability")
        if isinstance(cap, str):
            primary_caps_str.append(cap)

    if catalog is not None and catalog_schema_ok:
        errors.extend(
            f"Gate specified: {e}"
            for e in validate_catalog_capability_specs(
                catalog, repo_root, primary_caps_str
            )
        )

    live_ops = added + modified
    if live_ops:
        errors.extend(spec_delta_outside_slice_files(change_path, repo_root))
    if not live_ops:
        if not slices:
            errors.append(
                "Gate specified: requirement_delta none requires slices with exact existing spec_refs"
            )
        for slice_name, meta in slices:
            srefs = meta.get("spec_refs") or []
            if not isinstance(srefs, list) or not srefs:
                errors.append(
                    f"Gate specified: {slice_name} has no spec_refs; "
                    "unchanged specification must cite existing anchors"
                )
                continue
            for sref in srefs:
                if not isinstance(sref, str) or "#" not in sref:
                    errors.append(
                        f"Gate specified: {slice_name} spec_ref {sref!r} must include "
                        "an existing anchor"
                    )
                    continue
                s_err = validate_spec_ref(sref, repo_root)
                if s_err:
                    errors.append(f"Gate specified: {slice_name}: {s_err}")

    return errors


def _task_frontmatter_by_id(change_path: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    tasks_dir = change_path / "tasks"
    if not tasks_dir.is_dir():
        return tasks
    for task_file in tasks_dir.glob("*.md"):
        try:
            meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(meta, dict) and isinstance(meta.get("id"), str):
            tasks[meta["id"]] = meta
    return tasks


_TASKS_CLOSED = frozenset({"cancelled", "superseded"})


def _tasks_behind_gate(
    change_path: Path, gate: str, reached: set[str], phases: tuple[str, ...]
) -> list[str]:
    """Every live task must have reached `reached` with its own evidence.

    The declaring and implemented gates asked for any evidence file at all. In
    q0 run 20260921T130115Z the declaring gate closed with one task of three
    declared - the other two could no longer be declared - and
    `check-gate implemented` read "passed" with two tasks still pending.
    """
    command = {"declaring": "declared", "implemented": "implemented"}[gate]
    errors: list[str] = []
    for task_id, meta in sorted(_task_frontmatter_by_id(change_path).items()):
        status = meta.get("status")
        if status in _TASKS_CLOSED:
            continue
        if status not in reached:
            errors.append(
                f"Gate {gate}: task {task_id} is '{status}'; every task must be "
                f"{command} first (deltafuse state <change> --task {task_id} --status {command})"
            )
        for phase in phases:
            if not (change_path / "evidence" / phase / f"{task_id}.yaml").is_file():
                errors.append(
                    f"Gate {gate}: task {task_id} has no {phase} evidence "
                    f"(evidence/{phase}/{task_id}.yaml)"
                )
    return errors


VERIFICATION_OUTCOMES = (
    "converged",
    "tasks-missing",
    "spec-gap",
    "test-gap",
    "scope-drift",
    "decision-gap",
    "not-reproduced",
)

_OUTCOME_LINE = re.compile(
    r"^[ \t]*[-*]?[ \t]*\**Outcome\**[ \t]*:[ \t]*(?P<value>.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _verification_outcome_errors(ver_file: Path) -> list[str]:
    """Read the verdict Verify wrote, not merely that it wrote a file.

    verification.md is hand-written prose that structural_kind excludes, so it
    has no schema and the converged gate asked only `.is_file()`: a file
    recording "test-gap ... Do not converge" closed the very gate it was telling
    the Core not to close. The vocabulary and the `- Outcome:` line are the
    shipped template's and verify/SKILL.md's.
    """
    try:
        text = ver_file.read_text(encoding="utf-8", errors="replace")
    except OSError as ex:
        return [f"Gate converged: verification.md cannot be read: {ex}"]
    match = _OUTCOME_LINE.search(text)
    if match is None:
        return [
            "Gate converged: verification.md records no outcome; add a line "
            "`- Outcome: <verdict>` where <verdict> is exactly one of "
            + ", ".join(VERIFICATION_OUTCOMES)
        ]
    raw = match.group("value").strip().strip("`").strip()
    outcome = raw.lower()
    if outcome not in VERIFICATION_OUTCOMES:
        return [
            f"Gate converged: verification.md outcome {raw[:80]!r} is not one of "
            + ", ".join(VERIFICATION_OUTCOMES)
            + "; the template's placeholder line is not a verdict - replace it"
        ]
    if outcome != "converged":
        return [
            f"Gate converged: verification.md records the gap '{outcome}', so Verify did not "
            "converge this Change; a gap stops here and is not repaired silently - fix what "
            "the gap names, then write the verification again"
        ]
    return []


def frozen_oracle_errors(red_file: Path, repo_root: Path, label: str) -> list[str]:
    """The oracle Red was taken against is frozen; Implement may add tests, not change it.

    Green was matched to Red by test *name* alone, so rewriting the assertion
    during Implement produced an authentic Green and an authentic regression
    over a product nobody had changed. A record with `red_oracle_tests` froze
    the tests Red saw fail (core/oracle.py); one with only `red_oracle` froze
    the declared files whole and is checked that way. A record with neither was
    written before the freeze existed, or declared no test file, and has
    nothing to compare against.
    """
    from deltafuse.core.hasher import compute_red_oracle_digest, oracle_paths
    from deltafuse.core.oracle import red_oracle_changes

    try:
        red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(red, dict):
        return []
    paths = [p for p in (red.get("changed_paths") or []) if isinstance(p, str)]
    per_test = red.get("red_oracle_tests")
    if isinstance(per_test, dict):
        changes = red_oracle_changes(repo_root, per_test)
        if not changes:
            return []
        what = "; ".join(changes)
    else:
        recorded = red.get("red_oracle")
        if not isinstance(recorded, str) or not recorded:
            return []
        if compute_red_oracle_digest(repo_root, paths) == recorded:
            return []
        frozen = oracle_paths(paths)
        what = f"{', '.join(frozen) or 'the declared test files'} changed after Declare"
    return [
        f"the frozen Red oracle behind {label} no longer matches what Red recorded - "
        f"{what}. "
        "Implement may add tests but must not edit the one Red was taken against: rewriting the "
        "oracle so it passes leaves the product unchanged and proves nothing. Restore the "
        "declared test, or - if the oracle itself was wrong - record Red again with "
        "`deltafuse evidence --phase red` and take it from there"
    ]


def isolation_errors(red_file: Path, green_file: Path, label: str) -> list[str]:
    """The frozen tests must pass on their own, not only inside the Worker's run.

    The freeze holds the oracle's source fixed, but a new test in the same file
    can still change what it sees at run time - patch the product module, fill
    a cache - and a command-line option can load a plugin that does. So Green
    also runs the frozen tests alone (evidence `oracle_isolation`), and a Green
    whose runner reported tests but carries no isolated run was not recorded
    by this Core, or skipped it.
    """
    from deltafuse.core.oracle import frozen_test_ids

    try:
        red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
        green = yaml.safe_load(green_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(red, dict) or not isinstance(green, dict):
        return []
    frozen = red.get("red_oracle_tests")
    if not isinstance(frozen, dict) or frozen.get("version") is None:
        return []
    red_tests = red.get("tests") if isinstance(red.get("tests"), dict) else {}
    expected = frozen_test_ids(frozen, [str(t) for t in red_tests.get("failed") or []])
    if not expected:
        return []
    isolation = green.get("oracle_isolation")
    if not isinstance(isolation, dict):
        if isinstance(green.get("tests"), dict) and green.get("exit_code") == 0:
            return [
                f"{label} has no isolated run of the frozen Red tests: record Green again with "
                "`deltafuse evidence --phase green`, which runs them on their own"
            ]
        return []
    not_passing = [str(t) for t in isolation.get("not_passing") or []]
    if not not_passing:
        return []
    green_tests = green.get("tests") if isinstance(green.get("tests"), dict) else {}
    passed_in_green = {str(t) for t in green_tests.get("passed") or []}
    if not passed_in_green & set(not_passing):
        # Green's own run did not pass them either (it ran other tests), so
        # nothing "helped" them - they simply do not pass yet.
        return [
            f"the frozen Red tests behind {label} do not pass: {not_passing[:5]} - neither "
            "Green's own run nor the run of those tests alone passed them. Make the product "
            "pass the tests Red recorded, and record Green over them"
        ]
    return [
        f"the frozen Red tests behind {label} do not pass on their own: {not_passing[:5]}. "
        "They passed in the full run only because something else in it made them pass - a "
        "test that patches the product or leaves state behind, or an option on the command "
        "line. Make the product pass them by itself"
    ]


def _already_green_red_errors(red_file: Path, label: str) -> list[str]:
    """An already-green Red proves no delta, so it cannot carry `implemented`.

    Green is checked against the Red record's own `tests.failed`
    (green_covers_red), which is empty when the oracle already passed on
    unchanged product code: the implemented gate closed on a product nobody had
    modified, and nothing downstream could tell. Declare may still record the
    observation - it is a legal Declare outcome, and a stopping one.
    """
    try:
        red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(red, dict) or red.get("result") != "already-green":
        return []
    return [
        f"Gate implemented: green evidence '{label}' answers an already-green Red - the "
        "declared oracle passed on unchanged product code, so there is no failure for this "
        "Green to have removed and nothing here proves a delta. Declare a Red that fails for "
        "the expected public reason, or, if the requirement is genuinely already met, close "
        "the Change on the no-op path (terminal status 'not-reproduced') instead of Implement"
    ]


def _validate_evidence_changed_paths_contract(
    change_path: Path,
    evidence_phase: str,
    contract_phase: str,
    *,
    gate: str,
    route: str = "code",
) -> list[str]:
    """RM-002: evidence changed_paths must stay inside route write globs.

    Declare additionally honours the task's own `allowed_paths`: on a compiled
    language the test cannot reference a symbol that does not exist yet, so the
    throwing stub has to be written in Declare - which is what
    declare/SKILL.md tells the Worker to do and why test_reports.py reads a JVM
    `<error>` as a test that ran and failed. The task cannot use this to widen
    its envelope in Declare: `allowed_paths` is already bounded by its slice at
    the `decomposed` gate (task_envelope_errors) and `tasks/**` is outside
    Declare's write scope.
    """
    errors: list[str] = []
    ev_dir = change_path / "evidence" / evidence_phase
    if not ev_dir.is_dir():
        return errors
    write_globs = phase_write_globs(contract_phase, route)
    tasks = _task_frontmatter_by_id(change_path)
    for ev_file in ev_dir.glob("*.yaml"):
        try:
            ev_data = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(ev_data, dict):
            continue
        changed = ev_data.get("changed_paths") or []
        if not isinstance(changed, list):
            continue
        rel_paths = [p for p in changed if isinstance(p, str)]
        task_id = ev_data.get("task")
        declared: list[str] = []
        forbidden: list[str] = []
        if isinstance(task_id, str) and task_id in tasks:
            raw_allowed = tasks[task_id].get("allowed_paths") or []
            if isinstance(raw_allowed, list):
                declared = [p for p in raw_allowed if isinstance(p, str)]
            raw = tasks[task_id].get("forbidden_paths") or []
            if isinstance(raw, list):
                forbidden = [p for p in raw if isinstance(p, str)]
        allowed_globs = list(write_globs)
        if evidence_phase == "red" and route == "code":
            allowed_globs += declared
        for msg in validate_paths_against_globs(
            rel_paths,
            allowed_globs,
            label=f"Gate {gate} {evidence_phase} changed_paths",
        ):
            errors.append(msg + (_RED_WRITES_HINT if evidence_phase == "red" else ""))
        if route in {"docs", "ops"}:
            for rel in rel_paths:
                if is_product_code_path(rel):
                    errors.append(
                        f"Gate {gate}: {ev_file.relative_to(change_path)} {route} route "
                        f"must not write src/** or tests/** ('{rel}')"
                    )
        for rel in rel_paths:
            if path_is_listed(rel, forbidden):
                errors.append(
                    f"Gate {gate}: {ev_file.relative_to(change_path)} changed_paths "
                    f"'{rel}' is listed in task forbidden_paths"
                )
    return errors


def _spec_delta_ops(spec_delta_file: Path) -> tuple[dict[str, list[str]], list[str]]:
    ops: dict[str, list[str]] = {"added": [], "modified": [], "removed": []}
    errors: list[str] = []
    if not spec_delta_file.is_file():
        return ops, errors
    try:
        meta, _ = parse_frontmatter(spec_delta_file.read_text(encoding="utf-8"))
    except Exception as ex:
        return ops, [f"spec-delta.md frontmatter error: {ex}"]
    if not isinstance(meta, dict):
        return ops, errors
    for key in ops:
        raw = meta.get(key) or []
        if not isinstance(raw, list):
            errors.append(f"spec-delta.md: {key} must be a list")
            continue
        for item in raw:
            if isinstance(item, str):
                ops[key].append(item)
            else:
                errors.append(f"spec-delta.md: {key} entries must be strings")
    return ops, errors


def _validate_spec_delta_matches_disk(
    repo_root: Path,
    ops: dict[str, list[str]],
    *,
    gate: str,
) -> list[str]:
    """RM-008: added/modified must exist; removed must be gone. Not a spec merge on archive."""
    errors: list[str] = []
    for kind in ("added", "modified"):
        for sref in ops.get(kind) or []:
            if not spec_ref_is_under_docs_spec(sref, repo_root):
                errors.append(
                    f"Gate {gate}: spec-delta {kind} '{sref}' must resolve under docs/spec/"
                )
                continue
            s_err = validate_spec_ref(sref, repo_root)
            if s_err:
                errors.append(f"Gate {gate}: spec-delta {kind} is not on disk: {s_err}")
    for sref in ops.get("removed") or []:
        if not spec_ref_is_under_docs_spec(sref, repo_root):
            errors.append(
                f"Gate {gate}: spec-delta removed '{sref}' must resolve under docs/spec/"
            )
            continue
        s_err = validate_spec_ref(sref, repo_root)
        if s_err is None:
            errors.append(
                f"Gate {gate}: spec-delta removed '{sref}' is still present in docs/spec/"
            )
        elif "Path traversal" in s_err:
            errors.append(f"Gate {gate}: {s_err}")
    return errors


_RED_WRITES_HINT = (
    " (Red writes tests, plus only the product paths this task's allowed_paths declares - a "
    "compiled-language stub; the rest of the product code is written in Implement, after Red "
    "is recorded)"
)


def _red_category_hint(ev_data: dict) -> str:
    """Why a Red record is not a behavioural failure, and what is not the fix.

    Gemma read only the category and edited product code to make a test fail on
    an assertion (gemma-334-probe M01), when the record's own summary said its
    command had never run.
    """
    summary = str(ev_data.get("summary") or "").strip().splitlines()
    last = summary[-1].strip()[:160] if summary else ""
    said = f"; the record says: {last}" if last else ""
    return (
        f"{said}. The test did not run to a failure: fix the test or the command and "
        "record Red again. Do not edit product code in this phase - a test that calls an "
        "API which does not exist yet fails with AttributeError or TypeError, and that "
        "is a legitimate Red"
    )


def _uncharacterized_draft_errors(change_path: Path, repo_root: Path) -> list[str]:
    """q6 5(b), D7: once the baseline is accepted, a Change does not start on inherited code
    nobody has characterized.

    A draft whose `code_roots` hold code is that case. A draft whose roots hold nothing is
    the new capability q8 lets a Worker propose in Analyze - it must not be stopped, and
    neither must any draft while the baseline is still `draft` (the Bootstrap profile).
    The test is the code on disk, not only a non-empty list: a proposal may name the
    directory it means to create.
    """
    from deltafuse.core.capability import draft_capabilities
    from deltafuse.core.leash import load_baseline
    from deltafuse.core.ownership import (
        DIRECT_SUFFIX,
        capability_code_roots,
        is_direct_root,
        routed_capabilities,
    )

    if load_baseline(repo_root) != "accepted":
        return []
    routed = sorted(routed_capabilities(change_path))
    drafts = draft_capabilities(repo_root, routed)
    if not drafts:
        return []
    roots = capability_code_roots(repo_root)
    out: list[str] = []
    for name in drafts:
        prefixes = roots.get(name) or next(
            (v for k, v in roots.items() if k.endswith("." + name)), []
        )
        for prefix in prefixes:
            direct = is_direct_root(prefix)
            base = repo_root / (prefix[: -len(DIRECT_SUFFIX)] if direct else prefix.rstrip("/"))
            # A direct root `dir/*` holds only the files lying in `dir`; a tree root, all below.
            candidates = base.iterdir() if direct and base.is_dir() else base.rglob("*")
            if base.is_dir() and any(
                p.is_file() and "__pycache__" not in p.parts for p in candidates
            ):
                out.append(
                    f"Gate analyzed: capability '{name}' is a draft and its code_roots hold code "
                    f"({prefix}) that no characterization pins; characterize it first and set it "
                    "active before routing a Change into it"
                )
                break
    return out


def _draft_capability_errors(gate: str, change_path: Path, repo_root: Path) -> list[str]:
    """A capability this Change routes into must be the human's before it closes.

    The Worker may propose one in Analyze (`deltafuse capability propose`,
    q8 decision) and the catalog carries it as a draft until the human accepts
    the spec at the `specified` gate. Checked again at `converged`: this is the
    catalog rule q6 was holding - no Change converges into a draft.
    """
    from deltafuse.core.analyze import routing_primary_capabilities
    from deltafuse.core.capability import draft_capabilities

    drafts = draft_capabilities(repo_root, routing_primary_capabilities(change_path))
    return [
        f"Gate {gate}: capability '{name}' is still a draft in "
        "docs/spec/_capabilities.yaml; the human accepts it (status: active) "
        "together with the specification"
        for name in drafts
    ]


def missing_analyze_artifacts(change_path: Path | str) -> list[str]:
    """Analyze substeps not yet on disk. `analyzed` requires this list to be empty.

    A Change cannot close Analyze without routing.yaml, slices/, and coverage.yaml.
    One slice file does not cover two routing primary capabilities; that is a
    separate `analyzed` error from `uncovered_primary_capabilities`.
    """
    path = Path(change_path)
    missing: list[str] = []
    if not (path / "routing.yaml").is_file():
        missing.append("routing.yaml")
    slices = path / "slices"
    if not slices.is_dir() or not any(slices.glob("*.md")):
        missing.append("slices/")
    if not (path / "coverage.yaml").is_file():
        missing.append("coverage.yaml")
    return missing


def _spec_delta_status(spec_delta_file: Path) -> str | None:
    if not spec_delta_file.is_file():
        return None
    try:
        meta, _ = parse_frontmatter(spec_delta_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    raw = meta.get("status")
    return raw if isinstance(raw, str) else None


def _human_gate_errors(
    *,
    gate: str,
    change_id: str,
    change_status: str | None,
    repo_root: Path,
    spec_delta_file: Path,
    require_spec_acceptance: bool = False,
) -> list[str]:
    errors: list[str] = []
    from deltafuse.core.gate_receipts import journal_errors as receipt_journal_errors

    errors.extend(receipt_journal_errors(repo_root))
    unresolved = find_unresolved_decisions_for_change(change_id, repo_root)
    if unresolved:
        errors.append(
            f"Gate {gate}: Change '{change_id}' is blocked-on-decision: {'; '.join(unresolved)}"
        )
    unrecorded = find_unrecorded_terminal_decisions_for_change(change_id, repo_root)
    if unrecorded:
        errors.append(f"Gate {gate}: {'; '.join(unrecorded)}")
    if gate != "specified":
        return errors
    spec_status = _spec_delta_status(spec_delta_file)
    if spec_status in TERMINAL_STATUSES:
        rel = spec_delta_file.resolve().relative_to(repo_root.resolve()).as_posix()
        from deltafuse.core.gate_receipts import has_valid_receipt

        if not has_valid_receipt(
            repo_root,
            kind="spec",
            status=spec_status,
            artifact_id=change_id,
            rel_path=rel,
            artifact=spec_delta_file,
        ):
            errors.append(
                f"Gate specified: spec-delta.md is {spec_status} without deltafuse decide"
            )
    if change_status == "specified" and spec_status != "accepted":
        errors.append(
            "Gate specified: specified requires spec-delta.md accepted via "
            f"deltafuse decide (got {spec_status!r})"
        )
    # The proposed path to 'specified' is the Human Gate itself: leaving
    # specification-proposed needs the human's accepted verdict. Without this a
    # spec delta still 'proposed' passed the gate, and the Worker could run
    # `deltafuse advance --gate specified` past the human (q0, campaign
    # 20260921T072327Z). The terminal-status check above then proves the
    # verdict came through decide.
    if (
        require_spec_acceptance
        and change_status == "specification-proposed"
        and spec_status != "accepted"
    ):
        errors.append(
            "Gate specified: leaving specification-proposed needs spec-delta.md "
            f"accepted via deltafuse decide (Human Gate); got {spec_status!r}"
        )
    return errors


def _derived_coverage(change_path: Path) -> dict[str, Any] | None:
    """coverage.yaml as the Core would write it now, or None when it cannot."""
    from deltafuse.core.analyze import CoverageError, build_coverage_document

    try:
        return build_coverage_document(change_path)
    except (CoverageError, OSError):
        return None


def check_gate(
    change_dir: Path | str,
    gate: str,
    registry: SchemaRegistry | None = None,
    *,
    assume_status: str | None = None,
    human: bool = True,
) -> list[str]:
    """Gate errors for a Change, with the cause first when a file was written by hand."""
    errors = _check_gate(change_dir, gate, registry, assume_status=assume_status, human=human)
    if not errors:
        return errors
    return _hand_written_causes(Path(change_dir), errors) + errors


def _hand_written_causes(change_path: Path, errors: list[str]) -> list[str]:
    """Name the cause once when a hand-written file is what the schema errors are about.

    glm-4.7-flash wrote routing, slices and `change.yaml` by hand: the leash refused them, but
    the files stayed, and every later gate answered with their schema errors (39 x 3
    `[deltas -> N] is a required property`, 34 for routing.yaml). A Worker patching those
    one at a time never learned the file should not exist in that form.
    """
    from deltafuse.core.leash import hand_written_errors, structural_kind, vouched_digests

    try:
        root = find_repo_root(change_path)
        vouched = vouched_digests(root)
        rel_dir = change_path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return []
    notes: list[str] = []
    candidates = [change_path / "routing.yaml", change_path / "spec-delta.md"]
    for folder in ("slices", "tasks"):
        if (change_path / folder).is_dir():
            candidates += sorted((change_path / folder).glob("*.md"))
    for path in candidates:
        if not path.is_file() or not any(path.name in err for err in errors):
            continue
        rel = f"{rel_dir}/{path.relative_to(change_path).as_posix()}"
        kind = structural_kind(rel)
        if kind and hand_written_errors(root, rel, head=None, vouched=vouched):
            notes.append(
                f"{path.name} was written by hand, not through the Artifact Writer, so the errors "
                f"about it below are the file's, not yours to patch one by one: delete it and "
                f"recreate it with `deltafuse artifact write --kind {kind} --change {rel_dir}`"
            )
    if sum(1 for err in errors if err.startswith("change.yaml:")) >= 3:
        notes.append(
            "change.yaml has several schema errors: its fields are written with "
            f"`deltafuse artifact write --kind change --change {rel_dir}`, not edited by hand"
        )
    return notes


def _check_gate(
    change_dir: Path | str,
    gate: str,
    registry: SchemaRegistry | None = None,
    *,
    assume_status: str | None = None,
    human: bool = True,
) -> list[str]:
    """Gate errors for a Change. ``assume_status`` evaluates the gate as if
    change.yaml held that status, without writing it: the Core asks "would
    this pass once moved?" before it moves anything. ``human=False`` leaves out
    everything only the human can supply - the verdict a Human Gate waits for and
    a capability catalog still in ``draft`` - and is only for checking whether a
    spec delta is ready to be put in front of the human at all."""
    change_path = Path(change_dir).resolve()
    errors = validate_change_package(change_path, registry=registry)

    repo_root = find_repo_root(change_path)

    # V3-FIX-009: a gate may only be evaluated on top of an intact Core
    # receipt chain; hand-edited statuses halt before gate logic.
    from deltafuse.core.transitions import receipt_chain_errors

    errors.extend(receipt_chain_errors(repo_root, change_path))
    req_file = change_path / "request.md"
    spec_delta_file = change_path / "spec-delta.md"
    tasks_dir = change_path / "tasks"

    change_id: str = change_path.name
    change_status: str | None = None
    change_file = change_path / "change.yaml"
    if change_file.is_file():
        try:
            cdata = yaml.safe_load(change_file.read_text(encoding="utf-8"))
            if isinstance(cdata, dict):
                if "id" in cdata:
                    change_id = cdata["id"]
                change_status = cdata.get("status")
        except Exception:
            pass
    if assume_status is not None:
        change_status = assume_status

    gate_lower = gate.lower()

    if gate_lower == "intake":
        if not req_file.is_file():
            errors.append("Gate intake: request.md is missing")

    elif gate_lower == "analyzed":
        if not req_file.is_file():
            errors.append("Gate analyzed: request.md is missing")
        for artifact in missing_analyze_artifacts(change_path):
            if artifact == "routing.yaml":
                errors.append("Gate analyzed: routing.yaml is missing")
            elif artifact == "slices/":
                errors.append("Gate analyzed: at least one slice file in slices/ is required")
            elif artifact == "coverage.yaml" and _derived_coverage(change_path) is None:
                # The Core derives coverage and `advance` writes it; the gate
                # asks only whether it can be derived (roadmap item 4, box A).
                errors.append("Gate analyzed: coverage.yaml is missing")
        for cap in uncovered_primary_capabilities(change_path):
            errors.append(
                f"Gate analyzed: routing capability '{cap}' has no slice"
            )
        errors.extend(_uncharacterized_draft_errors(change_path, repo_root))

        errors.extend(
            _human_gate_errors(
                gate="analyzed",
                change_id=change_id,
                change_status=change_status,
                repo_root=repo_root,
                spec_delta_file=spec_delta_file,
            )
        )

    elif gate_lower == "specified":
        if not spec_delta_file.is_file():
            errors.append("Gate specified: spec-delta.md is missing")
        if human:
            # A capability still in `draft` is the human's to accept, and they
            # accept it together with the specification - so it cannot be a
            # precondition of handing that specification to them. Demanding it
            # here deadlocked specify: `specification-proposed` refused until the
            # catalog was active, and `decide --spec` refused until the Change was
            # proposed. Checked again at `converged`, which no proposal skips.
            errors.extend(_draft_capability_errors("specified", change_path, repo_root))
        errors.extend(
            _human_gate_errors(
                gate="specified",
                change_id=change_id,
                change_status=change_status,
                repo_root=repo_root,
                spec_delta_file=spec_delta_file,
                require_spec_acceptance=human,
            )
        )
        errors.extend(
            _validate_specified_live_spec(
                change_path,
                repo_root,
                change_status,
                spec_delta_file,
                registry or default_registry,
            )
        )

    elif gate_lower == "decomposed":
        if not tasks_dir.is_dir() or not list(tasks_dir.glob("*.md")):
            errors.append("Gate decomposed: at least one task file in tasks/ is required")

        # DF3-006 / SEC-04: a task cannot widen its write envelope by
        # editing YAML; allowed_paths must stay inside slice target_paths.
        from deltafuse.core.leash import task_envelope_errors

        errors.extend(task_envelope_errors(change_path))

    elif gate_lower == "declaring":
        route, route_errs = load_change_route(change_path)
        errors.extend(route_errs)
        red_dir = change_path / "evidence" / "red"
        if not red_dir.is_dir() or not list(red_dir.glob("*.yaml")):
            errors.append("Gate declaring: Red evidence in evidence/red/ is required")
        errors.extend(
            _tasks_behind_gate(
                change_path,
                "declaring",
                {"declared", "implementing", "implemented", "verified"},
                ("red",),
            )
        )
        errors.extend(
            _validate_evidence_changed_paths_contract(
                change_path, "red", "declare", gate="declaring", route=route
            )
        )

    elif gate_lower == "implemented":
        route, route_errs = load_change_route(change_path)
        errors.extend(route_errs)
        green_dir = change_path / "evidence" / "green"
        reg_dir = change_path / "evidence" / "regression"
        if not green_dir.is_dir() or not list(green_dir.glob("*.yaml")):
            errors.append("Gate implemented: Green evidence in evidence/green/ is required")
        if route == "code":
            if not reg_dir.is_dir() or not list(reg_dir.glob("*.yaml")):
                errors.append("Gate implemented: Regression evidence in evidence/regression/ is required")
        behind = _tasks_behind_gate(
            change_path,
            "implemented",
            {"implemented", "verified"},
            ("green", "regression") if route == "code" else ("green",),
        )
        if any("every task must be implemented first" in e for e in behind):
            # Tasks still to implement come first, and an earlier task's stale
            # evidence is left out: the next task moves src again, and the queue
            # routes the re-run once every task is implemented. In q0 run
            # 20260921T181306Z the Worker re-ran TASK-001's evidence on the
            # first error instead of implementing TASK-002.
            errors[:] = behind + [e for e in errors if ": stale evidence:" not in e]
        else:
            errors.extend(behind)
        errors.extend(
            _validate_evidence_changed_paths_contract(
                change_path, "green", "implement", gate="implemented", route=route
            )
        )
        if reg_dir.is_dir() and list(reg_dir.glob("*.yaml")):
            errors.extend(
                _validate_evidence_changed_paths_contract(
                    change_path, "regression", "implement", gate="implemented", route=route
                )
            )


        # DF3-006: Red and Green are bound to one test oracle — a Green stamp
        # without the task's own Red evidence does not close the gate.
        if green_dir.is_dir() and list(green_dir.glob("*.yaml")):
            for green_file in sorted(green_dir.glob("*.yaml")):
                red_file = change_path / "evidence" / "red" / green_file.name
                if not red_file.is_file():
                    errors.append(
                        f"Gate implemented: green evidence '{green_file.name}' has no matching Red evidence"
                    )
                    continue
                if route == "code":
                    errors.extend(_already_green_red_errors(red_file, green_file.name))
                    errors.extend(
                        f"Gate implemented: {e}"
                        for e in frozen_oracle_errors(
                            red_file, repo_root, f"green evidence '{green_file.name}'"
                        )
                    )
                    errors.extend(
                        f"Gate implemented: {e}"
                        for e in isolation_errors(
                            red_file, green_file, f"green evidence '{green_file.name}'"
                        )
                    )

    elif gate_lower == "converged":
        ver_file = change_path / "verification.md"
        ver_run = change_path / "evidence" / "verification" / "run.yaml"
        if not ver_file.is_file():
            errors.append("Gate converged: verification.md is missing")
        else:
            errors.extend(_verification_outcome_errors(ver_file))
        if not ver_run.is_file():
            errors.append("Gate converged: evidence/verification/run.yaml is missing")
        errors.extend(_draft_capability_errors("converged", change_path, repo_root))

        # Check all tasks frontmatter status (P1 / T3 / RM-005)
        if tasks_dir.is_dir():
            terminal = {"implemented", "verified", "cancelled", "superseded"}
            for task_file in tasks_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
                    task_status = meta.get("status")
                    if task_status not in terminal:
                        errors.append(
                            f"Gate converged: task '{task_file.name}' has non-terminal status '{task_status}' "
                            "(must be 'implemented', 'verified', 'cancelled', or 'superseded')"
                        )
                except Exception as ex:
                    errors.append(f"Gate converged: failed to parse task '{task_file.name}': {ex}")

        # Coverage evidence mapping check (P4). DF3-002 / F-02: route-aware —
        # docs/ops routes keep their own green oracle and are not required to
        # carry product-source regression evidence.
        cov_file = change_path / "coverage.yaml"
        route, route_errs = load_change_route(change_path)
        errors.extend(route_errs)
        derived = _derived_coverage(change_path)
        if derived is not None or cov_file.is_file():
            try:
                cov_data = derived if derived is not None else yaml.safe_load(cov_file.read_text(encoding="utf-8"))
                claims_map = cov_data.get("claims", {})
                for c_id, c_val in claims_map.items():
                    if isinstance(c_val, dict):
                        ev_map = c_val.get("evidence", {})
                        missing = []
                        if not ev_map.get("green"):
                            missing.append("green")
                        if route == "code" and not ev_map.get("regression"):
                            missing.append("regression")
                        if missing:
                            errors.append(
                                f"Gate converged: claim '{c_id}' in coverage.yaml is missing {' and '.join(missing)} evidence mapping"
                            )
            except Exception:
                pass

        if spec_delta_file.is_file():
            ops, parse_errs = _spec_delta_ops(spec_delta_file)
            errors.extend(f"Gate converged: {e}" for e in parse_errs)
            errors.extend(
                _validate_spec_delta_matches_disk(repo_root, ops, gate="converged")
            )

    return errors
