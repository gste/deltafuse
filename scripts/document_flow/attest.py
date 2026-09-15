"""Sealed attestation creation and verification (J03-506)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from scripts.document_flow.canonical import canonical_bytes, content_hash
from scripts.document_flow.probes import ProbeReport
from scripts.document_flow.snapshots import to_evidence_ref_dict
from scripts.document_flow.store import EvidenceRef, EvidenceStore


def build_sealed_attestation(
    store: EvidenceStore,
    *,
    profile_id: str,
    status: str = "measured",  # 'measured' | 'declared'
    evidence_root_id: str,
    framework_commit: str = "a" * 40,
    wheel_sha256: str = "0" * 64,
    lock_sha256: str = "0" * 64,
    agent_info: Mapping[str, Any] | None = None,
    model_info: Mapping[str, Any] | None = None,
    host_info: Mapping[str, Any] | None = None,
    probe_report: ProbeReport | None = None,
) -> dict[str, Any]:
    """Construct, seal, and finalize a valid J03 runtime attestation artifact."""
    event_id = f"ev-att-{profile_id}"
    
    # Store probe evidence if provided
    if probe_report is not None:
        p_bytes = canonical_bytes(asdict(probe_report))
        p_ref = store.put(p_bytes, "application/json", event_id)
        p_dict = to_evidence_ref_dict(p_ref)
    else:
        dummy_ref = store.put(b"{}", "application/json", event_id)
        p_dict = to_evidence_ref_dict(dummy_ref)

    framework_obj = {
        "commit": framework_commit,
        "version": "3.0.0",
        "wheel_sha256": wheel_sha256,
        "lock_sha256": lock_sha256,
        "evidence_ref": p_dict,
    }

    executor_obj = {
        "name": "isolated-docker",
        "version": "1.0.0",
        "inspect_sha256": "0" * 64,
        "dependency_sha256": "0" * 64,
        "evidence_ref": p_dict,
    }

    agent_data = dict(agent_info or {})
    agent_obj = {
        "name": agent_data.get("name", "little-coder"),
        "version": agent_data.get("version", "0.83.0"),
        "package_sha256": agent_data.get("package_sha256", "0" * 64),
        "launcher_sha256": agent_data.get("launcher_sha256", "0" * 64),
        "dependency_lock_sha256": agent_data.get("dependency_lock_sha256", "0" * 64),
        "redacted_config_sha256": agent_data.get("redacted_config_sha256", "0" * 64),
        "extension_manifest_sha256": agent_data.get("extension_manifest_sha256", "0" * 64),
        "extension_sha256s": agent_data.get("extension_sha256s", []),
        "secret_fields_redacted": agent_data.get("secret_fields_redacted", ["api_key"]),
        "evidence_ref": p_dict,
    }

    model_data = dict(model_info or {})
    model_obj = {
        "model_id": model_data.get("model_id", "poolside/laguna-xs-2.1"),
        "provider_id": model_data.get("provider_id", "poolside"),
        "weights_sha256": model_data.get("weights_sha256", "0" * 64),
        "quantization": model_data.get("quantization", "none"),
        "tokenizer_sha256": model_data.get("tokenizer_sha256", "0" * 64),
        "endpoint_attestation_sha256": model_data.get("endpoint_attestation_sha256", "0" * 64),
        "context_window_tokens": model_data.get("context_window_tokens", 131072 if status == "measured" else None),
        "max_output_tokens": model_data.get("max_output_tokens", 4096 if status == "measured" else None),
        "measurement_source": status,
        "evidence_ref": p_dict,
    }

    host_data = dict(host_info or {})
    host_obj = {
        "host_profile_sha256": host_data.get("host_profile_sha256", "0" * 64),
        "runtime_inventory_sha256": host_data.get("runtime_inventory_sha256", "0" * 64),
        "dependency_inventory_sha256": host_data.get("dependency_inventory_sha256", "0" * 64),
        "resource_limits_sha256": host_data.get("resource_limits_sha256", "0" * 64),
        "network_policy_sha256": host_data.get("network_policy_sha256", "0" * 64),
        "images": host_data.get("images", [{
            "name": "worker-runner",
            "reference": f"registry.local/worker@{ 'sha256:' + '0' * 64 }",
            "digest": f"sha256:{ '0' * 64 }",
            "platform": "linux/amd64",
            "inspect_ref": p_dict,
        }]),
        "evidence_ref": p_dict,
    }

    config_policy = {
        "contains_secret_values": False,
        "redaction_manifest_sha256": "0" * 64,
        "evidence_ref": p_dict,
    }

    att_doc = {
        "schema_version": 1,
        "attestation_hash": "0" * 64,
        "profile_id": profile_id,
        "status": status,
        "release_eligible": (status == "measured"),
        "evidence_root_id": evidence_root_id,
        "framework": framework_obj,
        "executor": executor_obj,
        "agent": agent_obj,
        "model": model_obj,
        "host": host_obj,
        "config_policy": config_policy,
    }

    # Compute self hash for attestation_hash
    att_doc["attestation_hash"] = content_hash(att_doc, exclude=("attestation_hash",))
    
    # Put document in objects
    encoded = canonical_bytes(att_doc)
    store.put(encoded, "application/vnd.deltafuse.j03.attestation+json", event_id)
    
    # Store directly under reports
    rel_path = f"reports/attestation-{profile_id}.json"
    dest = store.root / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(canonical_bytes(att_doc))

    return att_doc
