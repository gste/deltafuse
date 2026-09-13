import copy
import json
from pathlib import Path

import pytest

from scripts.document_flow.validation import ValidationError, decode_validate


SHA = "a" * 64


def ref(name="objects/evidence.json"):
    return {
        "key": name,
        "sha256": SHA,
        "media_type": "application/json",
        "byte_length": 12,
        "producer_event_id": "event-0001",
    }


def event(kind, payload):
    return {
        "schema_version": 1,
        "event_id": "event-0001",
        "sequence": 1,
        "previous_hash": None,
        "event_hash": SHA,
        "monotonic_ns": 1,
        "diagnostic_timestamp": "2026-09-13T00:00:00Z",
        "run_id": "run-1",
        "session_id": "session-1",
        "call_id": "call-1" if kind == "model_call" else None,
        "visit_id": "visit-1",
        "task_id": "task-1",
        "stage_id": "intake",
        "kind": kind,
        "host_source": {"host_id": "host-1", "collector_id": "judge-1"},
        "payload": payload,
    }


CASES = {
    "core": {"action": "next", "next_stage": "analyze", "halted": False, "evidence_refs": [ref()]},
    "model_call": {
        "input_tokens": 0, "output_tokens": None, "framework_tokens": 3,
        "reserved_output_tokens": 100, "tokenizer_fingerprint": SHA,
        "template_fingerprint": SHA, "usage_source": "provider",
        "request_sha256": SHA, "response_sha256": None,
        "thinking_retained": True, "profile_id": "profile-1",
    },
    "file_access": {
        "canonical_path": "docs/changes/X/intake.md", "file_sha256": SHA,
        "range": {"start": 1, "end": 3}, "operation": "read",
        "origin": "tool", "repeat_relation": None, "allowed": True,
        "tool_id": "read", "call_id": "call-1", "process_id": None,
    },
    "command": {
        "argv": ["python", "-m", "pytest"], "cwd": ".",
        "environment_inventory_sha256": SHA, "started_monotonic_ns": 1,
        "finished_monotonic_ns": 2, "timed_out": False, "exit_code": 0,
        "stdout_ref": ref("objects/stdout"), "stderr_ref": None,
        "process_id": "process-1", "executor_id": "executor-1",
        "target_snapshot_id": "snapshot-1", "operation_instance_id": "op-1",
    },
    "compaction": {
        "before_session_ref": "session-before", "after_session_ref": "session-after",
        "before_request_ref": "request-before", "after_request_ref": "request-after",
        "cause": "context_limit", "before_tokens": 100, "after_tokens": None,
        "retained_state": True, "lost_state_checks": [],
    },
    "boundary": {
        "boundary_type": "command", "phase": "enter",
        "envelope_sha256": SHA, "allowed": True, "reason": None,
    },
    "human_gate": {
        "halted": True, "gate_type": "spec", "chosen_option": None,
        "operator_id": None, "receipt_ref": None, "resume_state": "awaiting_operator",
    },
}


@pytest.mark.parametrize("kind,payload", CASES.items())
def test_all_event_variants_validate(kind, payload):
    decoded = decode_validate("event", json.dumps(event(kind, payload)).encode())
    assert decoded["kind"] == kind
    if kind == "model_call":
        assert decoded["payload"]["input_tokens"] == 0
        assert decoded["payload"]["output_tokens"] is None


@pytest.mark.parametrize("mutation", ["unknown_nested", "bool_count", "nan", "unsupported_kind", "broken_ref"])
def test_invalid_events_fail_closed(mutation):
    value = event("model_call", copy.deepcopy(CASES["model_call"]))
    if mutation == "unknown_nested": value["payload"]["surprise"] = True
    if mutation == "bool_count": value["payload"]["input_tokens"] = True
    if mutation == "nan": value["monotonic_ns"] = float("nan")
    if mutation == "unsupported_kind": value["kind"] = "invented"
    if mutation == "broken_ref":
        value = event("core", copy.deepcopy(CASES["core"]))
        value["payload"]["evidence_refs"][0]["sha256"] = "broken"
    with pytest.raises(ValidationError):
        decode_validate("event", json.dumps(value).encode())


def test_duplicate_json_keys_are_rejected():
    raw = b'{"schema_version":1,"schema_version":1}'
    with pytest.raises(ValidationError, match="duplicate JSON key"):
        decode_validate("event", raw)


def test_unknown_kind_and_remote_schema_name_never_resolve():
    with pytest.raises(ValidationError, match="unknown schema kind"):
        decode_validate("https://example.invalid/event.schema.json", b"{}")


def test_bad_diagnostic_timestamp_is_rejected():
    value = event("core", copy.deepcopy(CASES["core"]))
    value["diagnostic_timestamp"] = "not-a-timestamp"
    with pytest.raises(ValidationError):
        decode_validate("event", json.dumps(value).encode())


def test_evidence_ref_rejects_parent_escape_and_bool_length():
    value = ref("../secret")
    value["byte_length"] = True
    with pytest.raises(ValidationError):
        decode_validate("evidence-ref", json.dumps(value).encode())
