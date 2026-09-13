import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path("scripts/document_flow/schemas")
SHA = "a" * 64
STAGES = ("intake", "analyze", "specify", "decompose", "declare", "implement", "verify")


def evidence(key="objects/result.json"):
    return {"key": key, "sha256": SHA, "media_type": "application/json", "byte_length": 12, "producer_event_id": "event-1"}


def identity(stage=None):
    value = {
        "campaign_id": "campaign-1", "run_id": "run-1", "case_id": "J03-document-flow",
        "variant_id": "variant-1", "framework_commit": SHA, "wheel_sha256": SHA,
        "lock_sha256": SHA, "registry_sha256": SHA, "agent_name": "little-coder",
        "agent_version": "1.19.0", "agent_config_sha256": SHA, "model_id": "laguna-xs-2.1",
        "provider_id": "provider-1", "endpoint_attestation_ref": evidence("objects/endpoint.json"),
        "tokenizer_fingerprint": SHA,
    }
    if stage is not None:
        value["stage_id"] = stage
    return value


def load_validator(name):
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (
        ROOT / "evidence-ref.schema.json", ROOT / "event.schema.json", ROOT / name
    )]
    registry = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    return Draft202012Validator(schemas[-1], registry=registry, format_checker=FormatChecker())


def stage_report(stage, status="passed"):
    reached = status != "not_reached"
    return {
        "schema_version": 1, "report_hash": SHA, "predecessor_report_hash": None,
        "identity": identity(stage), "status": status,
        "lifecycle": {"start_state": stage if reached else None, "end_state": "complete" if reached else None, "next_stage": None},
        "visit_ids": ["visit-1"] if reached else [],
        "task_attempts": [{"task_id": "task-1", "attempt": 1, "visit_ids": ["visit-1"], "status": "passed", "evidence_refs": [evidence("objects/task-attempt.json")]}] if reached else [],
        "snapshot_refs": [evidence("objects/snapshot.json")] if reached else [],
        "attestation_refs": [evidence("objects/attestation.json")], "event_refs": [evidence("objects/events.jsonl")] if reached else [],
        "checks": [{"check_id": "IN.C01", "status": "pass", "awarded_points": 1, "evidence_refs": [evidence()], "failure_reason": None}] if reached else [],
        "measurements": {
            "worker_calls": 1 if reached else 0, "input_tokens": 10 if reached else None,
            "output_tokens": 2 if reached else None, "framework_tokens": 1 if reached else None,
            "files_read": 1 if reached else 0, "files_written": 0, "files_reread": 0,
            "tool_calls": 1 if reached else 0, "tool_failures": 0, "timeouts": 0,
            "rejected_actions": 0, "gate_retries": 0, "evidence_retries": 0,
            "coverage_retries": 0, "compaction_count": 0, "context_peak_tokens": 13 if reached else None,
            "wall_time_ms": 1 if reached else None, "provenance_refs": [evidence("objects/measurements.json")] if reached else [],
        },
        "totals": {"correctness": 1 if reached else 0, "discipline": 0, "efficiency": 0, "score": 1 if reached else 0},
        "hard_failures": [], "test_result_refs": [evidence("objects/tests.json")] if reached else [],
    }


def system_report(status="passed"):
    invalid = status == "invalid"
    reached = status != "not_reached"
    failure_class = None
    if status == "failed": failure_class = "product-functional-failure"
    if invalid: failure_class = "infrastructure-invalid"
    return {
        "schema_version": 1, "report_hash": SHA, "identity": identity(), "status": status,
        "failure_class": failure_class, "snapshot_ref": evidence("objects/system-snapshot.json") if reached else None,
        "attestation_refs": [evidence("objects/attestation.json")], "event_refs": [evidence("objects/events.jsonl")] if reached else [],
        "scenarios": [{"check_id": "SYS.F01", "status": "pass" if status == "passed" else "fail", "build_id": "build-1", "fault_id": None, "load_id": None, "evidence_refs": [evidence()], "failure_reason": None if status == "passed" else "observable failure"}] if reached and not invalid else [],
        "measurements": {"sql_statements": 1 if reached and not invalid else None, "completion_ms": 1 if reached and not invalid else None, "heap_peak_bytes": 1 if reached and not invalid else None, "provenance_refs": [evidence("objects/system-measurements.json")] if reached and not invalid else []},
        "totals": None if invalid or not reached else {"functional": 1, "resilience": 0, "compatibility": 0, "efficiency": 0, "score": 1},
        "hard_failures": [] if status == "passed" else [failure_class or "not-reached"],
        "test_result_refs": [evidence("objects/system-tests.json")] if reached and not invalid else [],
    }


@pytest.mark.parametrize("stage", STAGES)
def test_all_seven_stage_variants_validate(stage):
    load_validator("stage.schema.json").validate(stage_report(stage))


@pytest.mark.parametrize("status", ["passed", "failed", "not_reached", "invalid"])
def test_system_outcome_variants_validate(status):
    load_validator("system.schema.json").validate(system_report(status))


def test_successful_stage_without_measurements_is_rejected():
    value = stage_report("intake")
    del value["measurements"]
    assert list(load_validator("stage.schema.json").iter_errors(value))


def test_not_reached_stage_cannot_claim_task_attempt():
    value = stage_report("verify", "not_reached")
    value["task_attempts"] = [{"task_id": "task-1", "attempt": 1, "visit_ids": ["visit-1"], "status": "passed", "evidence_refs": [evidence()]}]
    assert list(load_validator("stage.schema.json").iter_errors(value))


@pytest.mark.parametrize("mutation", ["missing_identity", "bad_stage", "score_high", "nested_extra"])
def test_bad_stage_reports_are_rejected(mutation):
    value = stage_report("intake")
    if mutation == "missing_identity": del value["identity"]["framework_commit"]
    if mutation == "bad_stage": value["identity"]["stage_id"] = "review"
    if mutation == "score_high": value["totals"]["score"] = 1001
    if mutation == "nested_extra": value["measurements"]["estimated_tokens"] = 1
    assert list(load_validator("stage.schema.json").iter_errors(value))


def test_invalid_system_cannot_masquerade_as_product_failure_or_have_score():
    value = system_report("invalid")
    value["failure_class"] = "product-functional-failure"
    value["totals"] = {"functional": 0, "resilience": 0, "compatibility": 0, "efficiency": 0, "score": 1}
    assert list(load_validator("system.schema.json").iter_errors(value))


def test_passed_system_requires_measurement_and_test_provenance():
    value = system_report("passed")
    value["measurements"]["provenance_refs"] = []
    value["test_result_refs"] = []
    assert list(load_validator("system.schema.json").iter_errors(value))
