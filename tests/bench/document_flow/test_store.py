import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.document_flow.canonical import CanonicalError, canonical_bytes, content_hash, with_self_hash
from scripts.document_flow.store import EvidenceRef, EvidenceStore, IntegrityError


KEY = b"host-owned-test-key"


def store(tmp_path, name="run-1"):
    return EvidenceStore.create(tmp_path / name, name, f"root-{name}")


def test_canonical_json_and_self_hash_are_deterministic():
    left = {"z": [1, True, None], "a": "é", "report_hash": "ignored"}
    right = {"report_hash": "different", "a": "é", "z": [1, True, None]}
    assert canonical_bytes(left) != canonical_bytes(right)
    assert content_hash(left, exclude=("report_hash",)) == content_hash(right, exclude=("report_hash",))
    sealed = with_self_hash({"value": 1}, "report_hash")
    assert sealed["report_hash"] == content_hash(sealed, exclude=("report_hash",))
    with pytest.raises(CanonicalError):
        canonical_bytes({"float": 1.5})


def test_content_addressed_put_resolve_and_missing_object(tmp_path):
    evidence = store(tmp_path)
    ref = evidence.put(b"payload", "text/plain", "event-1")
    assert evidence.put(b"payload", "text/plain", "event-1") == ref
    assert evidence.resolve(ref) == b"payload"
    (evidence.root / ref.key).unlink()
    with pytest.raises(IntegrityError, match="missing object"):
        evidence.resolve(ref)


@pytest.mark.parametrize("key", ["../secret", "/absolute", "C:/absolute", "objects\\hash", "objects/not-a-hash"])
def test_unsafe_relative_refs_are_rejected(tmp_path, key):
    evidence = store(tmp_path)
    ref = EvidenceRef(key, "a" * 64, "text/plain", 1, "event-1", evidence.run_id, evidence.root_id)
    with pytest.raises(IntegrityError, match="unsafe evidence key"):
        evidence.resolve(ref)


def test_cross_run_substitution_is_rejected(tmp_path):
    first = store(tmp_path, "run-1")
    second = store(tmp_path, "run-2")
    ref = first.put(b"same", "text/plain", "event-1")
    second.put(b"same", "text/plain", "event-1")
    with pytest.raises(IntegrityError, match="run/root identity mismatch"):
        second.resolve(ref)


def test_symlink_or_junction_boundary_is_rejected(tmp_path, monkeypatch):
    evidence = store(tmp_path)
    ref = evidence.put(b"payload", "text/plain", "event-1")
    monkeypatch.setattr(evidence, "_has_link_boundary", lambda path: True)
    with pytest.raises(IntegrityError, match="link boundary"):
        evidence.resolve(ref)


def test_event_chain_and_repeated_verification_are_identical(tmp_path):
    evidence = store(tmp_path)
    evidence.append_event({"kind": "first", "payload": {"value": 1}})
    evidence.append_event({"kind": "second", "payload": {"value": 2}})
    evidence.finalize_json("reports/run.json", {"raw_score": 1, "final_score": 1})
    seal = evidence.seal(KEY)
    assert evidence.verify(seal, KEY) == evidence.verify(seal, KEY)


def _rewrite_event_chain(path, mutate_first=True, remove_last=False):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if mutate_first:
        rows[0]["payload"]["value"] = 99
    previous = None
    for sequence, row in enumerate(rows):
        row["sequence"] = sequence
        row["previous_hash"] = previous
        row["event_hash"] = content_hash(row, exclude=("event_hash",))
        previous = row["event_hash"]
    if remove_last:
        rows.pop()
    path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))


def test_rewritten_and_rehashed_event_chain_fails_external_seal(tmp_path):
    evidence = store(tmp_path)
    evidence.append_event({"kind": "first", "payload": {"value": 1}})
    evidence.append_event({"kind": "second", "payload": {"value": 2}})
    seal = evidence.seal(KEY)
    _rewrite_event_chain(evidence.events_path)
    with pytest.raises(IntegrityError, match="sealed manifest mismatch"):
        evidence.verify(seal, KEY)


def test_removed_or_truncated_event_segment_fails(tmp_path):
    evidence = store(tmp_path)
    evidence.append_event({"kind": "first", "payload": {"value": 1}})
    evidence.append_event({"kind": "second", "payload": {"value": 2}})
    seal = evidence.seal(KEY)
    _rewrite_event_chain(evidence.events_path, mutate_first=False, remove_last=True)
    with pytest.raises(IntegrityError, match="sealed manifest mismatch"):
        evidence.verify(seal, KEY)


def test_report_rehash_still_requires_semantic_recomputation(tmp_path):
    evidence = store(tmp_path)
    evidence.finalize_json("reports/run.json", {"facts": [1, 2], "raw_score": 3})
    seal = evidence.seal(KEY)
    assert evidence.verify(seal, KEY, {"reports/run.json": lambda value: value["raw_score"] == sum(value["facts"])})

    forged = with_self_hash({"facts": [1, 2], "raw_score": 999}, "report_hash")
    report_path = evidence.root / "reports/run.json"
    report_path.write_bytes(canonical_bytes(forged))
    forged_seal = evidence.seal(KEY)
    with pytest.raises(IntegrityError, match="semantic recomputation mismatch"):
        evidence.verify(forged_seal, KEY, {"reports/run.json": lambda value: value["raw_score"] == sum(value["facts"])})
    with pytest.raises(IntegrityError, match="sealed manifest mismatch"):
        evidence.verify(seal, KEY)


def test_tampered_seal_manifest_cannot_be_resigned_locally(tmp_path):
    evidence = store(tmp_path)
    seal = evidence.seal(KEY)
    tampered = type(seal)(seal.manifest_bytes.replace(b'"run-1"', b'"run-x"'), seal.mac_sha256)
    with pytest.raises(IntegrityError, match="seal authentication"):
        evidence.verify(tampered, KEY)


def test_finalize_is_create_only_and_collision_safe(tmp_path):
    evidence = store(tmp_path)
    evidence.finalize_json("stages/intake.json", {"score": 1})
    with pytest.raises(IntegrityError, match="already finalized"):
        evidence.finalize_json("stages/intake.json", {"score": 2})
    with pytest.raises(IntegrityError, match="unsafe final path"):
        evidence.finalize_json("../escape.json", {"score": 1})


def test_recovery_removes_only_temporary_files_and_keeps_finalized_reports(tmp_path):
    evidence = store(tmp_path)
    evidence.finalize_json("reports/run.json", {"score": 1})
    temporary = evidence.root / "objects" / ".tmp-interrupted"
    temporary.write_bytes(b"partial")
    evidence.recover()
    assert not temporary.exists()
    assert (evidence.root / "reports/run.json").is_file()
