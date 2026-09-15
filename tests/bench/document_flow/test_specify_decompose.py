from pathlib import Path
import pytest

from scripts.document_flow.snapshots import take_stage_snapshot
from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.witness import validate_witnesses
from scripts.document_flow.oracles.specify import evaluate_specify_stage
from scripts.document_flow.oracles.decompose import evaluate_decompose_stage


SHA = "a" * 64


def init_mock_product(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    dot_df = ws / ".deltafuse"
    dot_df.mkdir(parents=True, exist_ok=True)
    (dot_df / "config.yaml").write_text("framework:\n  version: 3.0.0\n", encoding="utf-8")
    (dot_df / "lock.yaml").write_text("framework:\n  version: 3.0.0\n  sha: " + SHA + "\n", encoding="utf-8")


def valid_spec_content() -> str:
    obls = [f'{{"obligation_id": "J03-OBL-{i:03d}", "source_anchor": "INSTRUCTION.md#4", "predicate": "version.status != null"}}' for i in range(1, 19)]
    return f"""# Specification: Version Supersede and Route Approval
## Obligations
```j03-obligations
[
  {",\n  ".join(obls)}
]
```

## State Machine
- Supersede transitions: Pending routes become `SUPERSEDED` when a new version is submitted.
- Approval stages: `expert-review` (legal, security slots) then `registrar`.

## Canonical Query
- Endpoint returns canonical `audit_sequence` and `open_slots`.

## Compatibility
- Full backward compatibility with baseline single-approver behavior.
"""


def test_witness_validation():
    valid_text = valid_spec_content()
    res = validate_witnesses(valid_text)
    assert res.valid
    assert len(res.entries) == 18

    # Vacuous predicate
    vacuous_text = """```j03-obligations
[{"obligation_id": "J03-OBL-001", "source_anchor": "INSTRUCTION.md#1", "predicate": "True == True"}]
```"""
    res_vac = validate_witnesses(vacuous_text)
    assert not res_vac.valid
    assert any("vacuous" in e for e in res_vac.errors)

    # Contradictory predicate
    contra_text = """```j03-obligations
[{"obligation_id": "J03-OBL-001", "source_anchor": "INSTRUCTION.md#1", "predicate": "status == 'APPROVED' and status == 'REJECTED'"}]
```"""
    res_con = validate_witnesses(contra_text)
    assert not res_con.valid
    assert any("contradictory" in e for e in res_con.errors)


def test_specify_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "spec.md").write_text(valid_spec_content(), encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="specify", store=store, producer_event_id="ev-sp-1")
    
    events = [
        {"kind": "file_write", "path": "docs/changes/CHG-001/spec.md"}
    ]
    
    results = evaluate_specify_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    
    assert result_map["SP.C01"].status == "pass"
    assert result_map["SP.C01"].awarded_points == 240
    assert result_map["SP.C02"].status == "pass"
    assert result_map["SP.C02"].awarded_points == 160
    assert result_map["SP.C03"].status == "pass"
    assert result_map["SP.C03"].awarded_points == 120
    assert result_map["SP.C04"].status == "pass"
    assert result_map["SP.C04"].awarded_points == 80
    assert result_map["SP.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("SP.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("SP.D"))
    assert correctness == 600
    assert discipline == 250


def test_specify_oracle_negative_missing_supersede(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    bad_spec = valid_spec_content().replace("SUPERSEDED", "SOME_OTHER_STATUS").replace("Supersede", "Other")
    (ch_dir / "spec.md").write_text(bad_spec, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="specify", store=store, producer_event_id="ev-sp-1")
    
    results = evaluate_specify_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["SP.C02"].status == "fail"


def test_decompose_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    tasks_dir = ws / "docs" / "changes" / "CHG-001" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    task1 = """---
id: TASK-001
change: CHG-001
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: added
spec_refs: ["docs/spec/supersede.md"]
allowed_paths: ["document-service/src/**"]
forbidden_paths: ["workflow-service/**"]
context_budget:
  max_tokens: 50000
  max_files: 10
---
# Task 1: Document service supersede
"""
    task2 = """---
id: TASK-002
change: CHG-001
slice: SLICE-02
kind: feature
status: pending
depends_on: [TASK-001]
requirement_delta: added
spec_refs: ["docs/spec/approval.md"]
allowed_paths: ["workflow-service/src/**"]
forbidden_paths: ["document-service/**"]
context_budget:
  max_tokens: 50000
  max_files: 10
---
# Task 2: Workflow parallel approval
"""
    (tasks_dir / "TASK-001.md").write_text(task1, encoding="utf-8")
    (tasks_dir / "TASK-002.md").write_text(task2, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="decompose", store=store, producer_event_id="ev-de-1")
    
    events = [
        {"kind": "file_write", "path": "docs/changes/CHG-001/tasks/TASK-001.md"},
        {"kind": "file_write", "path": "docs/changes/CHG-001/tasks/TASK-002.md"},
    ]
    
    results = evaluate_decompose_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    
    assert result_map["DE.C01"].status == "pass"
    assert result_map["DE.C01"].awarded_points == 200
    assert result_map["DE.C02"].status == "pass"
    assert result_map["DE.C02"].awarded_points == 160
    assert result_map["DE.C03"].status == "pass"
    assert result_map["DE.C03"].awarded_points == 140
    assert result_map["DE.C04"].status == "pass"
    assert result_map["DE.C04"].awarded_points == 100
    assert result_map["DE.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("DE.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("DE.D"))
    assert correctness == 600
    assert discipline == 250


def test_decompose_oracle_negative_cycle(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    tasks_dir = ws / "docs" / "changes" / "CHG-001" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    task1 = """---
id: TASK-001
depends_on: [TASK-002]
allowed_paths: ["document-service/src/**"]
---
"""
    task2 = """---
id: TASK-002
depends_on: [TASK-001]
allowed_paths: ["workflow-service/src/**"]
---
"""
    (tasks_dir / "TASK-001.md").write_text(task1, encoding="utf-8")
    (tasks_dir / "TASK-002.md").write_text(task2, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="decompose", store=store, producer_event_id="ev-de-1")
    
    results = evaluate_decompose_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["DE.C01"].status == "fail"
    assert "cycle" in (result_map["DE.C01"].failure_reason or "")


def test_decompose_oracle_negative_unbounded_paths(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    tasks_dir = ws / "docs" / "changes" / "CHG-001" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    task1 = """---
id: TASK-001
depends_on: []
allowed_paths: ["/**"]
---
"""
    (tasks_dir / "TASK-001.md").write_text(task1, encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="decompose", store=store, producer_event_id="ev-de-1")
    
    results = evaluate_decompose_stage(snapshot, store=store, events=[], evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["DE.C02"].status == "fail"
