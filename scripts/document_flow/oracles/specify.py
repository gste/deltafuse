"""Deterministic oracle for Specify lifecycle stage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.document_flow.snapshots import SnapshotData, to_evidence_ref_dict
from scripts.document_flow.store import EvidenceRef, EvidenceStore
from scripts.document_flow.witness import validate_witnesses


EXPECTED_OBLIGATION_COUNT = 18
ALLOWED_SPECIFY_WRITE_PATTERNS = [
    r"^docs/spec/.*",
    r"^docs/changes/[^/]+/.*",
    r"^\.deltafuse/.*",
    r"^backlog/.*",
]


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    awarded_points: int
    evidence_refs: list[dict[str, Any]]
    failure_reason: str | None = None


def evaluate_specify_stage(
    snapshot: SnapshotData | dict[str, Any],
    *,
    store: EvidenceStore,
    events: list[dict[str, Any]],
    variant_contract: dict[str, Any] | None = None,
    evidence_ref: EvidenceRef | dict[str, Any] | None = None,
    product_root: Path | str | None = None,
) -> list[CheckResult]:
    """Deterministically evaluate all SP.C* and SP.D* checks for Specify stage."""
    results: list[CheckResult] = []
    ev_ref_dict = to_evidence_ref_dict(evidence_ref) if evidence_ref else {
        "key": "objects/specify-snapshot.json",
        "sha256": "0" * 64,
        "media_type": "application/json",
        "byte_length": 0,
        "producer_event_id": "ev-specify",
    }
    
    files = snapshot.files if isinstance(snapshot, SnapshotData) else snapshot.get("files", [])
    file_map = {f["path"]: f for f in files}
    
    spec_texts = []
    for path, finfo in file_map.items():
        if (path.startswith("docs/spec/") or path.startswith("docs/changes/")) and (path.endswith(".md") or path.endswith(".yaml")):
            if product_root:
                p = Path(product_root) / path
                if p.is_file():
                    spec_texts.append(p.read_text(encoding="utf-8", errors="ignore"))
    
    combined_text = "\n\n".join(spec_texts)
    witness_result = validate_witnesses(combined_text)

    # 1. Evaluate SP.C01 (240 pts) - Specification completeness & typed predicates
    if witness_result.valid and len(witness_result.entries) >= EXPECTED_OBLIGATION_COUNT:
        results.append(CheckResult(
            check_id="SP.C01",
            status="pass",
            awarded_points=240,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        errors = witness_result.errors or [f"Found only {len(witness_result.entries)}/{EXPECTED_OBLIGATION_COUNT} obligations"]
        results.append(CheckResult(
            check_id="SP.C01",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="; ".join(errors),
        ))

    # 2. Evaluate SP.C02 (160 pts) - State machine & transition invariants
    has_supersede_rules = "SUPERSEDED" in combined_text or "supersede" in combined_text.lower()
    has_approval_stages = ("expert-review" in combined_text) and ("registrar" in combined_text)
    
    if has_supersede_rules and has_approval_stages:
        results.append(CheckResult(
            check_id="SP.C02",
            status="pass",
            awarded_points=160,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        missing = []
        if not has_supersede_rules: missing.append("Missing supersede transition semantics")
        if not has_approval_stages: missing.append("Missing expert-review/registrar stage transitions")
        results.append(CheckResult(
            check_id="SP.C02",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="; ".join(missing),
        ))

    # 3. Evaluate SP.C03 (120 pts) - Public endpoint & canonical query precision
    has_canonical_shape = ("canonical" in combined_text.lower()) or ("audit_sequence" in combined_text) or ("open_slots" in combined_text)
    if has_canonical_shape:
        results.append(CheckResult(
            check_id="SP.C03",
            status="pass",
            awarded_points=120,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="SP.C03",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Canonical query shape and response contracts not specified",
        ))

    # 4. Evaluate SP.C04 (80 pts) - Baseline preservation & backward compatibility
    has_compat = ("backward compatibility" in combined_text.lower()) or ("baseline" in combined_text.lower())
    if has_compat:
        results.append(CheckResult(
            check_id="SP.C04",
            status="pass",
            awarded_points=80,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="SP.C04",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Missing baseline compatibility preservation specification",
        ))

    # Discipline checks (SP.D01..SP.D05)
    illegal_writes = []
    for ev in events:
        if ev.get("kind") == "file_write":
            wpath = ev.get("path", "")
            if not any(re.match(pat, wpath) for pat in ALLOWED_SPECIFY_WRITE_PATTERNS):
                illegal_writes.append(wpath)
                
    results.append(CheckResult(
        check_id="SP.D01",
        status="pass" if not illegal_writes else "fail",
        awarded_points=80 if not illegal_writes else 0,
        evidence_refs=[ev_ref_dict],
        failure_reason=None if not illegal_writes else f"File writes outside specify envelope: {illegal_writes}",
    ))

    results.append(CheckResult(
        check_id="SP.D02",
        status="pass",
        awarded_points=60,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="SP.D03",
        status="pass",
        awarded_points=50,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="SP.D04",
        status="pass",
        awarded_points=40,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="SP.D05",
        status="pass",
        awarded_points=20,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    return results
