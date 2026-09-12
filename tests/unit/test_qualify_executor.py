"""QF-013: release qualification requires an isolated Worker executor.

Red evidence for the current fail-open boundary: the in-process runner can
produce a release verdict while Worker-authored pytest runs with runner
rights. The unit tests here pin the fail-closed gating that must hold on any
host; the actual boundary adversarial matrix lives in
tests/integration/test_qualify_boundary.py and requires a container runtime.
"""

from __future__ import annotations

import json

import pytest

import sys

sys.path.insert(0, "scripts")

import qualify  # noqa: E402
import qualify_executor  # noqa: E402


def test_default_executor_mode_is_isolated():
    """A release campaign must not silently fall back to in-process exec."""
    parser = qualify.build_arg_parser()
    assert parser.get_default("executor") == "isolated"


def test_isolated_unavailable_is_pending_before_worker_calls(tmp_path, monkeypatch, capsys):
    """No isolated boundary -> PENDING exit 2 before any Worker call."""
    monkeypatch.setattr(qualify_executor.IsolatedExecutor, "available", lambda self: False)
    monkeypatch.setattr(qualify, "provenance",
                        lambda: {"commit": "a" * 40, "lock_hash": "sha256:x",
                                 "thresholds_revision": "r1"})
    monkeypatch.setattr(qualify, "RUNS_DIR", tmp_path / "bench" / "runs")
    exit_code = qualify.main_with_args(["--executor", "isolated"])
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "PENDING" in out
    assert not (tmp_path / "bench" / "runs").exists()


def test_resolve_executor_rejects_unknown_mode():
    with pytest.raises(qualify_executor.ExecutorError):
        qualify_executor.resolve_executor("wat")


def test_local_dev_green_scorecard_cannot_release_pass():
    """local-dev caps the campaign at non-release even with green runs."""
    manifest = {
        "verdict": "pass",
        "case_verdicts": {"M01-cooldown": {"verdict": "pass"}},
        "runs": [],
    }
    qualify_executor.apply_executor_verdict_cap(manifest, "local-dev")
    assert manifest["verdict"] == "non-release"


def test_isolated_mode_allows_release_pass():
    manifest = {
        "verdict": "pass",
        "case_verdicts": {"M01-cooldown": {"verdict": "pass"}},
        "runs": [],
    }
    qualify_executor.apply_executor_verdict_cap(manifest, "isolated")
    assert manifest["verdict"] == "pass"


def test_manifest_executor_attestation_shape():
    """Every executor attestation field carries provenance (QF-007 style)."""
    executor = qualify_executor.LocalDevExecutor()
    attestation = executor.attest()
    assert attestation["kind"]["value"] == "local-dev"
    assert attestation["kind"]["provenance"] in ("declared", "measured")
    for key in ("kind", "boundary", "network_policy"):
        assert key in attestation


def test_manifest_without_executor_block_fails_schema():
    """The manifest schema requires the executor attestation block."""
    manifest = {
        "schema_version": 1,
        "campaign_id": "c",
        "created": "2026-09-13T00:00:00Z",
        "framework": {"commit": "a" * 40, "lock_hash": "sha256:" + "0" * 64},
        "model": {},
        "thresholds": {
            "source": "s", "revision": "r",
            "absolute": {
                "correctness_failed": 0, "stages_completed": 7,
                "gate_retries_max": 2, "context_peak_tokens_max": 32768,
                "framework_input_tokens_max": 16000, "max_unique_files": 24,
                "hallucinated_paths": 0, "envelope_violations": 0,
                "evidence_authentic": True,
            },
        },
        "cases": ["M01-cooldown"],
        "runs": [],
        "case_verdicts": {},
        "verdict": "non-release",
    }
    with pytest.raises(qualify.SchemaValidationError, match="executor"):
        qualify.validate_document("run-manifest", manifest)


def test_manifest_schema_accepts_non_release_verdict(tmp_path):
    manifest = {
        "schema_version": 1,
        "campaign_id": "c",
        "created": "2026-09-13T00:00:00Z",
        "framework": {"commit": "a" * 40, "lock_hash": "sha256:" + "0" * 64},
        "model": {},
        "thresholds": {
            "source": "s", "revision": "r",
            "absolute": {
                "correctness_failed": 0, "stages_completed": 7,
                "gate_retries_max": 2, "context_peak_tokens_max": 32768,
                "framework_input_tokens_max": 16000, "max_unique_files": 24,
                "hallucinated_paths": 0, "envelope_violations": 0,
                "evidence_authentic": True,
            },
        },
        "executor": {
            "kind": {"value": "local-dev", "provenance": "declared", "basis": "b"},
            "boundary": {"value": "in-process", "provenance": "declared", "basis": "b"},
            "network_policy": {"value": "none", "provenance": "declared", "basis": "b"},
        },
        "cases": ["M01-cooldown"],
        "runs": [],
        "case_verdicts": {},
        "verdict": "non-release",
    }
    qualify.validate_document("run-manifest", manifest)


def test_boundary_probe_flags_leak():
    """The adversarial probe must turn any leak into a blocking failure."""
    leaked = {"sentinel_read": "LEAK", "pack_found": [], "write_leak": [], "network": "blocked"}
    with pytest.raises(qualify_executor.BoundaryViolation):
        qualify_executor.assert_boundary_clean(leaked)
    clean = {"sentinel_read": "blocked", "pack_found": [], "write_leak": [], "network": "blocked"}
    qualify_executor.assert_boundary_clean(clean)
