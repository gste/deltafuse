"""Re-evaluate runs from source artifacts and evidence store (J03-408)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from scripts.document_flow.canonical import canonical_bytes, content_hash, with_self_hash
from scripts.document_flow.evaluate import (
    CheckFact,
    EvaluationError,
    RunSummary,
    StageFactors,
    evaluate_run,
)
from scripts.document_flow.registry import FrozenRegistry, load_registry
from scripts.document_flow.store import EvidenceStore, IntegrityError


class ReplayError(ValueError):
    """Raised when re-evaluating run artifacts violates semantic integrity."""


@dataclass(frozen=True)
class ReplayResult:
    summary: RunSummary
    semantic_result_hash: str
    run_report: dict[str, Any]
    re_evaluated: bool


def _load_canonical_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReplayError(f"missing json artifact: {path}")
    data = path.read_bytes()
    try:
        val = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise ReplayError(f"invalid json in {path}") from exc
    if not isinstance(val, dict):
        raise ReplayError(f"json root is not an object in {path}")
    return val


def reevaluate_run_from_store(
    store: EvidenceStore,
    registry: FrozenRegistry | None = None,
    *,
    registry_path: Path | str = "scripts/document_flow/contracts/checks.json",
) -> ReplayResult:
    """Reconstruct all check facts, stage factors, and run score from disk artifacts."""
    if registry is None:
        registry = load_registry(registry_path)

    # 1. Read and verify all 7 stage reports
    check_facts: list[CheckFact] = []
    stage_factors_map: dict[str, StageFactors] = {}
    validity_failures: list[str] = []
    failure_classes: list[str] = []

    seen_check_ids: set[str] = set()

    for stage_name in registry.stages:
        stage_file = store.root / "stages" / f"{stage_name}.json"
        if not stage_file.is_file():
            # Missing stage file -> invalidity or failed
            validity_failures.append("provenance-invalid")
            continue
        
        stage_doc = _load_canonical_json(stage_file)
        
        # Verify self hash
        if stage_doc.get("report_hash") != content_hash(stage_doc, exclude=("report_hash",)):
            raise ReplayError(f"stage report self-hash mismatch: {stage_name}")

        status = stage_doc.get("status")
        if status == "invalid":
            validity_failures.append("provenance-invalid")

        # Extract checks
        for c in stage_doc.get("checks", []):
            cid = c.get("check_id")
            cstatus = c.get("status", "fail")
            ev_refs = tuple(
                ref.get("key") if isinstance(ref, dict) else str(ref)
                for ref in c.get("evidence_refs", [])
            )
            if cid in seen_check_ids:
                raise ReplayError(f"duplicate check in replay: {cid}")
            seen_check_ids.add(cid)
            check_facts.append(CheckFact(check_id=cid, status=cstatus, evidence_refs=ev_refs if ev_refs else None))

        # Extract measurements / factors
        meas = stage_doc.get("measurements", {})
        prov_refs = tuple(
            ref.get("key") if isinstance(ref, dict) else str(ref)
            for ref in meas.get("provenance_refs", [])
        )
        
        # Derive factors or construct StageFactors
        from scripts.document_flow.efficiency import compute_stage_factors
        s_factors = compute_stage_factors(meas, stage=stage_name, provenance_refs=prov_refs)
        stage_factors_map[stage_name] = s_factors

    # 2. System report
    system_file = store.root / "reports" / "system.json"
    system_failed = False
    if system_file.is_file():
        system_doc = _load_canonical_json(system_file)
        if system_doc.get("report_hash") != content_hash(system_doc, exclude=("report_hash",)):
            raise ReplayError("system report self-hash mismatch")
        for c in system_doc.get("checks", []):
            cid = c.get("check_id")
            cstatus = c.get("status", "fail")
            ev_refs = tuple(
                ref.get("key") if isinstance(ref, dict) else str(ref)
                for ref in c.get("evidence_refs", [])
            )
            if cid in seen_check_ids:
                raise ReplayError(f"duplicate check in replay: {cid}")
            seen_check_ids.add(cid)
            check_facts.append(CheckFact(check_id=cid, status=cstatus, evidence_refs=ev_refs if ev_refs else None))
        if system_doc.get("status") == "failed":
            system_failed = True
    else:
        # Fill missing system checks as not_reached or fail
        for chk in registry.checks:
            if chk.category == "system" and chk.id not in seen_check_ids:
                check_facts.append(CheckFact(check_id=chk.id, status="not_reached", evidence_refs=None))
                seen_check_ids.add(chk.id)

    # 3. Fill any missing stage checks as not_reached
    for chk in registry.checks:
        if chk.id not in seen_check_ids:
            check_facts.append(CheckFact(check_id=chk.id, status="not_reached", evidence_refs=None))
            seen_check_ids.add(chk.id)

    # Fill missing stage factors if any stage missing
    for stg in registry.stages:
        if stg not in stage_factors_map:
            stage_factors_map[stg] = StageFactors(None, None, None, None, None)

    # 4. Absolute gates
    absolute_gates = {gate: True for gate in registry.hard_gate_ids}
    # Check if any hard gate check failed
    for fact in check_facts:
        if fact.check_id in absolute_gates and fact.status != "pass":
            absolute_gates[fact.check_id] = False

    # 5. Evaluate
    summary = evaluate_run(
        registry,
        check_facts,
        stage_factors_map,
        absolute_gates,
        functional_system_failure=system_failed,
        validity_failures=validity_failures,
        failure_classes=failure_classes,
    )

    # Semantic result hash
    semantic_dict = {
        "status": summary.status,
        "raw_score": summary.raw_score,
        "final_score": summary.final_score,
        "release_verdict": summary.release_verdict,
        "first_failure": summary.first_failure,
        "hard_failures": list(summary.hard_failures),
        "applied_ceilings": [{"kind": c.kind, "limit": c.limit} for c in summary.applied_ceilings],
    }
    semantic_hash = content_hash(semantic_dict)

    # Construct or verify run report
    run_file = store.root / "reports" / "run.json"
    if run_file.is_file():
        stored_run = _load_canonical_json(run_file)
        # Verify self hash
        if stored_run.get("report_hash") != content_hash(stored_run, exclude=("report_hash",)):
            raise ReplayError("stored run.json report_hash mismatch")
        # Compare derived fields with stored fields
        if stored_run.get("status") != summary.status:
            raise ReplayError(f"stored status mismatch: {stored_run.get('status')} vs derived {summary.status}")
        if stored_run.get("raw_score") != summary.raw_score:
            raise ReplayError(f"stored raw_score mismatch: {stored_run.get('raw_score')} vs derived {summary.raw_score}")
        if stored_run.get("final_score") != summary.final_score:
            raise ReplayError(f"stored final_score mismatch: {stored_run.get('final_score')} vs derived {summary.final_score}")
        if stored_run.get("release_verdict") != summary.release_verdict:
            raise ReplayError(f"stored release_verdict mismatch: {stored_run.get('release_verdict')} vs derived {summary.release_verdict}")
        run_report = stored_run
    else:
        run_report = semantic_dict

    return ReplayResult(
        summary=summary,
        semantic_result_hash=semantic_hash,
        run_report=run_report,
        re_evaluated=True,
    )
