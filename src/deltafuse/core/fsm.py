# Finite State Machine and Gatekeeper rules engine for DeltaFuse Change packages.

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.graph import topological_sort, DependencyCycleError
from deltafuse.core.integrity import extract_claims_from_request, validate_coverage_completeness
from deltafuse.core.schemas import SchemaRegistry, default_registry

VALID_CHANGE_STATUSES = {
    "normalized",
    "analyzing",
    "analyzed",
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

    # 1. Validate change.yaml
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        errors.append("Missing required change.yaml in Change directory")
    else:
        try:
            change_data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
            errs = registry.validate("change", change_data)
            errors.extend(f"change.yaml: {e}" for e in errs)
        except Exception as ex:
            errors.append(f"change.yaml parsing error: {ex}")

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
            except Exception as ex:
                errors.append(f"{slice_file.name} frontmatter error: {ex}")

    # 5. Validate tasks/ and DAG
    tasks_dir = change_path / "tasks"
    if tasks_dir.is_dir():
        task_graph: dict[str, list[str]] = {}
        for task_file in tasks_dir.glob("*.md"):
            try:
                meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
                errs = registry.validate("task", meta)
                errors.extend(f"{task_file.name}: {e}" for e in errs)
                task_id = meta.get("id")
                if task_id:
                    task_graph[task_id] = meta.get("depends_on", [])
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
        except Exception as ex:
            errors.append(f"spec-delta.md frontmatter error: {ex}")

    # 7. Validate evidence/
    evidence_dir = change_path / "evidence"
    if evidence_dir.is_dir():
        for ev_file in evidence_dir.rglob("*.yaml"):
            try:
                ev_data = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
                errs = registry.validate("evidence", ev_data)
                errors.extend(f"{ev_file.relative_to(change_path)}: {e}" for e in errs)
            except Exception as ex:
                errors.append(f"{ev_file.relative_to(change_path)} parsing error: {ex}")

    return errors


def check_gate(
    change_dir: Path | str,
    gate: str,
    registry: SchemaRegistry | None = None,
) -> list[str]:
    change_path = Path(change_dir).resolve()
    errors = validate_change_package(change_path, registry=registry)
    if errors:
        return errors

    req_file = change_path / "request.md"
    routing_file = change_path / "routing.yaml"
    spec_delta_file = change_path / "spec-delta.md"
    tasks_dir = change_path / "tasks"

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

    elif gate_lower == "specified":
        if not spec_delta_file.is_file():
            errors.append("Gate specified: spec-delta.md is missing")

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

    return errors
