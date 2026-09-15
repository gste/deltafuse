from pathlib import Path
import pytest

from scripts.document_flow.snapshots import take_stage_snapshot
from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.oracles.implement import evaluate_implement_stage
from scripts.document_flow.oracles.verify import evaluate_verify_stage


SHA = "a" * 64


def init_mock_product(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    dot_df = ws / ".deltafuse"
    dot_df.mkdir(parents=True, exist_ok=True)
    (dot_df / "config.yaml").write_text("framework:\n  version: 3.0.0\n", encoding="utf-8")
    (dot_df / "lock.yaml").write_text("framework:\n  version: 3.0.0\n  sha: " + SHA + "\n", encoding="utf-8")


def test_implement_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: implementing\n", encoding="utf-8")
    
    test_file = ws / "tests" / "test_supersede.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_supersede(): assert True", encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="implement", store=store, producer_event_id="ev-im-1")
    
    test_entry = next(f for f in snapshot.files if f["path"] == "tests/test_supersede.py")
    declared_hashes = {"tests/test_supersede.py": test_entry["sha256"]}
    
    test_results = [
        {"name": "test_supersede", "exit_code": 0, "status": "passed"}
    ]
    events = [
        {"kind": "file_write", "path": "document-service/src/main/java/dev/deltafuse/App.java"}
    ]
    
    results = evaluate_implement_stage(
        snapshot,
        store=store,
        events=events,
        test_results=test_results,
        declared_test_hashes=declared_hashes,
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    
    assert result_map["IM.C01"].status == "pass"
    assert result_map["IM.C01"].awarded_points == 240
    assert result_map["IM.C02"].status == "pass"
    assert result_map["IM.C02"].awarded_points == 160
    assert result_map["IM.C03"].status == "pass"
    assert result_map["IM.C03"].awarded_points == 120
    assert result_map["IM.C04"].status == "pass"
    assert result_map["IM.C04"].awarded_points == 80
    assert result_map["IM.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("IM.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("IM.D"))
    assert correctness == 600
    assert discipline == 250


def test_implement_oracle_negative_modified_test(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    test_file = ws / "tests" / "test_supersede.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_supersede(): assert True # modified", encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="implement", store=store, producer_event_id="ev-im-1")
    
    declared_hashes = {"tests/test_supersede.py": "0" * 64}
    
    results = evaluate_implement_stage(
        snapshot,
        store=store,
        events=[],
        declared_test_hashes=declared_hashes,
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    assert result_map["IM.C03"].status == "fail"


def test_implement_oracle_negative_failing_test(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="implement", store=store, producer_event_id="ev-im-1")
    
    test_results = [
        {"name": "test_supersede", "exit_code": 1, "status": "failed"}
    ]
    
    results = evaluate_implement_stage(
        snapshot,
        store=store,
        events=[],
        test_results=test_results,
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    assert result_map["IM.C01"].status == "fail"


def test_verify_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(
        ws,
        stage="verify",
        store=store,
        producer_event_id="ev-ve-1",
        git_state={"head": SHA, "branch": "master", "dirty": False},
    )
    
    tasks_status = {
        "TASK-001": "verified",
        "TASK-002": "verified",
    }
    system_evidence = {
        "exit_code": 0,
        "classification": "complete",
    }
    events = [
        {"kind": "file_write", "path": "docs/changes/CHG-001/evidence.yaml"}
    ]
    
    results = evaluate_verify_stage(
        snapshot,
        store=store,
        events=events,
        tasks_status=tasks_status,
        system_evidence=system_evidence,
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    
    assert result_map["VE.C01"].status == "pass"
    assert result_map["VE.C01"].awarded_points == 180
    assert result_map["VE.C02"].status == "pass"
    assert result_map["VE.C02"].awarded_points == 180
    assert result_map["VE.C03"].status == "pass"
    assert result_map["VE.C03"].awarded_points == 140
    assert result_map["VE.C04"].status == "pass"
    assert result_map["VE.C04"].awarded_points == 100
    assert result_map["VE.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("VE.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("VE.D"))
    assert correctness == 600
    assert discipline == 250


def test_verify_oracle_negative_non_terminal_task(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="verify", store=store, producer_event_id="ev-ve-1")
    
    tasks_status = {
        "TASK-001": "verified",
        "TASK-002": "declaring",
    }
    
    results = evaluate_verify_stage(
        snapshot,
        store=store,
        events=[],
        tasks_status=tasks_status,
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    assert result_map["VE.C01"].status == "fail"


def test_verify_oracle_negative_dirty_tree(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(
        ws,
        stage="verify",
        store=store,
        producer_event_id="ev-ve-1",
        git_state={"head": SHA, "branch": "master", "dirty": True},
    )
    
    results = evaluate_verify_stage(
        snapshot,
        store=store,
        events=[],
        evidence_ref=ref,
        product_root=ws,
    )
    result_map = {r.check_id: r for r in results}
    assert result_map["VE.C03"].status == "fail"
