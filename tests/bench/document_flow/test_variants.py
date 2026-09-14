"""Determinism, causality and corpus tests for the J03 variant generator.

The named checks mirror the card's Red: the same seed must produce the same
stream under different interpreter hash seeds (cross-runtime determinism),
a valid scenario must never contain an invalid actor reuse, and generated
identities must not be static public fixture ids. The golden hash pins one
calibration seed byte-for-byte.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from scripts.document_flow import variants

REPO_ROOT = Path(__file__).parents[3]
CASE_ROOT = REPO_ROOT / "process/bench/cases/J03-document-flow"
CONTRACT = CASE_ROOT / "oracle/variant-contract.json"
VARIANT_SCHEMA = REPO_ROOT / "scripts/document_flow/schemas/variant.schema.json"

FIXTURE_PUBLIC_IDS = {"pub-doc-approve", "pub-doc-reject", "pub-ver-approve-1",
                      "pub-ver-reject-1", "pub-dec-approve-1", "pub-dec-reject-1"}


def _stream_bytes(seed: int) -> bytes:
    operations = variants.generate_operations(seed, CONTRACT)
    return variants.canonical_stream(operations)


def test_same_seed_reproduces_identical_stream_across_hash_seeds():
    baseline = _stream_bytes(20260914)
    for hash_seed in ("0", "1", "12345", "random"):
        environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
        finished = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s');"
             "from scripts.document_flow import variants;"
             "sys.stdout.buffer.write(variants.canonical_stream("
             "variants.generate_operations(20260914, r'%s')))"
             % (REPO_ROOT, CONTRACT)],
            capture_output=True, timeout=120, env=environment)
        assert finished.returncode == 0, finished.stderr
        assert finished.stdout == baseline, (
            "same seed produced a different stream under PYTHONHASHSEED="
            + hash_seed)


def test_golden_calibration_seed_matches_recorded_hash():
    digest = hashlib.sha256(_stream_bytes(1)).hexdigest()
    assert digest == variants.GOLDEN_STREAM_SHA256[1]


def test_different_seeds_change_identities_and_schedules():
    hashes = set()
    identities = set()
    for seed in (1, 2, 3, 4, 5):
        operations = variants.generate_operations(seed, CONTRACT)
        hashes.add(hashlib.sha256(variants.canonical_stream(operations)).hexdigest())
        for operation in operations:
            for key in ("document_id", "version_id", "route_id", "decision_id"):
                value = operation.get(key)
                if value:
                    identities.add(value)
    assert len(hashes) == 5, "distinct calibration seeds produced identical streams"
    assert len(identities) >= 5 * 4, "generated identities collide across seeds"


def test_generated_ids_are_not_static_public_fixture_ids():
    for seed in (1, 2, 3):
        for operation in variants.generate_operations(seed, CONTRACT):
            for key in ("document_id", "version_id", "route_id", "decision_id",
                        "actor_id"):
                assert operation.get(key) not in FIXTURE_PUBLIC_IDS, (
                    "generator leaked a static fixture id: %s" % operation)


def test_valid_scenarios_never_reuse_an_actor_across_expert_roles():
    for seed in variants.CORPUS_SEEDS:
        operations = variants.generate_operations(seed, CONTRACT)
        expert_actors: dict[str, set[str]] = {}
        for operation in operations:
            if (operation["kind"] != "decision"
                    or operation.get("valid") is not True
                    or operation.get("label") is not None):
                continue  # labeled invalid/replay schedules are not scored
            if operation["role"] in ("legal", "security"):
                # DEC-B: role separation binds within one route; the same
                # actor may hold the same role again on a successor route.
                previous = expert_actors.setdefault(operation["route_id"],
                                                    set())
                assert operation["actor_id"] not in previous, (
                    "actor reused across expert roles in a valid decision: %s"
                    % operation)
                previous.add(operation["actor_id"])


def test_invalid_schedules_are_labeled_and_causally_possible():
    labeled = 0
    for seed in variants.CORPUS_SEEDS:
        for operation in variants.generate_operations(seed, CONTRACT):
            if operation.get("valid") is False:
                labeled += 1
                assert operation.get("label") in variants.INVALID_LABELS
                assert operation.get("expected_code")
    assert labeled >= len(variants.CORPUS_SEEDS), (
        "every variant must contain at least one deliberate invalid schedule")


def test_stream_is_causally_ordered_per_document():
    for seed in variants.CORPUS_SEEDS:
        created = set()
        submitted = set()
        routes = set()
        superseded = set()
        decided = set()
        for operation in variants.generate_operations(seed, CONTRACT):
            document = operation.get("document_id")
            if operation["kind"] == "http" and operation["op"] == "create-document":
                created.add(document)
            elif operation["kind"] == "http" and operation["op"] == "create-version":
                assert document in created
            elif operation["kind"] == "http" and operation["op"] == "submit-version":
                assert document in created
                submitted.add((document, operation["version_id"]))
            elif operation["kind"] == "delivery" and operation["op"] == "route-created":
                assert (document, operation["version_id"]) in submitted
                routes.add(operation["route_id"])
            elif operation["kind"] == "decision":
                if operation["route_id"] in superseded:
                    assert operation.get("valid") is False, operation
                else:
                    assert operation["route_id"] in routes, operation
                if operation.get("valid") is True and operation.get("label") is None:
                    decided.add(operation["route_id"])
            elif operation["kind"] == "delivery" and operation["op"] == "route-superseded":
                superseded.add(operation["route_id"])
                assert operation["route_id"] in routes
            elif operation["kind"] == "crash":
                assert operation["point"] in variants.CRASH_POINTS


def _validate_manifest(manifest: dict) -> None:
    import referencing
    import referencing.jsonschema
    schemas = REPO_ROOT / "scripts/document_flow/schemas"
    evidence = json.loads(
        (schemas / "evidence-ref.schema.json").read_text(encoding="utf-8"))
    schema = json.loads(VARIANT_SCHEMA.read_text(encoding="utf-8"))
    registry = referencing.Registry().with_resources([
        ("urn:deltafuse:j03:evidence-ref:1",
         referencing.jsonschema.DRAFT202012.create_resource(evidence)),
    ])
    jsonschema.validate(manifest, schema, registry=registry)


def test_manifest_binds_seed_generator_and_contract():
    contract_bytes = CONTRACT.read_bytes()
    source_sha = variants.source_sha256()
    manifest = variants.build_manifest(4, CONTRACT,
                                       source_revision="a" * 40)
    _validate_manifest(manifest)
    assert manifest["seed"] == 4
    assert manifest["generator"]["source_revision"] == "a" * 40
    assert manifest["generator"]["source_sha256"] == source_sha
    assert manifest["generator"]["contract_sha256"] == (
        hashlib.sha256(contract_bytes).hexdigest())
    stream = manifest["operation_stream"]
    operations = variants.generate_operations(4, CONTRACT)
    assert stream["operation_count"] == len(operations)
    payload = variants.canonical_stream(operations)
    assert stream["sha256"] == hashlib.sha256(payload).hexdigest()
    assert stream["evidence_ref"]["byte_length"] == len(payload)
    assert manifest["manifest_hash"] == variants.manifest_hash(manifest)
    assert manifest["ambiguity_ids"] and manifest["workload_ids"]


def test_corpus_is_frozen_and_split():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    corpus = contract["corpus"]
    assert variants.CORPUS_SEEDS == (
        sorted(corpus["calibration_seeds"] + corpus["heldout_seeds"]))
    assert not set(corpus["calibration_seeds"]) & set(corpus["heldout_seeds"])
    assert len(corpus["heldout_seeds"]) >= 3


def test_duplicate_deliveries_never_introduce_new_state():
    for seed in variants.CORPUS_SEEDS:
        operations = variants.generate_operations(seed, CONTRACT)
        for operation in operations:
            if operation["kind"] == "duplicate-delivery":
                assert operation.get("valid") is True
                assert operation.get("label") == "duplicate-delivery"
                originals = [candidate for candidate in operations
                             if candidate["kind"] == "delivery"
                             and candidate["op"] == operation["op"]
                             and candidate.get("event_id") == operation.get("event_id")]
                assert originals, "duplicate delivery without an original"
