import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path("scripts/document_flow/schemas")
SHA = "c" * 64
COMMIT = "d" * 40


def evidence(key="objects/inspect.json"):
    return {"key": key, "sha256": SHA, "media_type": "application/json", "byte_length": 12, "producer_event_id": "event-1"}


def validator(name):
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "evidence-ref.schema.json", ROOT / name)]
    registry = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in schemas)
    return Draft202012Validator(schemas[-1], registry=registry)


def attestation(status="measured"):
    measured = status == "measured"
    return {
        "schema_version": 1, "attestation_hash": SHA, "profile_id": "profile-1",
        "status": status, "release_eligible": measured, "evidence_root_id": "evidence-root-1",
        "framework": {"commit": COMMIT, "version": "3.0.0", "wheel_sha256": SHA, "lock_sha256": SHA, "evidence_ref": evidence("objects/framework.json")},
        "executor": {"name": "deltafuse", "version": "3.0.0", "inspect_sha256": SHA, "dependency_sha256": SHA, "evidence_ref": evidence("objects/executor.json")},
        "agent": {
            "name": "little-coder", "version": "1.19.0", "package_sha256": SHA, "launcher_sha256": SHA,
            "dependency_lock_sha256": SHA, "redacted_config_sha256": SHA, "extension_manifest_sha256": SHA,
            "extension_sha256s": [SHA], "secret_fields_redacted": ["api_key"], "evidence_ref": evidence("objects/agent.json"),
        },
        "model": {
            "model_id": "poolside/laguna-xs-2.1", "provider_id": "provider-1", "weights_sha256": SHA,
            "quantization": "declared-none", "tokenizer_sha256": SHA, "endpoint_attestation_sha256": SHA,
            "context_window_tokens": 32768 if measured else None, "max_output_tokens": 4096 if measured else None,
            "measurement_source": "measured" if measured else "declared", "evidence_ref": evidence("objects/model.json"),
        },
        "host": {
            "host_profile_sha256": SHA, "runtime_inventory_sha256": SHA, "dependency_inventory_sha256": SHA,
            "resource_limits_sha256": SHA, "network_policy_sha256": SHA,
            "images": [{"name": "postgres", "reference": f"postgres@sha256:{SHA}", "digest": f"sha256:{SHA}", "platform": "linux/amd64", "inspect_ref": evidence("objects/image.json")}],
            "evidence_ref": evidence("objects/host.json"),
        },
        "config_policy": {"contains_secret_values": False, "redaction_manifest_sha256": SHA, "evidence_ref": evidence("objects/redaction.json")},
    }


def variant():
    return {
        "schema_version": 1, "manifest_hash": SHA, "variant_id": "variant-1", "seed": 42,
        "generator": {"source_revision": COMMIT, "source_sha256": SHA, "contract_sha256": SHA},
        "operation_stream": {"sha256": SHA, "operation_count": 8, "evidence_ref": evidence("objects/operations.json")},
        "ambiguity_ids": ["AMB-001"], "workload_ids": ["WORK-001"],
    }


def test_measured_release_attestation_validates():
    validator("attestation.schema.json").validate(attestation())


def test_declared_only_attestation_is_valid_but_non_release():
    fixture = attestation("declared")
    validator("attestation.schema.json").validate(fixture)
    assert fixture["release_eligible"] is False


@pytest.mark.parametrize("mutation", ["tag_only_image", "missing_provider", "unmeasured_context", "secret_value"])
def test_invalid_release_attestations_fail(mutation):
    fixture = attestation()
    if mutation == "tag_only_image": fixture["host"]["images"][0]["reference"] = "postgres:17"
    if mutation == "missing_provider": del fixture["model"]["provider_id"]
    if mutation == "unmeasured_context": fixture["model"]["context_window_tokens"] = None
    if mutation == "secret_value": fixture["agent"]["api_key"] = "not-allowed"
    assert list(validator("attestation.schema.json").iter_errors(fixture))


def test_declared_only_cannot_claim_release_eligibility():
    fixture = attestation("declared")
    fixture["release_eligible"] = True
    assert list(validator("attestation.schema.json").iter_errors(fixture))


def test_reproducible_variant_validates():
    validator("variant.schema.json").validate(variant())


@pytest.mark.parametrize("field", ["sha256", "operation_count", "evidence_ref"])
def test_variant_requires_complete_operation_stream_identity(field):
    fixture = variant()
    del fixture["operation_stream"][field]
    assert list(validator("variant.schema.json").iter_errors(fixture))


def test_variant_rejects_free_form_or_unknown_identity_fields():
    fixture = variant()
    fixture["generator"]["branch_label"] = "latest"
    fixture["seed"] = True
    assert list(validator("variant.schema.json").iter_errors(fixture))
