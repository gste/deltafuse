import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path("scripts/document_flow/schemas")
SHA = "b" * 64


def evidence(key="objects/report.json"):
    return {"key": key, "sha256": SHA, "media_type": "application/json", "byte_length": 12, "producer_event_id": "event-1"}


def validator(name):
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "evidence-ref.schema.json", ROOT / name)]
    registry = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    return Draft202012Validator(schemas[-1], registry=registry)


def run_report(status="passed", raw=10000, score=10000, verdict="release_pass", ceilings=None):
    invalid = status == "invalid"
    return {
        "schema_version": 1, "report_hash": SHA, "semantic_result_hash": SHA,
        "identity": {
            "campaign_id": "campaign-1", "run_id": "run-1", "case_id": "J03-document-flow", "variant_id": "variant-1",
            "session_id": "session-1", "sandbox_id": "sandbox-1", "profile_sha256": SHA, "contract_sha256": SHA,
            "registry_sha256": SHA, "host_profile_sha256": SHA,
        },
        "status": status, "raw_score": None if invalid else raw, "applied_ceilings": [] if invalid else (ceilings or []),
        "final_score": None if invalid else score, "release_verdict": "invalid" if invalid else verdict,
        "stage_report_refs": [evidence(f"objects/stage-{number}.json") for number in range(1, 8)] if not invalid else [],
        "system_report_ref": evidence("objects/system.json") if not invalid else None,
        "attestation_refs": [evidence("objects/attestation.json")],
        "hard_failures": ["provenance-invalid"] if invalid else ([] if status == "passed" else ["process-failure"]),
        "failure_classes": ["provenance-invalid"] if invalid else ([] if status == "passed" else ["process-failure"]),
    }


def member(number, status="valid_pass", score=10000):
    absent = status in {"missing", "not_run"}
    invalid = status == "invalid"
    return {
        "run_id": f"run-{number}", "session_id": f"session-{number}", "sandbox_id": f"sandbox-{number}",
        "seed": number, "schedule_sha256": SHA, "status": status,
        "report_ref": None if absent else evidence(f"objects/run-{number}.json"),
        "score": None if absent or invalid else score,
        "first_failure": None if status == "valid_pass" else status,
    }


def campaign_report(status="complete", members=None, score=10000):
    members = members or [member(1), member(2), member(3)]
    return {
        "schema_version": 1, "report_hash": SHA, "semantic_result_hash": SHA,
        "identity": {"campaign_id": "campaign-1", "case_id": "J03-document-flow", "profile_sha256": SHA, "contract_sha256": SHA, "registry_sha256": SHA, "host_profile_sha256": SHA, "generator_sha256": SHA, "membership_sha256": SHA},
        "status": status, "required_run_count": len(members), "members": members,
        "campaign_score": score if status == "complete" else None,
        "diagnostics": {
            "run_scores": [item["score"] for item in members], "median": score if status == "complete" else None,
            "minimum": score if status == "complete" else None, "mean": score if status == "complete" else None,
            "pass_rate_numerator": sum(item["status"] == "valid_pass" for item in members), "pass_rate_denominator": len(members),
            "population_variance": 0 if status == "complete" else None,
            "first_failure_distribution": [], "stage_deltas": [],
        },
        "member_report_refs": [item["report_ref"] for item in members if item["report_ref"] is not None],
        "failure_reasons": [] if status == "complete" else ["required-member-unavailable"],
    }


@pytest.mark.parametrize("fixture", [
    run_report(),
    run_report("failed", raw=0, score=1, verdict="fail"),
    run_report("failed", raw=8000, score=4999, verdict="fail", ceilings=[{"kind": "incomplete_lifecycle", "limit": 4999}]),
    run_report("invalid"),
])
def test_run_boundary_variants_validate(fixture):
    validator("run.schema.json").validate(fixture)


def test_incomplete_campaign_preserves_missing_and_not_run_members():
    fixture = campaign_report("incomplete", [member(1), member(2, "missing"), member(3, "not_run")], None)
    validator("campaign.schema.json").validate(fixture)
    assert fixture["diagnostics"]["run_scores"] == [10000, None, None]


def test_invalid_campaign_preserves_invalid_member_without_numeric_score():
    fixture = campaign_report("invalid", [member(1), member(2, "invalid"), member(3)], None)
    validator("campaign.schema.json").validate(fixture)
    assert fixture["members"][1]["report_ref"] is not None
    assert fixture["members"][1]["score"] is None


def test_invalid_run_cannot_carry_numeric_score():
    fixture = run_report("invalid")
    fixture["final_score"] = 10000
    assert list(validator("run.schema.json").iter_errors(fixture))


def test_numeric_score_cannot_have_null_verdict():
    fixture = run_report()
    fixture["release_verdict"] = None
    assert list(validator("run.schema.json").iter_errors(fixture))


def test_duplicate_campaign_members_are_rejected():
    first = member(1)
    fixture = campaign_report(members=[first, copy.deepcopy(first), member(3)])
    assert list(validator("campaign.schema.json").iter_errors(fixture))


def test_fewer_than_three_required_runs_is_rejected():
    fixture = campaign_report(members=[member(1), member(2)])
    assert list(validator("campaign.schema.json").iter_errors(fixture))


def test_executed_member_without_report_reference_is_rejected():
    fixture = campaign_report()
    fixture["members"][0]["report_ref"] = None
    assert list(validator("campaign.schema.json").iter_errors(fixture))


def test_missing_member_cannot_be_recorded_as_zero_score():
    fixture = campaign_report("incomplete", [member(1), member(2, "missing"), member(3)], None)
    fixture["members"][1]["score"] = 0
    assert list(validator("campaign.schema.json").iter_errors(fixture))


def test_closed_nested_objects_and_score_bounds():
    fixture = run_report()
    fixture["identity"]["extra"] = True
    fixture["raw_score"] = 10001
    assert list(validator("run.schema.json").iter_errors(fixture))
