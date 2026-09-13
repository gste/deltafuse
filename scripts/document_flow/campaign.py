"""Exact J03 campaign aggregation and compatibility-aware comparison."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Iterable, Mapping

from scripts.document_flow.evaluate import Ceiling, RunSummary, StageScore


STAGES = ("intake", "analyze", "specify", "decompose", "declare", "implement", "verify")
SYSTEM_GROUPS = ("functional", "resilience", "compatibility", "efficiency")


class CampaignError(ValueError):
    """Campaign inputs do not match the frozen preregistered plan."""


@dataclass(frozen=True)
class CampaignMember:
    run_id: str
    session_id: str
    sandbox_id: str
    profile_sha256: str
    host_sha256: str
    variant_sha256: str
    seed: int
    schedule_sha256: str


@dataclass(frozen=True)
class CampaignPlan:
    campaign_id: str
    profile_sha256: str
    host_sha256: str
    contract_sha256: str
    registry_sha256: str
    members: tuple[CampaignMember, ...]


@dataclass(frozen=True)
class ReevaluatedRun:
    member: CampaignMember
    summary: RunSummary
    semantic_result_hash: str
    re_evaluated: bool


@dataclass(frozen=True)
class CampaignSummary:
    campaign_id: str
    status: str
    campaign_score: int | None
    scores: tuple[int | None, ...]
    median: Fraction | None
    minimum: int | None
    mean: Fraction | None
    pass_rate: Fraction
    population_variance: Fraction | None
    first_failure_distribution: tuple[tuple[str, int], ...]
    stage_deltas: Mapping[str, int]
    stage_means: Mapping[str, Fraction]
    first_failure: str | None
    compatibility_identity: tuple[object, ...]


@dataclass(frozen=True)
class CampaignComparison:
    status: str
    reason: str | None
    score_delta: int | None
    stage_deltas: Mapping[str, Fraction]


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_member(member: CampaignMember) -> None:
    if not isinstance(member, CampaignMember):
        raise CampaignError("campaign member has the wrong type")
    for name in ("run_id", "session_id", "sandbox_id"):
        if not isinstance(getattr(member, name), str) or not getattr(member, name):
            raise CampaignError(f"member {name} must be a nonempty string")
    for name in ("profile_sha256", "host_sha256", "variant_sha256", "schedule_sha256"):
        if not _is_hash(getattr(member, name)):
            raise CampaignError(f"member {name} must be a SHA256")
    if isinstance(member.seed, bool) or not isinstance(member.seed, int) or member.seed < 0:
        raise CampaignError("member seed must be a nonnegative integer")


def _validate_plan(plan: CampaignPlan) -> None:
    if not isinstance(plan, CampaignPlan) or not plan.campaign_id:
        raise CampaignError("campaign plan identity is missing")
    for name in ("profile_sha256", "host_sha256", "contract_sha256", "registry_sha256"):
        if not _is_hash(getattr(plan, name)):
            raise CampaignError(f"plan {name} must be a SHA256")
    if not isinstance(plan.members, tuple) or len(plan.members) < 3:
        raise CampaignError("campaign plan requires at least three members")
    for member in plan.members:
        _validate_member(member)
        if member.profile_sha256 != plan.profile_sha256 or member.host_sha256 != plan.host_sha256:
            raise CampaignError(f"member identity mismatch for {member.run_id}")
    for field in ("run_id", "session_id", "sandbox_id"):
        values = [getattr(member, field) for member in plan.members]
        if len(values) != len(set(values)):
            label = "run" if field == "run_id" else field.removesuffix("_id")
            raise CampaignError(f"duplicate {label} identity")


def _median(scores: list[int]) -> Fraction:
    ordered = sorted(scores)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[middle])
    return Fraction(ordered[middle - 1] + ordered[middle], 2)


def _validate_summary(run_id: str, summary: RunSummary) -> None:
    if summary.status == "invalid":
        if summary.raw_score is not None or summary.final_score is not None or summary.release_verdict != "invalid":
            raise CampaignError(f"invalid run has numeric score: {run_id}")
        return
    if summary.status not in ("passed", "failed"):
        raise CampaignError(f"unknown run status for {run_id}")
    if tuple(summary.stages) != STAGES or tuple(summary.system_groups) != SYSTEM_GROUPS:
        raise CampaignError(f"re-evaluated run group identities differ: {run_id}")
    for stage, value in summary.stages.items():
        if not isinstance(value, StageScore) or value.total != value.correctness + value.discipline + value.efficiency:
            raise CampaignError(f"forged stage total for {run_id}:{stage}")
        if not (0 <= value.correctness <= 600 and 0 <= value.discipline <= 250 and 0 <= value.efficiency <= 150 and 0 <= value.total <= 1000):
            raise CampaignError(f"stage total out of range for {run_id}:{stage}")
    limits = {"functional": 1800, "resilience": 600, "compatibility": 400, "efficiency": 200}
    for group, value in summary.system_groups.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= limits[group]:
            raise CampaignError(f"system total out of range for {run_id}:{group}")
    derived_raw = sum(value.total for value in summary.stages.values()) + sum(summary.system_groups.values())
    if summary.raw_score != derived_raw:
        raise CampaignError(f"forged raw score for {run_id}")
    derived_final = max(1, min(10000, derived_raw))
    allowed_ceilings = {
        "incomplete_lifecycle": 4999,
        "functional_system_failure": 6999,
        "integrity_or_substitution": 1999,
    }
    seen_ceilings: set[str] = set()
    for ceiling in summary.applied_ceilings:
        if not isinstance(ceiling, Ceiling) or allowed_ceilings.get(ceiling.kind) != ceiling.limit or ceiling.kind in seen_ceilings:
            raise CampaignError(f"invalid applied ceiling for {run_id}")
        seen_ceilings.add(ceiling.kind)
    if summary.applied_ceilings:
        derived_final = min(derived_final, *(ceiling.limit for ceiling in summary.applied_ceilings))
    if summary.final_score != derived_final:
        raise CampaignError(f"forged final score for {run_id}")
    expected_verdict = "release_pass" if summary.status == "passed" else "fail"
    if summary.release_verdict != expected_verdict:
        raise CampaignError(f"run verdict mismatch for {run_id}")
    if summary.status == "passed" and (summary.hard_failures or summary.first_failure is not None):
        raise CampaignError(f"passing run contains failure evidence: {run_id}")
    if summary.status == "failed" and (not summary.hard_failures or summary.first_failure != summary.hard_failures[0]):
        raise CampaignError(f"failed run lacks deterministic first failure: {run_id}")


def _diagnostics(
    plan: CampaignPlan,
    ordered_runs: list[ReevaluatedRun | None],
) -> tuple[tuple[int | None, ...], Fraction | None, int | None, Fraction | None, Fraction, Fraction | None, tuple[tuple[str, int], ...], Mapping[str, int], Mapping[str, Fraction]]:
    scores = tuple(run.summary.final_score if run is not None else None for run in ordered_runs)
    numeric = [score for score in scores if score is not None]
    median = _median(numeric) if numeric else None
    minimum = min(numeric) if numeric else None
    mean = Fraction(sum(numeric), len(numeric)) if numeric else None
    variance = Fraction(sum((Fraction(score) - mean) ** 2 for score in numeric), len(numeric)) if numeric else None
    passed = sum(run is not None and run.summary.status == "passed" for run in ordered_runs)
    pass_rate = Fraction(passed, len(plan.members))
    failures = Counter(
        run.summary.first_failure
        for run in ordered_runs
        if run is not None and run.summary.first_failure is not None
    )
    valid_runs = [run for run in ordered_runs if run is not None and run.summary.status in ("passed", "failed")]
    stages = tuple(valid_runs[0].summary.stages) if valid_runs else ()
    for run in valid_runs:
        if tuple(run.summary.stages) != stages:
            raise CampaignError("re-evaluated run stage identities differ")
    stage_deltas = {
        stage: max(run.summary.stages[stage].total for run in valid_runs) - min(run.summary.stages[stage].total for run in valid_runs)
        for stage in stages
    }
    stage_means = {
        stage: Fraction(sum(run.summary.stages[stage].total for run in valid_runs), len(valid_runs))
        for stage in stages
    }
    return scores, median, minimum, mean, pass_rate, variance, tuple(sorted(failures.items())), MappingProxyType(stage_deltas), MappingProxyType(stage_means)


def evaluate_campaign(
    plan: CampaignPlan,
    runs: Iterable[ReevaluatedRun],
    *,
    claimed_campaign_score: int | None = None,
) -> CampaignSummary:
    """Evaluate exactly the plan's required runs, retaining failures and gaps."""
    if claimed_campaign_score is not None:
        raise CampaignError("claimed campaign score is forbidden")
    _validate_plan(plan)
    observed = tuple(runs)
    run_ids = [run.member.run_id for run in observed]
    if len(run_ids) != len(set(run_ids)):
        raise CampaignError("duplicate run identity")
    expected = {member.run_id: member for member in plan.members}
    extras = set(run_ids) - set(expected)
    if extras:
        raise CampaignError(f"unexpected run: {', '.join(sorted(extras))}")
    by_id: dict[str, ReevaluatedRun] = {}
    for run in observed:
        if not isinstance(run, ReevaluatedRun) or run.re_evaluated is not True:
            raise CampaignError("every campaign member must be re-evaluated")
        if run.member != expected[run.member.run_id]:
            raise CampaignError(f"identity mismatch for {run.member.run_id}")
        if not _is_hash(run.semantic_result_hash):
            raise CampaignError(f"semantic result hash missing for {run.member.run_id}")
        summary = run.summary
        if not isinstance(summary, RunSummary):
            raise CampaignError(f"re-evaluated summary missing for {run.member.run_id}")
        _validate_summary(run.member.run_id, summary)
        by_id[run.member.run_id] = run
    ordered_runs = [by_id.get(member.run_id) for member in plan.members]
    missing_ids = [member.run_id for member, run in zip(plan.members, ordered_runs) if run is None]
    invalid_ids = [run.member.run_id for run in ordered_runs if run is not None and run.summary.status == "invalid"]
    scores, median, minimum, mean, pass_rate, variance, distribution, stage_deltas, stage_means = _diagnostics(plan, ordered_runs)
    if invalid_ids:
        status = "invalid"
        campaign_score = None
        first_failure = next(run.summary.first_failure or f"invalid-run:{run.member.run_id}" for run in ordered_runs if run is not None and run.summary.status == "invalid")
    elif missing_ids:
        status = "incomplete"
        campaign_score = None
        first_failure = f"missing-required-run:{missing_ids[0]}"
    else:
        status = "complete"
        assert median is not None and minimum is not None and mean is not None
        campaign_score = round(Fraction(1, 2) * median + Fraction(3, 10) * minimum + Fraction(1, 5) * mean)
        first_failure = next((run.summary.first_failure for run in ordered_runs if run is not None and run.summary.first_failure is not None), None)
    variants = tuple((member.variant_sha256, member.seed, member.schedule_sha256) for member in plan.members)
    compatibility = (plan.profile_sha256, plan.host_sha256, plan.contract_sha256, plan.registry_sha256, variants)
    return CampaignSummary(plan.campaign_id, status, campaign_score, scores, median, minimum, mean, pass_rate, variance, distribution, stage_deltas, stage_means, first_failure, compatibility)


def compare_campaigns(left: CampaignSummary, right: CampaignSummary) -> CampaignComparison:
    """Compare only campaigns sharing the same frozen execution identity."""
    if left.compatibility_identity != right.compatibility_identity:
        return CampaignComparison("incompatible", "profile/host/contract/registry/variant identity mismatch", None, MappingProxyType({}))
    if left.campaign_score is None or right.campaign_score is None:
        return CampaignComparison("unavailable", "one or both campaign scores are null", None, MappingProxyType({}))
    stages = set(left.stage_means) | set(right.stage_means)
    if set(left.stage_means) != set(right.stage_means):
        return CampaignComparison("incompatible", "stage identity mismatch", None, MappingProxyType({}))
    deltas = {stage: right.stage_means[stage] - left.stage_means[stage] for stage in sorted(stages)}
    return CampaignComparison("compatible", None, right.campaign_score - left.campaign_score, MappingProxyType(deltas))
