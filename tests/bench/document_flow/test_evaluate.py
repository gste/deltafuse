from fractions import Fraction
from pathlib import Path

import pytest

from scripts.document_flow.evaluate import (
    Ceiling,
    CheckFact,
    EvaluationError,
    StageFactors,
    apply_score_policy,
    evaluate_run,
)
from scripts.document_flow.registry import load_registry


REGISTRY = load_registry(Path("scripts/document_flow/contracts/checks.json"))
ALL_GATES = {gate: True for gate in REGISTRY.hard_gate_ids}


def facts(status="pass"):
    return [CheckFact(check.id, status, (f"objects/{check.id}.json",)) for check in REGISTRY.checks]


def factors(value=Fraction(1, 1), provenance=("objects/metrics.json",)):
    return {stage: StageFactors(value, value, value, value, provenance) for stage in REGISTRY.stages}


@pytest.mark.parametrize("raw,expected", [(0, 1), (1, 1), (4999, 4999), (5000, 5000), (6999, 6999), (7000, 7000), (9999, 9999), (10000, 10000)])
def test_score_boundaries(raw, expected):
    score, ceilings = apply_score_policy(raw)
    assert score == expected
    assert ceilings == ()


def test_all_ceiling_boundaries_and_combination():
    score, ceilings = apply_score_policy(8000, lifecycle_complete=False, functional_system_failure=True, integrity_violation=True)
    assert score == 1999
    assert [(item.kind, item.limit) for item in ceilings] == [
        ("incomplete_lifecycle", 4999), ("functional_system_failure", 6999), ("integrity_or_substitution", 1999)
    ]
    assert apply_score_policy(100, False, True, True)[0] == 100


def test_maximum_is_derived_and_release_passes():
    result = evaluate_run(REGISTRY, facts(), factors(), ALL_GATES)
    assert result.raw_score == 10000
    assert result.final_score == 10000
    assert result.release_verdict == "release_pass"


def test_valid_zero_performance_clamps_to_one():
    result = evaluate_run(REGISTRY, facts("fail"), factors(Fraction(0)), ALL_GATES)
    assert result.raw_score == 0
    assert result.final_score == 1
    assert result.release_verdict == "fail"


def test_missing_factor_is_zero_but_missing_provenance_invalidates():
    missing = {stage: StageFactors(None, None, None, None, ("objects/metrics.json",)) for stage in REGISTRY.stages}
    result = evaluate_run(REGISTRY, facts("fail"), missing, ALL_GATES)
    assert all(stage.efficiency == 0 for stage in result.stages.values())
    invalid = evaluate_run(REGISTRY, facts("fail"), factors(Fraction(0), None), ALL_GATES)
    assert invalid.final_score is None
    assert invalid.release_verdict == "invalid"
    assert invalid.first_failure == "provenance-invalid"


def test_half_even_efficiency_rounding_is_exact():
    low = StageFactors(Fraction(1, 120), 0, 0, 0, ("evidence",))
    high = StageFactors(Fraction(1, 40), 0, 0, 0, ("evidence",))
    stage_factors = factors(Fraction(0))
    stage_factors["intake"] = low
    assert evaluate_run(REGISTRY, facts("fail"), stage_factors, ALL_GATES).stages["intake"].efficiency == 0
    stage_factors["intake"] = high
    assert evaluate_run(REGISTRY, facts("fail"), stage_factors, ALL_GATES).stages["intake"].efficiency == 2


@pytest.mark.parametrize("bad", [True, -1, Fraction(2, 1), 0.5])
def test_invalid_factor_primitives_are_rejected(bad):
    stage_factors = factors()
    stage_factors["intake"] = StageFactors(bad, 1, 1, 1, ("evidence",))
    with pytest.raises(EvaluationError, match="factor"):
        evaluate_run(REGISTRY, facts(), stage_factors, ALL_GATES)


def test_forged_supplied_totals_are_rejected():
    with pytest.raises(EvaluationError, match="supplied totals"):
        evaluate_run(REGISTRY, facts(), factors(), ALL_GATES, claimed_totals={"raw_score": 10000})


def test_unknown_duplicate_and_contradictory_check_facts_are_rejected():
    with pytest.raises(EvaluationError, match="unknown outcome"):
        evaluate_run(REGISTRY, facts() + [CheckFact("UNKNOWN", "pass", ("evidence",))], factors(), ALL_GATES)
    with pytest.raises(EvaluationError, match="duplicate check fact"):
        evaluate_run(REGISTRY, facts() + [facts()[0]], factors(), ALL_GATES)
    values = facts()
    values[3] = CheckFact("IN.C04", "fail", ("evidence",))
    with pytest.raises(EvaluationError, match="prerequisite"):
        evaluate_run(REGISTRY, values, factors(), ALL_GATES)


def test_invalidity_precedes_numeric_scoring():
    result = evaluate_run(REGISTRY, facts(), factors(), ALL_GATES, validity_failures=("oracle-leak", "host/model-invalid"))
    assert result.raw_score is None and result.final_score is None
    assert result.release_verdict == "invalid"
    assert result.first_failure == "host/model-invalid"


def test_invalid_failure_class_alone_forces_invalidity():
    result = evaluate_run(REGISTRY, facts(), factors(), ALL_GATES, failure_classes=("oracle-leak",))
    assert result.final_score is None
    assert result.release_verdict == "invalid"


def test_product_build_failure_implies_functional_ceiling():
    result = evaluate_run(REGISTRY, facts(), factors(), ALL_GATES, failure_classes=("product-build-failure",))
    assert result.raw_score == 10000
    assert result.final_score == 6999
    assert Ceiling("functional_system_failure", 6999) in result.applied_ceilings


def test_each_absolute_gate_is_independent_and_ordered():
    for gate in sorted(ALL_GATES):
        gates = dict(ALL_GATES)
        gates[gate] = False
        result = evaluate_run(REGISTRY, facts(), factors(), gates)
        assert result.release_verdict == "fail"
        assert gate in result.hard_failures
    gates = dict(ALL_GATES)
    gates["GATE.TELEMETRY_COMPLETE"] = False
    gates["GATE.CONTEXT_CAP"] = False
    assert evaluate_run(REGISTRY, facts(), factors(), gates).first_failure == "GATE.CONTEXT_CAP"


def test_input_order_cannot_change_result():
    forward = evaluate_run(REGISTRY, facts(), factors(), ALL_GATES)
    reverse_factors = dict(reversed(list(factors().items())))
    reverse = evaluate_run(REGISTRY, list(reversed(facts())), reverse_factors, dict(reversed(list(ALL_GATES.items()))))
    assert reverse == forward
