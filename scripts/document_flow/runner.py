"""End-to-end benchmark run execution orchestrator (J03-507)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.document_flow.attest import build_sealed_attestation
from scripts.document_flow.canonical import canonical_bytes, with_self_hash
from scripts.document_flow.preflight import run_preflight_checks
from scripts.document_flow.probes import run_local_adversarial_probe
from scripts.document_flow.registry import load_registry
from scripts.document_flow.replay import reevaluate_run_from_store
from scripts.document_flow.reports import render_run_markdown
from scripts.document_flow.snapshots import (
    finalize_stage_rollups,
    record_stage_visit,
    take_stage_snapshot,
)
from scripts.document_flow.store import EvidenceStore


class RunnerError(RuntimeError):
    """Raised when benchmark runner encounters an unrecoverable failure."""


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    status: str
    score: int | None
    verdict: str
    output_dir: Path


def execute_benchmark_run(
    *,
    run_id: str,
    output_dir: Path | str,
    sandbox_dir: Path | str,
    profile_id: str = "default-profile",
    root_id: str = "root-1",
    preflight_only: bool = False,
    fail_on_preflight: bool = True,
) -> RunOutcome:
    """Execute preflight, initialize evidence store, run lifecycle stages, and seal results."""
    out_path = Path(output_dir).resolve()
    s_path = Path(sandbox_dir).resolve()

    if out_path.exists() and any(out_path.iterdir()):
        raise RunnerError(f"output directory is not empty: {out_path}")

    # 1. Preflight
    preflight = run_preflight_checks()
    if not preflight.ok and fail_on_preflight:
        raise RunnerError(f"preflight checks failed: {'; '.join(preflight.failures)}")

    if preflight_only:
        return RunOutcome(run_id=run_id, status="preflight_passed", score=None, verdict="none", output_dir=out_path)

    # 2. Store creation
    store = EvidenceStore.create(out_path, run_id, root_id)

    # 3. Preflight probe & attestation
    probe = run_local_adversarial_probe(
        sandbox_root=s_path,
        sentinel_path=out_path / "sentinel.txt",
        phase="preflight",
    )
    att_doc = build_sealed_attestation(
        store,
        profile_id=profile_id,
        status="measured",
        evidence_root_id=root_id,
        probe_report=probe,
    )

    # Dummy initial snapshot
    snap, s_ref = take_stage_snapshot(s_path, stage="intake", store=store, producer_event_id="ev-init")

    # Record visits
    v_rec = record_stage_visit(
        store,
        visit_id="visit-intake-1",
        stage="intake",
        snapshot_ref=s_ref,
        start_event_seq=0,
        end_event_seq=1,
    )

    # Finalize stage rollups
    identity = {
        "campaign_id": "camp-1",
        "run_id": run_id,
        "case_id": "J03-document-flow",
        "variant_id": "var-1",
        "session_id": "sess-1",
        "sandbox_id": "sand-1",
        "profile_sha256": "0" * 64,
        "contract_sha256": "0" * 64,
        "registry_sha256": "0" * 64,
        "host_profile_sha256": "0" * 64,
        "endpoint_attestation_ref": att_doc["framework"]["evidence_ref"],
    }

    finalize_stage_rollups(
        store,
        identity=identity,
        stage_visits={"intake": [v_rec]},
        attestation_refs=[att_doc["framework"]["evidence_ref"]],
    )

    # 4. Replay from store to compute final verdict
    replay = reevaluate_run_from_store(store)

    return RunOutcome(
        run_id=run_id,
        status=replay.summary.status,
        score=replay.summary.final_score,
        verdict=replay.summary.release_verdict,
        output_dir=out_path,
    )
