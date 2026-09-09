# Finite State Machine and Gatekeeper rules engine for DeltaFuse Change packages.

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.context import validate_context_budget
from deltafuse.core.graph import topological_sort, DependencyCycleError
from deltafuse.core.hasher import compute_product_baseline_revision
from deltafuse.core.integrity import (
    extract_claims_from_request,
    validate_coverage_completeness,
    validate_spec_ref,
    validate_decision_ref,
    find_unresolved_decisions_for_change,
    load_capability_catalog,
    spec_ref_is_under_docs_spec,
    validate_catalog_capability_specs,
    scan_changed_paths_for_private_test_access,
)
from deltafuse.core.schemas import SchemaRegistry, default_registry

VALID_CHANGE_STATUSES = {
    "normalized",
    "analyzing",
    "blocked-on-decision",
    "analyzed",
    "specification-proposed",
    "specified",
    "decomposed",
    "targeting",
    "target-confirmed",
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
    "analyzed": {"specification-proposed", "specified", "targeting"},  # targeting for bugfix
    "specification-proposed": {"specified"},
    "specified": {"decomposed"},
    "decomposed": {"targeting"},
    "targeting": {"target-confirmed", "not-reproduced"},
    "target-confirmed": {"implementing"},
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

    repo_root = find_repo_root(change_path)
    spec_dir_exists = (repo_root / "docs" / "spec").is_dir()

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
            errors.append(f"change.yaml parsing error: {ex}")

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
        except Exception as ex:
            errors.append(f"routing.yaml parsing error: {ex}")

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
            errors.append(f"coverage.yaml error: {ex}")

    # 4. Validate slices/
    slices_dir = change_path / "slices"
    if slices_dir.is_dir():
        for slice_file in slices_dir.glob("*.md"):
            try:
                meta, _ = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
                errs = registry.validate("slice", meta)
                errors.extend(f"{slice_file.name}: {e}" for e in errs)

                # Check spec_refs anchors and context budget (N10, P7.6)
                if isinstance(meta, dict):
                    srefs = meta.get("spec_refs", [])
                    if srefs:
                        if not spec_dir_exists:
                            errors.append(f"{slice_file.name}: Specification root directory 'docs/spec' not found")
                        else:
                            for sref in srefs:
                                s_err = validate_spec_ref(sref, repo_root)
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
                                s_err = validate_spec_ref(sref, repo_root)
                                if s_err:
                                    errors.append(f"{task_file.name}: {s_err}")

                    # Validate design_ref (P3)
                    design_ref = meta.get("design_ref")
                    if design_ref:
                        d_errs = validate_decision_ref(design_ref, repo_root)
                        errors.extend(f"{task_file.name}: {de}" for de in d_errs)
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
                            s_err = validate_spec_ref(sref, repo_root)
                            if s_err:
                                errors.append(f"spec-delta.md: {s_err}")
        except Exception as ex:
            errors.append(f"spec-delta.md frontmatter error: {ex}")

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
                    if result == "expected-failure":
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
                        errors.append(
                            f"{rel_ev}: stale evidence: base_revision '{recorded}' does not "
                            f"match current docs/spec/** and src/** tree '{current}'"
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


def check_gate(
    change_dir: Path | str,
    gate: str,
    registry: SchemaRegistry | None = None,
) -> list[str]:
    change_path = Path(change_dir).resolve()
    errors = validate_change_package(change_path, registry=registry)

    repo_root = find_repo_root(change_path)
    req_file = change_path / "request.md"
    routing_file = change_path / "routing.yaml"
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

    gate_lower = gate.lower()

    if gate_lower == "intake":
        if not req_file.is_file():
            errors.append("Gate intake: request.md is missing")

    elif gate_lower == "analyzed":
        if not req_file.is_file():
            errors.append("Gate analyzed: request.md is missing")
        if not routing_file.is_file():
            errors.append("Gate analyzed: routing.yaml is missing")
        if not (change_path / "slices").is_dir() or not list((change_path / "slices").glob("*.md")):
            errors.append("Gate analyzed: at least one slice file in slices/ is required")
        if not (change_path / "coverage.yaml").is_file():
            errors.append("Gate analyzed: coverage.yaml is missing")

        # Check blocking decisions (P3)
        unresolved = find_unresolved_decisions_for_change(change_id, repo_root)
        if unresolved:
            errors.append(
                f"Gate analyzed: Change '{change_id}' is blocked-on-decision: {'; '.join(unresolved)}"
            )

    elif gate_lower == "specified":
        if not spec_delta_file.is_file():
            errors.append("Gate specified: spec-delta.md is missing")
        # Check blocking decisions (P3)
        unresolved = find_unresolved_decisions_for_change(change_id, repo_root)
        if unresolved:
            errors.append(
                f"Gate specified: Change '{change_id}' is blocked-on-decision: {'; '.join(unresolved)}"
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

    elif gate_lower == "targeting":
        red_dir = change_path / "evidence" / "red"
        if not red_dir.is_dir() or not list(red_dir.glob("*.yaml")):
            errors.append("Gate targeting: Red evidence in evidence/red/ is required")

    elif gate_lower == "implemented":
        green_dir = change_path / "evidence" / "green"
        reg_dir = change_path / "evidence" / "regression"
        if not green_dir.is_dir() or not list(green_dir.glob("*.yaml")):
            errors.append("Gate implemented: Green evidence in evidence/green/ is required")
        if not reg_dir.is_dir() or not list(reg_dir.glob("*.yaml")):
            errors.append("Gate implemented: Regression evidence in evidence/regression/ is required")

    elif gate_lower == "converged":
        ver_file = change_path / "verification.md"
        ver_run = change_path / "evidence" / "verification" / "run.yaml"
        if not ver_file.is_file():
            errors.append("Gate converged: verification.md is missing")
        if not ver_run.is_file():
            errors.append("Gate converged: evidence/verification/run.yaml is missing")

        # Check all tasks frontmatter status (P1 / T3)
        if tasks_dir.is_dir():
            for task_file in tasks_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
                    task_status = meta.get("status")
                    if task_status not in {"implemented", "verified"}:
                        errors.append(
                            f"Gate converged: task '{task_file.name}' has non-terminal status '{task_status}' "
                            "(must be 'implemented' or 'verified')"
                        )
                except Exception as ex:
                    errors.append(f"Gate converged: failed to parse task '{task_file.name}': {ex}")

        # Coverage evidence mapping check (P4)
        cov_file = change_path / "coverage.yaml"
        if cov_file.is_file():
            try:
                cov_data = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
                claims_map = cov_data.get("claims", {})
                for c_id, c_val in claims_map.items():
                    if isinstance(c_val, dict):
                        ev_map = c_val.get("evidence", {})
                        if not ev_map.get("green") or not ev_map.get("regression"):
                            errors.append(
                                f"Gate converged: claim '{c_id}' in coverage.yaml is missing green or regression evidence mapping"
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
