import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from scripts.document_flow.store import EvidenceStore, IntegrityError
from scripts.document_flow.snapshots import (
    STAGES,
    capture_workspace_inventory,
    compute_tree_hash,
    take_stage_snapshot,
    record_stage_visit,
    finalize_stage_rollups,
)

SCHEMA_ROOT = Path("scripts/document_flow/schemas")
SHA = "a" * 64


def load_stage_validator():
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (
        SCHEMA_ROOT / "evidence-ref.schema.json",
        SCHEMA_ROOT / "event.schema.json",
        SCHEMA_ROOT / "stage.schema.json",
    )]
    registry = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    return Draft202012Validator(schemas[-1], registry=registry, format_checker=FormatChecker())


def sample_identity():
    return {
        "campaign_id": "campaign-1",
        "run_id": "run-1",
        "case_id": "J03-document-flow",
        "variant_id": "variant-1",
        "framework_commit": SHA,
        "wheel_sha256": SHA,
        "lock_sha256": SHA,
        "registry_sha256": SHA,
        "agent_name": "little-coder",
        "agent_version": "1.19.0",
        "agent_config_sha256": SHA,
        "model_id": "laguna-xs-2.1",
        "provider_id": "provider-1",
        "endpoint_attestation_ref": {
            "key": "objects/endpoint.json",
            "sha256": SHA,
            "media_type": "application/json",
            "byte_length": 12,
            "producer_event_id": "event-1",
        },
        "tokenizer_fingerprint": SHA,
    }


def sample_attestation_refs():
    return [{
        "key": "objects/attestation.json",
        "sha256": SHA,
        "media_type": "application/json",
        "byte_length": 20,
        "producer_event_id": "event-attest-1",
    }]


def init_mock_product(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    dot_df = ws / ".deltafuse"
    dot_df.mkdir(parents=True, exist_ok=True)
    (dot_df / "config.yaml").write_text("framework:\n  version: 3.0.0\n", encoding="utf-8")
    (dot_df / "lock.yaml").write_text("framework:\n  version: 3.0.0\n  sha: " + SHA + "\n", encoding="utf-8")


def test_capture_workspace_inventory_filters_ignored(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "file1.txt").write_text("hello world", encoding="utf-8")
    (ws / "sub").mkdir()
    (ws / "sub" / "file2.txt").write_text("sub file", encoding="utf-8")
    
    # Ignored directories
    (ws / ".git").mkdir()
    (ws / ".git" / "HEAD").write_text("ref: refs/heads/master", encoding="utf-8")
    (ws / "__pycache__").mkdir()
    (ws / "__pycache__" / "file1.pyc").write_bytes(b"dummy")
    (ws / ".tmp-1234").write_text("temp", encoding="utf-8")
    
    entries = capture_workspace_inventory(ws)
    paths = [e.path for e in entries]
    assert paths == ["file1.txt", "sub/file2.txt"]
    assert len(entries) == 2
    
    tree_hash1 = compute_tree_hash(entries)
    tree_hash2 = compute_tree_hash(entries)
    assert tree_hash1 == tree_hash2
    assert len(tree_hash1) == 64


def test_take_stage_snapshot_and_store(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    (ws / "doc.txt").write_text("initial content", encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    
    snapshot, ref = take_stage_snapshot(
        ws,
        stage="intake",
        store=store,
        producer_event_id="ev-snap-1",
    )
    
    assert snapshot.stage == "intake"
    assert snapshot.file_count >= 2
    assert ref.key.startswith("objects/")
    
    raw = store.resolve(ref)
    assert b"initial content" not in raw
    loaded = json.loads(raw.decode("utf-8"))
    assert loaded["stage"] == "intake"
    assert loaded["tree_sha256"] == snapshot.tree_sha256


def test_record_stage_visit_immutability(tmp_path):
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    
    dummy_snap_bytes = b'{"snap": 1}'
    snap_ref = store.put(dummy_snap_bytes, "application/json", "ev-snap-1")
    
    visit = record_stage_visit(
        store,
        visit_id="visit-001",
        stage="intake",
        task_id="task-intake-1",
        snapshot_ref=snap_ref,
        start_event_seq=0,
        end_event_seq=5,
    )
    
    assert visit["visit_id"] == "visit-001"
    assert visit["stage"] == "intake"
    
    with pytest.raises(IntegrityError):
        record_stage_visit(
            store,
            visit_id="visit-001",
            stage="intake",
            task_id="task-intake-1",
            snapshot_ref=snap_ref,
            start_event_seq=0,
            end_event_seq=6,
        )


def test_finalize_stage_rollups_conforms_to_schema(tmp_path):
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    
    snap_ref = store.put(b"{}", "application/json", "ev-snap-1")
    
    intake_visit = record_stage_visit(
        store,
        visit_id="visit-in-1",
        stage="intake",
        snapshot_ref=snap_ref,
        start_event_seq=0,
        end_event_seq=3,
    )
    analyze_visit = record_stage_visit(
        store,
        visit_id="visit-an-1",
        stage="analyze",
        snapshot_ref=snap_ref,
        start_event_seq=4,
        end_event_seq=8,
    )
    
    stage_visits = {
        "intake": [intake_visit],
        "analyze": [analyze_visit],
    }
    
    reports = finalize_stage_rollups(
        store,
        identity=sample_identity(),
        stage_visits=stage_visits,
        attestation_refs=sample_attestation_refs(),
    )
    
    validator = load_stage_validator()
    assert len(reports) == 7
    for stage_name, report in reports.items():
        validator.validate(report)
        if stage_name in ("intake", "analyze"):
            assert report["status"] == "passed"
            assert len(report["visit_ids"]) == 1
        else:
            assert report["status"] == "not_reached"
            assert len(report["visit_ids"]) == 0
            assert report["totals"]["score"] == 0


def test_earlier_stage_evidence_preserved_against_later_workspace_edits(tmp_path):
    ws = tmp_path / "product"
    init_mock_product(ws)
    (ws / "spec.md").write_text("original spec v1", encoding="utf-8")
    
    store_root = tmp_path / "store"
    store = EvidenceStore.create(store_root, "run-1", "root-1")
    
    # 1. Intake snapshot
    snap_intake, ref_intake = take_stage_snapshot(ws, stage="intake", store=store, producer_event_id="ev-1")
    
    # 2. Later, in implementation, spec is edited/mutated
    (ws / "spec.md").write_text("mutated spec v2 in implement stage", encoding="utf-8")
    snap_impl, ref_impl = take_stage_snapshot(ws, stage="implement", store=store, producer_event_id="ev-2")
    
    # Verify intake snapshot in store remains completely unaffected
    intake_data = json.loads(store.resolve(ref_intake).decode("utf-8"))
    spec_in_intake = next(f for f in intake_data["files"] if f["path"] == "spec.md")
    
    impl_data = json.loads(store.resolve(ref_impl).decode("utf-8"))
    spec_in_impl = next(f for f in impl_data["files"] if f["path"] == "spec.md")
    
    assert spec_in_intake["sha256"] != spec_in_impl["sha256"]
    assert intake_data["tree_sha256"] != impl_data["tree_sha256"]
