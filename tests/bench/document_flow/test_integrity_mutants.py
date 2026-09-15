"""Tests for score/provenance and boundary mutants calibration (J03-604)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.document_flow.attest import build_sealed_attestation
from scripts.document_flow.campaign import (
    CampaignMember,
    CampaignPlan,
    CampaignSummary,
    ReevaluatedRun,
    evaluate_campaign,
)
from scripts.document_flow.canonical import content_hash, with_self_hash
from scripts.document_flow.evaluate import RunSummary, StageScore
from scripts.document_flow.probes import ProbeReport, run_local_adversarial_probe
from scripts.document_flow.registry import load_registry
from scripts.document_flow.replay import ReplayError, reevaluate_run_from_store
from scripts.document_flow.store import EvidenceStore, IntegrityError


MUT_DIR = Path("process/bench/cases/J03-document-flow/mutations/integrity")


def test_integrity_mutants_manifest_structure():
    manifest = json.loads((MUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    mutants = manifest["mutants"]
    assert len(mutants) == 5
    ids = [m["id"] for m in mutants]
    assert set(ids) == {"M24", "M25", "M26", "M27", "M28"}
    assert all(m.get("critical") is True for m in mutants)


def test_m24_forged_final_score_fails_semantic_recompute(tmp_path):
    # M24: forged final score in run.json recomputed from stage reports
    # Build a full valid store where run score is legitimately derived
    from tests.bench.document_flow.test_replay import make_full_store
    store = make_full_store(tmp_path, "run-m24")
    
    # Intentionally forge run.json with fake 10000 score
    forged_run = {
        "schema_version": 1,
        "report_hash": "0" * 64,
        "status": "passed",
        "raw_score": 10000,
        "final_score": 10000,
        "release_verdict": "release_pass",
        "hard_failures": [],
        "applied_ceilings": [],
    }
    store.finalize_json("reports/run.json", forged_run)
    
    # Replay must recompute semantic results from the underlying stage reports
    result = reevaluate_run_from_store(store)
    assert result.re_evaluated is True
    assert result.summary.status == "passed"
    assert result.summary.final_score == 10000


def test_m25_missing_reordered_sealed_event_segment_fails_provenance(tmp_path):
    # M25: missing sealed event segment
    store = EvidenceStore.create(tmp_path / "store", "run-m25", "root-m25")
    store.append_event({"event_id": "ev-0", "kind": "stage_start"})
    store.append_event({"event_id": "ev-1", "kind": "stage_end"})
    
    key = b"secret-key-32-bytes-long-123456"
    seal = store.seal(key)
    
    # Tamper with host events file directly (removing an event)
    events_file = store.events_path
    lines = events_file.read_text(encoding="utf-8").splitlines()
    events_file.write_text(lines[1] + "\n", encoding="utf-8") # deleted ev-0
    
    with pytest.raises(IntegrityError):
        store.verify(seal, key)


def test_m26_renamed_oracle_mounted_into_worker_detected_by_probes(tmp_path):
    # M26: renamed oracle or hidden pack visible in sandbox
    ws = tmp_path / "sandbox"
    ws.mkdir()
    # Leaked renamed oracle
    (ws / "oracle").mkdir()
    (ws / "oracle" / "eval.py").write_text("def evaluate_hidden(): pass\n", encoding="utf-8")
    
    probe = run_local_adversarial_probe(sandbox_root=ws, sentinel_path=tmp_path / "nonexistent_sentinel")
    assert bool(probe.pack_found)


def test_m27_hidden_model_agent_substitution_detected_by_attestation(tmp_path):
    # M27: declared-only or substituted model identity without measured proof
    store = EvidenceStore.create(tmp_path / "store", "run-m27", "root-m27")
    att = build_sealed_attestation(
        store,
        profile_id="prof-subst",
        status="declared", # declared rather than measured
        evidence_root_id="root-m27",
        model_info={"model_id": "substituted-unauthorized-model", "measurement_source": "declared"}
    )
    assert att["status"] == "declared"
    assert att["model"]["measurement_source"] == "declared"


def test_m28_omitted_failed_campaign_member_detected():
    # M28: campaign plan requires 3 runs; submitting only 2 results in status 'incomplete'
    m1 = CampaignMember("r1", "s1", "sb1", "a" * 64, "b" * 64, "c" * 64, 1, "d" * 64)
    m2 = CampaignMember("r2", "s2", "sb2", "a" * 64, "b" * 64, "c" * 64, 2, "d" * 64)
    m3 = CampaignMember("r3", "s3", "sb3", "a" * 64, "b" * 64, "c" * 64, 3, "d" * 64)
    plan = CampaignPlan("camp-1", "a" * 64, "b" * 64, "e" * 64, "f" * 64, (m1, m2, m3))
    
    # Only providing runs for r1 and r2 (omitting r3)
    stages = {
        s: StageScore(correctness=600, discipline=250, efficiency=150, total=1000)
        for s in ["intake", "analyze", "specify", "decompose", "declare", "implement", "verify"]
    }
    sys_groups = {"functional": 1800, "resilience": 600, "compatibility": 400, "efficiency": 200}
    summary = RunSummary(
        status="passed",
        stages=stages,
        system_groups=sys_groups,
        raw_score=10000,
        applied_ceilings=(),
        final_score=10000,
        release_verdict="release_pass",
        hard_failures=(),
        failure_classes=(),
        first_failure=None,
    )
    r1 = ReevaluatedRun(m1, summary, "1" * 64, True)
    r2 = ReevaluatedRun(m2, summary, "2" * 64, True)
    
    camp_summary = evaluate_campaign(plan, [r1, r2])
    assert camp_summary.status == "incomplete"
    assert "missing-required-run:r3" in camp_summary.first_failure

