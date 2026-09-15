"""Tests for worker model call and compaction telemetry (J03-502)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.worker.telemetry import record_compaction, record_model_call


SCHEMAS_DIR = Path("scripts/document_flow/schemas")


def get_event_validator():
    ev_schema = json.loads((SCHEMAS_DIR / "event.schema.json").read_text(encoding="utf-8"))
    ref_schema = json.loads((SCHEMAS_DIR / "evidence-ref.schema.json").read_text(encoding="utf-8"))
    
    registry = Registry().with_resources([
        (ev_schema["$id"], Resource.from_contents(ev_schema)),
        (ref_schema["$id"], Resource.from_contents(ref_schema)),
    ])
    return Draft202012Validator(ev_schema, registry=registry)


def test_record_model_call_telemetry_valid(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    validator = get_event_validator()
    
    req_dict = {"messages": [{"role": "user", "content": "analyze intake"}]}
    resp_dict = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
    usage = {
        "input_tokens": 1500,
        "output_tokens": 300,
        "usage_source": "provider",
    }
    
    event = record_model_call(
        store,
        event_id="ev-call-1",
        run_id="run-1",
        session_id="sess-1",
        visit_id="vis-1",
        stage_id="intake",
        profile_id="profile-poolside",
        request_data=req_dict,
        response_data=resp_dict,
        usage=usage,
        framework_tokens=50,
        thinking_retained=True,
    )
    
    validator.validate(event)
    assert event["kind"] == "model_call"
    assert event["payload"]["input_tokens"] == 1500
    assert event["payload"]["output_tokens"] == 300
    assert event["payload"]["thinking_retained"] is True
    assert event["payload"]["usage_source"] == "provider"


def test_record_model_call_unmeasured(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    validator = get_event_validator()
    
    event = record_model_call(
        store,
        event_id="ev-call-2",
        run_id="run-1",
        session_id="sess-1",
        visit_id="vis-1",
        stage_id="specify",
        profile_id="profile-poolside",
        request_data=b'{"prompt": "raw"}',
        response_data=None,
        usage=None,
    )
    
    validator.validate(event)
    assert event["payload"]["input_tokens"] is None
    assert event["payload"]["output_tokens"] is None
    assert event["payload"]["usage_source"] == "unmeasured"


def test_record_compaction_telemetry_valid(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    validator = get_event_validator()
    
    event = record_compaction(
        store,
        event_id="ev-comp-1",
        run_id="run-1",
        session_id="sess-1",
        visit_id="vis-1",
        stage_id="implement",
        before_tokens=65000,
        after_tokens=20000,
        cause="compaction_threshold",
        retained_state=True,
        lost_state_checks=[],
    )
    
    validator.validate(event)
    assert event["kind"] == "compaction"
    assert event["payload"]["before_tokens"] == 65000
    assert event["payload"]["after_tokens"] == 20000
    assert event["payload"]["retained_state"] is True
