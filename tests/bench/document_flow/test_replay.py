"""Tests for re-evaluating runs from disk artifacts (J03-408)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import json

import pytest

from scripts.document_flow.canonical import canonical_bytes, with_self_hash
from scripts.document_flow.evaluate import CheckFact, StageFactors
from scripts.document_flow.registry import load_registry
from scripts.document_flow.replay import ReplayError, reevaluate_run_from_store
from scripts.document_flow.snapshots import to_evidence_ref_dict
from scripts.document_flow.store import EvidenceStore


REGISTRY = load_registry(Path("scripts/document_flow/contracts/checks.json"))


def make_full_store(tmp_path: Path, run_id: str = "run-1") -> EvidenceStore:
    store = EvidenceStore.create(tmp_path / run_id, run_id, f"root-{run_id}")
    
    # Store dummy attestation
    att_ref = store.put(b"attestation-content", "text/plain", "ev-att-1")
    att_dict = to_evidence_ref_dict(att_ref)
    
    identity = {
        "campaign_id": "camp-1",
        "run_id": run_id,
        "case_id": "J03-document-flow",
        "variant_id": "var-1",
        "session_id": "sess-1",
        "sandbox_id": "sand-1",
        "profile_sha256": "0" * 64,
        "contract_sha256": "0" * 64,
        "registry_sha256": "0" * 64,
        "host_profile_sha256": "0" * 64,
        "endpoint_attestation_ref": att_dict,
    }
    
    # Create all checks across all 7 stages
    stage_checks = {stage: [] for stage in REGISTRY.stages}
    system_checks = []
    
    for chk in REGISTRY.checks:
        c_dict = {
            "check_id": chk.id,
            "status": "pass",
            "awarded_points": chk.points,
            "evidence_refs": [att_dict],
            "failure_reason": None,
        }
        if chk.category == "system":
            system_checks.append(c_dict)
        else:
            stage_pfx = chk.id.split(".", 1)[0]
            for sname in REGISTRY.stages:
                from scripts.document_flow.evaluate import STAGE_PREFIX
                if STAGE_PREFIX.get(stage_pfx) == sname:
                    stage_checks[sname].append(c_dict)
                    break

    # Finalize stage reports
    prev_hash = None
    for stage_name in REGISTRY.stages:
        stg_identity = dict(identity)
        stg_identity["stage_id"] = stage_name
        doc = {
            "schema_version": 1,
            "report_hash": "0" * 64,
            "predecessor_report_hash": prev_hash,
            "identity": stg_identity,
            "status": "passed",
            "lifecycle": {
                "start_state": stage_name,
                "end_state": "complete",
                "next_stage": None,
            },
            "visit_ids": [f"visit-{stage_name}-1"],
            "task_attempts": [],
            "snapshot_refs": [],
            "attestation_refs": [att_dict],
            "event_refs": [],
            "checks": stage_checks[stage_name],
            "measurements": {
                "worker_calls": 1,
                "context_peak_tokens": 0,
                "files_read": 5,
                "files_reread": 0,
                "tool_calls": 5,
                "tool_failures": 0,
                "timeouts": 0,
                "rejected_actions": 0,
                "gate_retries": 0,
                "evidence_retries": 0,
                "coverage_retries": 0,
                "provenance_refs": [att_dict],
            },
            "totals": {
                "correctness": sum(c["awarded_points"] for c in stage_checks[stage_name] if ".C" in c["check_id"]),
                "discipline": sum(c["awarded_points"] for c in stage_checks[stage_name] if ".D" in c["check_id"]),
                "efficiency": 150,
                "score": 1000,
            },
            "hard_failures": [],
            "test_result_refs": [],
        }
        finalized = store.finalize_json(f"stages/{stage_name}.json", doc)
        prev_hash = finalized["report_hash"]

    # Finalize system report
    sys_doc = {
        "schema_version": 1,
        "report_hash": "0" * 64,
        "status": "passed",
        "checks": system_checks,
    }
    store.finalize_json("reports/system.json", sys_doc)

    return store


def test_reevaluate_run_perfect_pass(tmp_path):
    store = make_full_store(tmp_path, "run-pass")
    replay = reevaluate_run_from_store(store, REGISTRY)
    
    assert replay.re_evaluated is True
    assert replay.summary.status == "passed"
    assert replay.summary.raw_score == 10000
    assert replay.summary.final_score == 10000
    assert replay.summary.release_verdict == "release_pass"
    assert replay.summary.first_failure is None


def test_reevaluate_run_detects_tampered_self_hash(tmp_path):
    store = make_full_store(tmp_path, "run-tamper")
    # Mutate a stage report without updating self hash
    stage_path = store.root / "stages" / "intake.json"
    doc = json.loads(stage_path.read_text(encoding="utf-8"))
    doc["totals"]["score"] = 9999
    stage_path.write_bytes(canonical_bytes(doc))
    
    with pytest.raises(ReplayError, match="stage report self-hash mismatch"):
        reevaluate_run_from_store(store, REGISTRY)


def test_reevaluate_run_detects_forged_totals_in_stored_run_json(tmp_path):
    store = make_full_store(tmp_path, "run-forged-run-json")
    
    # Write a forged run.json that claims a higher score than reality
    forged_run = with_self_hash({
        "status": "passed",
        "raw_score": 10000,
        "final_score": 10000,
        "release_verdict": "release_pass",
    }, "report_hash")
    (store.root / "reports" / "run.json").write_bytes(canonical_bytes(forged_run))
    
    # Mutate all checks in all stages to fail
    for stage_name in REGISTRY.stages:
        stage_path = store.root / "stages" / f"{stage_name}.json"
        doc = json.loads(stage_path.read_text(encoding="utf-8"))
        for c in doc["checks"]:
            c["status"] = "fail"
        doc = with_self_hash(doc, "report_hash")
        stage_path.write_bytes(canonical_bytes(doc))
    
    # Mutate system checks to fail
    sys_path = store.root / "reports" / "system.json"
    sdoc = json.loads(sys_path.read_text(encoding="utf-8"))
    for c in sdoc["checks"]:
        c["status"] = "fail"
    sdoc = with_self_hash(sdoc, "report_hash")
    sys_path.write_bytes(canonical_bytes(sdoc))
    
    with pytest.raises(ReplayError, match="stored status mismatch"):
        reevaluate_run_from_store(store, REGISTRY)
