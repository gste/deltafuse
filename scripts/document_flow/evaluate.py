"""Pure, exact scoring for a single J03 run."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Iterable, Mapping

from scripts.document_flow.registry import FrozenRegistry


FACTOR_NAMES = ("context", "file_focus", "tools", "retries")
FACTOR_WEIGHTS = (Fraction(2, 5), Fraction(1, 4), Fraction(3, 20), Fraction(1, 5))
GATE_ORDER = (
    "GATE.CONTEXT_CAP",
    "GATE.TELEMETRY_COMPLETE",
    "GATE.LIFECYCLE_COMPLETE",
    "GATE.QUALIFIED_PROVENANCE",
)
INVALID_PRECEDENCE = (
    "infrastructure-invalid",
    "host/model-invalid",
    "oracle-leak",
    "provenance-invalid",
)
FAILURE_PRECEDENCE = (
    "worker-tool-failure",
    "process-failure",
    "artifact-correctness-failure",
    "product-build-failure",
    "product-functional-failure",
    "product-resilience-failure",
    "security-boundary-failure",
)
STAGE_PREFIX = {
    "IN": "intake", "AN": "analyze", "SP": "specify", "DE": "decompose",
    "RD": "declare", "IM": "implement", "VE": "verify",
}
SYSTEM_GROUPS = ("functional", "resilience", "compatibility", "efficiency")


class EvaluationError(ValueError):
    """Inputs are malformed or contradict the frozen scoring contract."""


@dataclass(frozen=True)
class CheckFact:
    check_id: str
    status: str
    evidence_refs: tuple[str, ...] | None


@dataclass(frozen=True)
class StageFactors:
    context: Fraction | int | None
    file_focus: Fraction | int | None
    tools: Fraction | int | None
    retries: Fraction | int | None
    provenance_refs: tuple[str, ...] | None


@dataclass(frozen=True)
class StageScore:
    correctness: int
    discipline: int
    efficiency: int
    total: int


@dataclass(frozen=True)
class Ceiling:
    kind: str
    limit: int


@dataclass(frozen=True)
class RunSummary:
    status: str
    raw_score: int | None
    final_score: int | None
    release_verdict: str
    stages: Mapping[str, StageScore]
    system_groups: Mapping[str, int]
    applied_ceilings: tuple[Ceiling, ...]
    hard_failures: tuple[str, ...]
    failure_classes: tuple[str, ...]
    first_failure: str | None


def _factor(value: Fraction | int | None, name: str) -> Fraction:
    if value is None:
        return Fraction(0)
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise EvaluationError(f"factor {name} must be an exact rational or null")
    exact = Fraction(value)
    if exact.numerator.bit_length() > 256 or exact.denominator.bit_length() > 256:
        raise EvaluationError(f"factor {name} exceeds the bounded rational size")
    if exact < 0 or exact > 1:
        raise EvaluationError(f"factor {name} is outside [0,1]")
    return exact


def _efficiency(factors: StageFactors, stage: str) -> int:
    values = tuple(_factor(getattr(factors, name), f"{stage}.{name}") for name in FACTOR_NAMES)
    return round(150 * sum((weight * value for weight, value in zip(FACTOR_WEIGHTS, values)), Fraction(0)))


def apply_score_policy(
    raw_score: int,
    lifecycle_complete: bool = True,
    functional_system_failure: bool = False,
    integrity_violation: bool = False,
) -> tuple[int, tuple[Ceiling, ...]]:
    """Clamp a derived raw score and apply every applicable ceiling."""
    for name, value in (
        ("lifecycle_complete", lifecycle_complete),
        ("functional_system_failure", functional_system_failure),
        ("integrity_violation", integrity_violation),
    ):
        if not isinstance(value, bool):
            raise EvaluationError(f"{name} must be boolean")
    if isinstance(raw_score, bool) or not isinstance(raw_score, int) or not 0 <= raw_score <= 10000:
        raise EvaluationError("derived raw score must be an integer in [0,10000]")
    ceilings: list[Ceiling] = []
    if not lifecycle_complete:
        ceilings.append(Ceiling("incomplete_lifecycle", 4999))
    if functional_system_failure:
        ceilings.append(Ceiling("functional_system_failure", 6999))
    if integrity_violation:
        ceilings.append(Ceiling("integrity_or_substitution", 1999))
    score = max(1, min(10000, raw_score))
    if ceilings:
        score = min(score, *(item.limit for item in ceilings))
    return score, tuple(ceilings)


def evaluate_run(
    registry: FrozenRegistry,
    check_facts: Iterable[CheckFact],
    stage_factors: Mapping[str, StageFactors],
    absolute_gates: Mapping[str, bool],
    *,
    lifecycle_complete: bool = True,
    functional_system_failure: bool = False,
    integrity_violation: bool = False,
    validity_failures: Iterable[str] = (),
    failure_classes: Iterable[str] = (),
    claimed_totals: Mapping[str, int] | None = None,
) -> RunSummary:
    """Derive a run result from frozen registry facts and exact measurements."""
    if claimed_totals is not None:
        raise EvaluationError("supplied totals are forbidden; scores are derived")
    facts = tuple(check_facts)
    fact_ids = [fact.check_id for fact in facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise EvaluationError("duplicate check fact")
    known_ids = {check.id for check in registry.checks}
    unknown = set(fact_ids) - known_ids
    if unknown:
        raise EvaluationError(f"unknown outcome check id: {', '.join(sorted(unknown))}")
    missing = known_ids - set(fact_ids)
    if missing:
        raise EvaluationError(f"missing check fact: {', '.join(sorted(missing))}")
    by_id = {fact.check_id: fact for fact in facts}
    provenance_invalid = False
    for fact in facts:
        if fact.status not in ("pass", "fail", "not_reached"):
            raise EvaluationError(f"invalid status for {fact.check_id}")
        if fact.evidence_refs is not None and (
            not isinstance(fact.evidence_refs, tuple)
            or any(not isinstance(ref, str) or not ref for ref in fact.evidence_refs)
            or len(fact.evidence_refs) != len(set(fact.evidence_refs))
        ):
            raise EvaluationError(f"malformed evidence refs for {fact.check_id}")
        if fact.status != "not_reached" and not fact.evidence_refs:
            provenance_invalid = True
    for check in registry.checks:
        if by_id[check.id].status == "pass":
            failed_prerequisites = [item for item in check.prerequisite_ids if by_id[item].status != "pass"]
            if failed_prerequisites:
                raise EvaluationError(f"prerequisite contradiction for {check.id}: {', '.join(failed_prerequisites)}")

    if set(stage_factors) != set(registry.stages):
        raise EvaluationError("stage factors must contain exactly the seven registered stages")
    efficiencies: dict[str, int] = {}
    for stage in registry.stages:
        item = stage_factors[stage]
        if not isinstance(item, StageFactors):
            raise EvaluationError(f"stage factor record required for {stage}")
        efficiencies[stage] = _efficiency(item, stage)
        if item.provenance_refs is None:
            provenance_invalid = True
        elif (
            not isinstance(item.provenance_refs, tuple)
            or not item.provenance_refs
            or any(not isinstance(ref, str) or not ref for ref in item.provenance_refs)
            or len(item.provenance_refs) != len(set(item.provenance_refs))
        ):
            raise EvaluationError(f"malformed factor provenance for {stage}")

    if set(absolute_gates) != set(GATE_ORDER) or set(absolute_gates) != set(registry.hard_gate_ids):
        raise EvaluationError("absolute gates must exactly match the frozen registry")
    if any(not isinstance(value, bool) for value in absolute_gates.values()):
        raise EvaluationError("absolute gate observations must be boolean")
    if not isinstance(lifecycle_complete, bool) or not isinstance(functional_system_failure, bool) or not isinstance(integrity_violation, bool):
        raise EvaluationError("failure and lifecycle observations must be boolean")

    invalid_set = set(validity_failures)
    if invalid_set - set(INVALID_PRECEDENCE):
        raise EvaluationError(f"unknown validity failure: {', '.join(sorted(invalid_set - set(INVALID_PRECEDENCE)))}")
    if provenance_invalid:
        invalid_set.add("provenance-invalid")
    class_set = set(failure_classes)
    allowed_classes = set(FAILURE_PRECEDENCE) | set(INVALID_PRECEDENCE)
    if class_set - allowed_classes:
        raise EvaluationError(f"unknown failure class: {', '.join(sorted(class_set - allowed_classes))}")
    invalid_set.update(class_set & set(INVALID_PRECEDENCE))
    if class_set & {"product-build-failure", "product-functional-failure"}:
        functional_system_failure = True
    ordered_classes = tuple(item for item in INVALID_PRECEDENCE + FAILURE_PRECEDENCE if item in invalid_set | class_set)
    if invalid_set:
        first = next(item for item in INVALID_PRECEDENCE if item in invalid_set)
        return RunSummary("invalid", None, None, "invalid", MappingProxyType({}), MappingProxyType({}), (), tuple(item for item in INVALID_PRECEDENCE if item in invalid_set), ordered_classes, first)

    stage_points = {stage: {"correctness": 0, "discipline": 0} for stage in registry.stages}
    system_points = {group: 0 for group in SYSTEM_GROUPS}
    for check in registry.checks:
        if by_id[check.id].status != "pass":
            continue
        if check.category == "system":
            system_points[check.group.removeprefix("system.")] += check.points
        else:
            stage = STAGE_PREFIX[check.id.split(".", 1)[0]]
            stage_points[stage][check.category] += check.points
    stages = {
        stage: StageScore(values["correctness"], values["discipline"], efficiencies[stage], values["correctness"] + values["discipline"] + efficiencies[stage])
        for stage, values in stage_points.items()
    }
    raw_score = sum(item.total for item in stages.values()) + sum(system_points.values())
    lifecycle_complete = lifecycle_complete and absolute_gates["GATE.LIFECYCLE_COMPLETE"]
    final_score, ceilings = apply_score_policy(raw_score, lifecycle_complete, functional_system_failure, integrity_violation)

    hard_failures: list[str] = [gate for gate in GATE_ORDER if not absolute_gates[gate]]
    if not lifecycle_complete and "GATE.LIFECYCLE_COMPLETE" not in hard_failures:
        hard_failures.append("incomplete_lifecycle")
    hard_failures.extend(check.id for check in registry.checks if check.hard_gate and by_id[check.id].status != "pass")
    if functional_system_failure:
        hard_failures.append("functional_system_failure")
    if integrity_violation:
        hard_failures.append("integrity_or_substitution")
    for item in FAILURE_PRECEDENCE:
        if item in class_set and item not in hard_failures:
            hard_failures.append(item)
    release_pass = not hard_failures
    first_failure = hard_failures[0] if hard_failures else None
    return RunSummary(
        "passed" if release_pass else "failed",
        raw_score,
        final_score,
        "release_pass" if release_pass else "fail",
        MappingProxyType(stages),
        MappingProxyType(system_points),
        ceilings,
        tuple(hard_failures),
        ordered_classes,
        first_failure,
    )
