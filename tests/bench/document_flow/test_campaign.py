from fractions import Fraction
from dataclasses import replace
from types import MappingProxyType

import pytest

from scripts.document_flow.campaign import (
    CampaignError,
    CampaignMember,
    CampaignPlan,
    ReevaluatedRun,
    compare_campaigns,
    evaluate_campaign,
)
from scripts.document_flow.evaluate import RunSummary, StageScore


SHA = "e" * 64
STAGES = ("intake", "analyze", "specify", "decompose", "declare", "implement", "verify")


def summary(score, status="passed", first_failure=None, stage_total=1000):
    if status == "invalid":
        return RunSummary(status, None, None, "invalid", MappingProxyType({}), MappingProxyType({}), (), (first_failure,), (), first_failure)
    raw = 0 if score == 1 else score
    remaining = raw
    stage_values = {}
    for stage in STAGES:
        total = min(1000, remaining)
        remaining -= total
        correctness = min(600, total)
        discipline = min(250, total - correctness)
        stage_values[stage] = StageScore(correctness, discipline, total - correctness - discipline, total)
    system_values = {}
    for group, limit in (("functional", 1800), ("resilience", 600), ("compatibility", 400), ("efficiency", 200)):
        system_values[group] = min(limit, remaining)
        remaining -= system_values[group]
    assert remaining == 0
    stages = MappingProxyType(stage_values)
    return RunSummary(
        status, raw, score, "release_pass" if status == "passed" else "fail",
        stages, MappingProxyType(system_values), (),
        () if first_failure is None else (first_failure,), (), first_failure,
    )


def member(number):
    return CampaignMember(
        f"run-{number}", f"session-{number}", f"sandbox-{number}", SHA,
        SHA, (format(number, "x") * 64)[:64], number, SHA,
    )


def plan(count=3):
    return CampaignPlan("campaign-1", SHA, SHA, SHA, SHA, tuple(member(i) for i in range(1, count + 1)))


def observed(member_value, score, status="passed", first_failure=None):
    return ReevaluatedRun(member_value, summary(score, status, first_failure), SHA, True)


def runs(scores, statuses=None):
    p = plan(len(scores))
    statuses = statuses or ["passed" if score == 10000 else "failed" for score in scores]
    return p, [observed(item, score, status, None if status == "passed" else "process-failure") for item, score, status in zip(p.members, scores, statuses)]


@pytest.mark.parametrize("scores,expected", [
    ([1, 5000, 10000], 3500), ([1, 1, 1], 1), ([10000, 10000, 10000], 10000),
    ([1, 5000, 5000, 10000], 3500), ([1, 2, 15], 2),
])
def test_exact_campaign_arithmetic(scores, expected):
    p, values = runs(scores)
    result = evaluate_campaign(p, values)
    assert result.campaign_score == expected
    assert result.median == (Fraction(5000) if scores == [1, 5000, 5000, 10000] else result.median)


def test_all_failed_valid_campaign_is_retained():
    p, values = runs([1, 1, 1], ["failed", "failed", "failed"])
    result = evaluate_campaign(p, values)
    assert result.status == "complete"
    assert result.campaign_score == 1
    assert result.pass_rate == 0
    assert result.first_failure_distribution == (("process-failure", 3),)


def test_population_variance_and_stage_deltas_are_exact():
    p, values = runs([1, 5000, 10000])
    result = evaluate_campaign(p, values)
    assert result.population_variance == Fraction(149970002, 9)
    assert result.stage_deltas == MappingProxyType({stage: max(item.summary.stages[stage].total for item in values) - min(item.summary.stages[stage].total for item in values) for stage in STAGES})


def test_missing_lowest_or_invalid_member_invalidates_campaign():
    p, values = runs([1, 5000, 10000])
    assert evaluate_campaign(p, values[1:]).status == "incomplete"
    invalid = observed(p.members[0], None, "invalid", "provenance-invalid")
    result = evaluate_campaign(p, [invalid, *values[1:]])
    assert result.status == "invalid"
    assert result.campaign_score is None
    assert result.scores == (None, 5000, 10000)


def test_duplicate_sessions_and_runs_are_rejected():
    p = plan()
    bad_member = CampaignMember("run-2", "session-1", "sandbox-2", SHA, SHA, ("2" * 64), 2, SHA)
    with pytest.raises(CampaignError, match="session"):
        evaluate_campaign(CampaignPlan(p.campaign_id, p.profile_sha256, p.host_sha256, p.contract_sha256, p.registry_sha256, (p.members[0], bad_member, p.members[2])), [])
    values = [observed(item, 10000) for item in p.members]
    with pytest.raises(CampaignError, match="duplicate run"):
        evaluate_campaign(p, [values[0], values[0], values[2]])


@pytest.mark.parametrize("field", ["profile_sha256", "host_sha256", "variant_sha256", "schedule_sha256"])
def test_mixed_profile_host_variant_or_schedule_identity_is_rejected(field):
    p, values = runs([1, 5000, 10000])
    changed = values[1].member
    replacements = {field: "f" * 64}
    mixed = replace(changed, **replacements)
    values[1] = ReevaluatedRun(mixed, values[1].summary, SHA, True)
    with pytest.raises(CampaignError, match="identity mismatch"):
        evaluate_campaign(p, values)


def test_forged_totals_and_non_reevaluated_runs_are_rejected():
    p, values = runs([1, 5000, 10000])
    with pytest.raises(CampaignError, match="claimed campaign score"):
        evaluate_campaign(p, values, claimed_campaign_score=10000)
    values[0] = ReevaluatedRun(values[0].member, values[0].summary, SHA, False)
    with pytest.raises(CampaignError, match="re-evaluated"):
        evaluate_campaign(p, values)
    values = runs([1, 5000, 10000])[1]
    values[1] = ReevaluatedRun(values[1].member, replace(values[1].summary, raw_score=5001), SHA, True)
    with pytest.raises(CampaignError, match="forged raw score"):
        evaluate_campaign(p, values)


def test_order_of_run_inputs_does_not_change_result():
    p, values = runs([1, 5000, 10000])
    assert evaluate_campaign(p, values) == evaluate_campaign(p, list(reversed(values)))


def test_comparison_refuses_incompatible_profiles_and_ranks_compatible_campaigns():
    left_plan, left_runs = runs([1, 5000, 10000])
    right_plan, right_runs = runs([10000, 10000, 10000])
    left = evaluate_campaign(left_plan, left_runs)
    right = evaluate_campaign(right_plan, right_runs)
    compatible = compare_campaigns(left, right)
    assert compatible.status == "compatible"
    assert compatible.score_delta == 6500
    changed_members = tuple(CampaignMember(item.run_id, item.session_id, item.sandbox_id, "f" * 64, item.host_sha256, item.variant_sha256, item.seed, item.schedule_sha256) for item in right_plan.members)
    changed_plan = CampaignPlan("campaign-2", "f" * 64, right_plan.host_sha256, right_plan.contract_sha256, right_plan.registry_sha256, changed_members)
    changed_runs = [observed(item, 10000) for item in changed_members]
    incompatible = compare_campaigns(left, evaluate_campaign(changed_plan, changed_runs))
    assert incompatible.status == "incompatible"
    assert incompatible.score_delta is None
