"""Tests for attestation creation and adversarial leak probes (J03-506)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.document_flow.attest import build_sealed_attestation
from scripts.document_flow.probes import ProbeReport, run_local_adversarial_probe
from scripts.document_flow.store import EvidenceStore


SCHEMAS_DIR = Path("scripts/document_flow/schemas")


def get_attestation_validator():
    att_schema = json.loads((SCHEMAS_DIR / "attestation.schema.json").read_text(encoding="utf-8"))
    ref_schema = json.loads((SCHEMAS_DIR / "evidence-ref.schema.json").read_text(encoding="utf-8"))
    
    registry = Registry().with_resources([
        (att_schema["$id"], Resource.from_contents(att_schema)),
        (ref_schema["$id"], Resource.from_contents(ref_schema)),
    ])
    return Draft202012Validator(att_schema, registry=registry)


def test_build_sealed_attestation_measured_valid(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    validator = get_attestation_validator()

    probe = run_local_adversarial_probe(
        sandbox_root=tmp_path / "sandbox",
        sentinel_path=tmp_path / "outside-sentinel.txt",
    )

    doc = build_sealed_attestation(
        store,
        profile_id="profile-measured-1",
        status="measured",
        evidence_root_id="root-1",
        probe_report=probe,
    )

    validator.validate(doc)
    assert doc["status"] == "measured"
    assert doc["release_eligible"] is True
    assert doc["model"]["measurement_source"] == "measured"


def test_build_sealed_attestation_declared_valid(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    validator = get_attestation_validator()

    doc = build_sealed_attestation(
        store,
        profile_id="profile-declared-1",
        status="declared",
        evidence_root_id="root-1",
    )

    validator.validate(doc)
    assert doc["status"] == "declared"
    assert doc["release_eligible"] is False
    assert doc["model"]["measurement_source"] == "declared"


def test_adversarial_probe_detects_leaked_sentinel(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(parents=True)
    
    sentinel_file = sandbox / "leaked_sentinel.txt"
    sentinel_file.write_bytes(b"sentinel-secret-12345")

    probe = run_local_adversarial_probe(
        sandbox_root=sandbox,
        sentinel_path=sentinel_file,
    )

    assert probe.sentinel_read == "LEAK"
    assert len(probe.sentinel_found) == 1
    assert str(sentinel_file) in probe.sentinel_found
