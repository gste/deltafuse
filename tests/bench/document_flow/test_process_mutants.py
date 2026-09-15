"""Tests for process-artifact mutant calibration (J03-601)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.document_flow.oracles.analyze import evaluate_analyze_stage
from scripts.document_flow.oracles.declare import evaluate_declare_stage
from scripts.document_flow.oracles.decompose import evaluate_decompose_stage
from scripts.document_flow.oracles.implement import evaluate_implement_stage
from scripts.document_flow.oracles.intake import evaluate_intake_stage
from scripts.document_flow.oracles.specify import evaluate_specify_stage
from scripts.document_flow.snapshots import SnapshotData, take_stage_snapshot
from scripts.document_flow.store import EvidenceStore


MUT_DIR = Path("process/bench/cases/J03-document-flow/mutations/process")


def test_process_mutants_manifest_structure():
    manifest = json.loads((MUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    mutants = manifest["mutants"]
    assert len(mutants) == 10
    ids = [m["id"] for m in mutants]
    assert set(ids) == {"M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M21", "M23"}


def test_m01_meaningless_spec_killed_by_specify_oracle(tmp_path):
    # M01: tautological/meaningless spec
    store = EvidenceStore.create(tmp_path / "store", "run-m01", "root-m01")
    ws = tmp_path / "product"
    ws.mkdir()
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: specifying\n", encoding="utf-8")
    (ch_dir / "specs.md").write_text("# Spec\n<!-- witness: vacuous -->\n", encoding="utf-8")
    
    snapshot, s_ref = take_stage_snapshot(ws, stage="specify", store=store, producer_event_id="ev-1")
    results = evaluate_specify_stage(snapshot, store=store, events=[], evidence_ref=s_ref, product_root=ws)
    res_map = {r.check_id: r for r in results}
    assert res_map["SP.C01"].status == "fail"


def test_m02_wrong_routing_killed_by_analyze_oracle(tmp_path):
    # M02: wrong capability routing
    store = EvidenceStore.create(tmp_path / "store", "run-m02", "root-m02")
    ws = tmp_path / "product"
    ws.mkdir()
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: analyzing\n", encoding="utf-8")
    (ch_dir / "routing.yaml").write_text("capabilities:\n  - non_existent_capability\n", encoding="utf-8")
    
    snapshot, s_ref = take_stage_snapshot(ws, stage="analyze", store=store, producer_event_id="ev-1")
    results = evaluate_analyze_stage(snapshot, store=store, events=[], evidence_ref=s_ref, product_root=ws)
    res_map = {r.check_id: r for r in results}
    assert res_map["AN.C01"].status == "fail"


def test_m04_missing_dependency_killed_by_decompose_oracle(tmp_path):
    # M04: missing task dependency
    store = EvidenceStore.create(tmp_path / "store", "run-m04", "root-m04")
    ws = tmp_path / "product"
    ws.mkdir()
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    tasks_dir = ch_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: decomposing\n", encoding="utf-8")
    (tasks_dir / "02-successor.yaml").write_text("id: T02\ndepends_on:\n  - T01_MISSING\n", encoding="utf-8")
    
    snapshot, s_ref = take_stage_snapshot(ws, stage="decompose", store=store, producer_event_id="ev-1")
    results = evaluate_decompose_stage(snapshot, store=store, events=[], evidence_ref=s_ref, product_root=ws)
    res_map = {r.check_id: r for r in results}
    assert res_map["DE.C02"].status == "fail"


def test_m06_weakened_test_killed_by_implement_oracle(tmp_path):
    # M06: frozen test modified/weakened during implement
    store = EvidenceStore.create(tmp_path / "store", "run-m06", "root-m06")
    ws = tmp_path / "product"
    ws.mkdir()
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: implementing\n", encoding="utf-8")
    test_f = ws / "tests" / "test_suite.py"
    test_f.parent.mkdir()
    test_f.write_text("def test_foo(): pass # weakened", encoding="utf-8")
    
    snapshot, s_ref = take_stage_snapshot(ws, stage="implement", store=store, producer_event_id="ev-1")
    declared_hashes = {"tests/test_suite.py": "ORIGINAL_HASH_12345"}
    
    results = evaluate_implement_stage(
        snapshot,
        store=store,
        events=[],
        declared_test_hashes=declared_hashes,
        evidence_ref=s_ref,
        product_root=ws,
    )
    res_map = {r.check_id: r for r in results}
    assert res_map["IM.C03"].status == "fail"
