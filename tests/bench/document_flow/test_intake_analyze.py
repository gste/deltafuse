from pathlib import Path
import pytest

from scripts.document_flow.snapshots import FileEntry, SnapshotData, take_stage_snapshot
from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.oracles.intake import evaluate_intake_stage
from scripts.document_flow.oracles.analyze import evaluate_analyze_stage


SHA = "a" * 64


def init_mock_product(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    dot_df = ws / ".deltafuse"
    dot_df.mkdir(parents=True, exist_ok=True)
    (dot_df / "config.yaml").write_text("framework:\n  version: 3.0.0\n", encoding="utf-8")
    (dot_df / "lock.yaml").write_text("framework:\n  version: 3.0.0\n  sha: " + SHA + "\n", encoding="utf-8")


def valid_intake_content() -> str:
    obls = [f'{{"obligation_id": "J03-OBL-{i:03d}", "source_anchor": "INSTRUCTION.md#4"}}' for i in range(1, 19)]
    return f"""# Change request: managed version supersede
Case: J03-document-flow

```j03-obligations
[
  {",\n  ".join(obls)}
]
```
"""


def test_intake_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: intake\n", encoding="utf-8")
    (ch_dir / "input.md").write_text(valid_intake_content(), encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    
    snapshot, ref = take_stage_snapshot(ws, stage="intake", store=store, producer_event_id="ev-1")
    
    events = [
        {"kind": "file_read", "path": "docs/changes/CHG-001/input.md"},
        {"kind": "file_write", "path": "docs/changes/CHG-001/change.yaml"},
    ]
    
    results = evaluate_intake_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    
    result_map = {r.check_id: r for r in results}
    assert result_map["IN.C01"].status == "pass"
    assert result_map["IN.C01"].awarded_points == 240
    assert result_map["IN.C02"].status == "pass"
    assert result_map["IN.C02"].awarded_points == 180
    assert result_map["IN.C03"].status == "pass"
    assert result_map["IN.C03"].awarded_points == 120
    assert result_map["IN.C04"].status == "pass"
    assert result_map["IN.C04"].awarded_points == 60
    assert result_map["IN.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("IN.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("IN.D"))
    assert correctness == 600
    assert discipline == 250


def test_intake_oracle_negative_invented_obligation(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    bad_content = valid_intake_content().replace(
        '"J03-OBL-018"',
        '"J03-OBL-999-SPURIOUS"'
    )
    (ch_dir / "input.md").write_text(bad_content, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="intake", store=store, producer_event_id="ev-1")
    
    results = evaluate_intake_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["IN.C01"].status == "fail"
    assert result_map["IN.C01"].awarded_points == 0
    assert "J03-OBL-999-SPURIOUS" in (result_map["IN.C01"].failure_reason or "")


def test_intake_oracle_negative_forbidden_read(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "input.md").write_text(valid_intake_content(), encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="intake", store=store, producer_event_id="ev-1")
    
    events = [
        {"kind": "file_read", "path": "process/bench/cases/J03-document-flow/hidden_suite/test_functional.py"}
    ]
    
    results = evaluate_intake_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["IN.C03"].status == "fail"
    assert result_map["IN.C03"].awarded_points == 0


def test_intake_oracle_negative_envelope_write(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "input.md").write_text(valid_intake_content(), encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="intake", store=store, producer_event_id="ev-1")
    
    events = [
        {"kind": "file_write", "path": "document-service/src/main/java/App.java"}
    ]
    
    results = evaluate_intake_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["IN.D01"].status == "fail"


def test_analyze_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    analysis_text = """# Analysis
Impacted services:
- document-service
- workflow-service
- audit-service

Topics:
- j03.document-events
- j03.workflow-events

Slices:
- slice 1: document service draft and submit
- slice 2: workflow approval
"""
    (ch_dir / "analysis.md").write_text(analysis_text, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="analyze", store=store, producer_event_id="ev-an-1")
    
    events = [
        {"kind": "file_write", "path": "docs/changes/CHG-001/analysis.md"}
    ]
    
    results = evaluate_analyze_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["AN.C01"].status == "pass"
    assert result_map["AN.C01"].awarded_points == 180
    assert result_map["AN.C02"].status == "pass"
    assert result_map["AN.C02"].awarded_points == 180
    assert result_map["AN.C03"].status == "pass"
    assert result_map["AN.C03"].awarded_points == 140
    assert result_map["AN.C04"].status == "pass"
    assert result_map["AN.C04"].awarded_points == 100
    assert result_map["AN.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("AN.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("AN.D"))
    assert correctness == 600
    assert discipline == 250


def test_analyze_oracle_negative_whole_repo_slice(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    analysis_text = """# Analysis
Impacted services: document-service, workflow-service, audit-service
Topics: j03.document-events, j03.workflow-events
Slices:
- slice 1: path: /**
"""
    (ch_dir / "analysis.md").write_text(analysis_text, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="analyze", store=store, producer_event_id="ev-an-1")
    
    results = evaluate_analyze_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["AN.C02"].status == "fail"


def test_analyze_oracle_negative_spurious_decision(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    analysis_text = """# Analysis
Impacted services: document-service, workflow-service, audit-service
Topics: j03.document-events, j03.workflow-events
Slices: bounded
Decisions:
- DEC-FORGED: override standard consensus
"""
    (ch_dir / "analysis.md").write_text(analysis_text, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="analyze", store=store, producer_event_id="ev-an-1")
    
    results = evaluate_analyze_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["AN.C03"].status == "fail"
