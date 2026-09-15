from pathlib import Path
import pytest

from scripts.document_flow.snapshots import take_stage_snapshot
from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.red_runner import (
    AUTHENTIC_RED,
    COMPILE_ERROR,
    ALREADY_GREEN,
    SYNTAX_OR_IMPORT_ERROR,
    RedExecutionResult,
    classify_test_output,
    run_declared_test,
)
from scripts.document_flow.oracles.declare import evaluate_declare_stage


SHA = "a" * 64


def init_mock_product(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    dot_df = ws / ".deltafuse"
    dot_df.mkdir(parents=True, exist_ok=True)
    (dot_df / "config.yaml").write_text("framework:\n  version: 3.0.0\n", encoding="utf-8")
    (dot_df / "lock.yaml").write_text("framework:\n  version: 3.0.0\n  sha: " + SHA + "\n", encoding="utf-8")


def test_classify_test_output():
    # 1. Assertion failure
    auth, cat, msg = classify_test_output(1, "E AssertionError: assert 1 == 2", "")
    assert auth is True
    assert cat == AUTHENTIC_RED

    # 2. Compilation error
    auth, cat, msg = classify_test_output(1, "[ERROR] COMPILATION ERROR: cannot find symbol", "")
    assert auth is False
    assert cat == COMPILE_ERROR

    # 3. Already green (exit 0)
    auth, cat, msg = classify_test_output(0, "1 passed in 0.01s", "")
    assert auth is False
    assert cat == ALREADY_GREEN

    # 4. Syntax error
    auth, cat, msg = classify_test_output(1, "SyntaxError: invalid syntax", "")
    assert auth is False
    assert cat == SYNTAX_OR_IMPORT_ERROR


def test_run_declared_test_live(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    test_file = seed / "test_dummy.py"
    test_file.write_text("def test_failing():\n    assert 1 == 2\n", encoding="utf-8")
    
    res = run_declared_test(seed, test_file)
    assert res.exit_code == 1
    assert res.authentic_red is True
    assert res.failure_category == AUTHENTIC_RED
    assert len(res.test_sha256) == 64


def test_declare_oracle_positive(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    (ch_dir / "change.yaml").write_text("id: CHG-001\nstatus: declaring\n", encoding="utf-8")
    
    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_feature.py").write_text("def test_feat(): assert 1 == 2", encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="declare", store=store, producer_event_id="ev-rd-1")
    
    events = [
        {"kind": "file_write", "path": "tests/test_feature.py"}
    ]
    
    red_results = [
        RedExecutionResult(
            test_path="tests/test_feature.py",
            test_name="test_feature",
            test_sha256=SHA,
            exit_code=1,
            authentic_red=True,
            failure_category=AUTHENTIC_RED,
            failure_message="assert 1 == 2",
            duration_ms=50,
            stdout="AssertionError",
            stderr="",
        )
    ]
    
    results = evaluate_declare_stage(snapshot, store=store, events=events, red_results=red_results, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    
    assert result_map["RD.C01"].status == "pass"
    assert result_map["RD.C01"].awarded_points == 220
    assert result_map["RD.C02"].status == "pass"
    assert result_map["RD.C02"].awarded_points == 160
    assert result_map["RD.C03"].status == "pass"
    assert result_map["RD.C03"].awarded_points == 120
    assert result_map["RD.C04"].status == "pass"
    assert result_map["RD.C04"].awarded_points == 100
    assert result_map["RD.D01"].status == "pass"
    
    correctness = sum(r.awarded_points for r in results if r.check_id.startswith("RD.C"))
    discipline = sum(r.awarded_points for r in results if r.check_id.startswith("RD.D"))
    assert correctness == 600
    assert discipline == 250


def test_declare_oracle_negative_compilation_error_as_red(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    ch_dir = ws / "docs" / "changes" / "CHG-001"
    ch_dir.mkdir(parents=True)
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="declare", store=store, producer_event_id="ev-rd-1")
    
    red_results = [
        RedExecutionResult(
            test_path="tests/test_bad.py",
            test_name="test_bad",
            test_sha256=SHA,
            exit_code=1,
            authentic_red=False,
            failure_category=COMPILE_ERROR,
            failure_message="Compilation failure",
            duration_ms=50,
            stdout="cannot find symbol",
            stderr="",
        )
    ]
    
    results = evaluate_declare_stage(snapshot, store=store, events=[], red_results=red_results, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["RD.C01"].status == "fail"


def test_declare_oracle_negative_disallowed_write(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    snapshot, ref = take_stage_snapshot(ws, stage="declare", store=store, producer_event_id="ev-rd-1")
    
    events = [
        {"kind": "file_write", "path": "document-service/src/main/java/dev/deltafuse/App.java"}
    ]
    
    results = evaluate_declare_stage(snapshot, store=store, events=events, evidence_ref=ref, product_root=ws)
    result_map = {r.check_id: r for r in results}
    assert result_map["RD.D01"].status == "fail"
