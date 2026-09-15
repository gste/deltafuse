"""Capture and telemetry accounting for model calls and compaction (J03-502)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from scripts.document_flow.canonical import canonical_bytes, content_hash
from scripts.document_flow.store import EvidenceRef, EvidenceStore


RESERVATION_CAP = 32768


@dataclass(frozen=True)
class ModelCallRecord:
    call_id: str
    profile_id: str
    input_tokens: int | None
    output_tokens: int | None
    framework_tokens: int | None
    reserved_output_tokens: int | None
    usage_source: str  # 'provider' | 'tokenizer' | 'unmeasured'
    request_sha256: str
    response_sha256: str | None
    tokenizer_fingerprint: str | None
    template_fingerprint: str | None
    thinking_retained: bool | None


@dataclass(frozen=True)
class CompactionRecord:
    before_session_ref: str
    after_session_ref: str
    before_request_ref: str
    after_request_ref: str
    cause: str
    before_tokens: int | None
    after_tokens: int | None
    retained_state: bool
    lost_state_checks: list[str]


def record_model_call(
    store: EvidenceStore,
    *,
    event_id: str,
    run_id: str,
    session_id: str,
    visit_id: str,
    stage_id: str,
    profile_id: str,
    request_data: bytes | dict[str, Any],
    response_data: bytes | dict[str, Any] | None,
    usage: Mapping[str, Any] | None,
    framework_tokens: int | None = None,
    reserved_tokens: int = RESERVATION_CAP,
    tokenizer_fp: str | None = None,
    template_fp: str | None = None,
    thinking_retained: bool | None = None,
) -> dict[str, Any]:
    """Record outbound model request/response telemetry into store."""
    if isinstance(request_data, dict):
        req_bytes = canonical_bytes(request_data)
    else:
        req_bytes = request_data
    
    req_sha = hashlib.sha256(req_bytes).hexdigest()
    store.put(req_bytes, "application/json", event_id)

    if response_data is not None:
        if isinstance(response_data, dict):
            resp_bytes = canonical_bytes(response_data)
        else:
            resp_bytes = response_data
        resp_sha = hashlib.sha256(resp_bytes).hexdigest()
        store.put(resp_bytes, "application/json", event_id)
    else:
        resp_sha = None

    if usage is not None:
        in_tok = usage.get("input_tokens") or usage.get("prompt_tokens")
        out_tok = usage.get("output_tokens") or usage.get("completion_tokens")
        usage_source = usage.get("usage_source", "provider")
    else:
        in_tok = None
        out_tok = None
        usage_source = "unmeasured"

    payload = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "framework_tokens": framework_tokens,
        "reserved_output_tokens": reserved_tokens,
        "tokenizer_fingerprint": tokenizer_fp,
        "template_fingerprint": template_fp,
        "usage_source": usage_source,
        "request_sha256": req_sha,
        "response_sha256": resp_sha,
        "thinking_retained": thinking_retained,
        "profile_id": profile_id,
    }

    event = {
        "schema_version": 1,
        "event_id": event_id,
        "monotonic_ns": time.monotonic_ns(),
        "diagnostic_timestamp": "2026-09-15T19:00:00Z",
        "run_id": run_id,
        "session_id": session_id,
        "call_id": event_id,
        "visit_id": visit_id,
        "task_id": None,
        "stage_id": stage_id,
        "kind": "model_call",
        "host_source": {
            "host_id": "host-j03",
            "collector_id": "telemetry-collector",
        },
        "payload": payload,
    }

    return store.append_event(event)


def record_compaction(
    store: EvidenceStore,
    *,
    event_id: str,
    run_id: str,
    session_id: str,
    visit_id: str,
    stage_id: str,
    before_tokens: int | None,
    after_tokens: int | None,
    cause: str = "context_cap_reached",
    retained_state: bool = True,
    lost_state_checks: list[str] | None = None,
) -> dict[str, Any]:
    """Record compaction event with before/after state provenance."""
    payload = {
        "before_session_ref": f"sess-pre-{event_id}",
        "after_session_ref": f"sess-post-{event_id}",
        "before_request_ref": f"req-pre-{event_id}",
        "after_request_ref": f"req-post-{event_id}",
        "cause": cause,
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
        "retained_state": retained_state,
        "lost_state_checks": lost_state_checks or [],
    }

    event = {
        "schema_version": 1,
        "event_id": event_id,
        "monotonic_ns": time.monotonic_ns(),
        "diagnostic_timestamp": "2026-09-15T19:00:00Z",
        "run_id": run_id,
        "session_id": session_id,
        "call_id": None,
        "visit_id": visit_id,
        "task_id": None,
        "stage_id": stage_id,
        "kind": "compaction",
        "host_source": {
            "host_id": "host-j03",
            "collector_id": "telemetry-collector",
        },
        "payload": payload,
    }

    return store.append_event(event)
