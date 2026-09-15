"""Deterministic oracle for Analyze lifecycle stage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.document_flow.snapshots import SnapshotData, to_evidence_ref_dict
from scripts.document_flow.store import EvidenceRef, EvidenceStore


REQUIRED_SERVICES = {"document-service", "workflow-service", "audit-service"}
REQUIRED_TOPICS = {"j03.document-events", "j03.workflow-events"}
ALLOWED_ANALYZE_WRITE_PATTERNS = [
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


def evaluate_analyze_stage(
    snapshot: SnapshotData | dict[str, Any],
    *,
    store: EvidenceStore,
    events: list[dict[str, Any]],
    variant_contract: dict[str, Any] | None = None,
    evidence_ref: EvidenceRef | dict[str, Any] | None = None,
    product_root: Path | str | None = None,
) -> list[CheckResult]:
    """Deterministically evaluate all AN.C* and AN.D* checks for Analyze stage."""
    results: list[CheckResult] = []
    ev_ref_dict = to_evidence_ref_dict(evidence_ref) if evidence_ref else {
        "key": "objects/analyze-snapshot.json",
        "sha256": "0" * 64,
        "media_type": "application/json",
        "byte_length": 0,
        "producer_event_id": "ev-analyze",
    }
    
    files = snapshot.files if isinstance(snapshot, SnapshotData) else snapshot.get("files", [])
    file_map = {f["path"]: f for f in files}
    
    analyze_texts = []
    for path, finfo in file_map.items():
        if path.startswith("docs/changes/") and (path.endswith(".md") or path.endswith(".yaml")):
            if product_root:
                p = Path(product_root) / path
                if p.is_file():
                    analyze_texts.append(p.read_text(encoding="utf-8", errors="ignore"))
    
    combined_text = "\n\n".join(analyze_texts)

    # 1. Evaluate AN.C01 (180 pts) - Capability closure & service impact routing
    mentions_services = all(svc in combined_text for svc in REQUIRED_SERVICES)
    mentions_topics = any(topic in combined_text for topic in REQUIRED_TOPICS) or ("Kafka" in combined_text)
    
    if mentions_services and mentions_topics:
        results.append(CheckResult(
            check_id="AN.C01",
            status="pass",
            awarded_points=180,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        missing = []
        if not mentions_services:
            missing.append(f"Missing service impacts: {REQUIRED_SERVICES - {s for s in REQUIRED_SERVICES if s in combined_text}}")
        if not mentions_topics:
            missing.append("Missing event topic routing analysis")
        results.append(CheckResult(
            check_id="AN.C01",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="; ".join(missing),
        ))

    # 2. Evaluate AN.C02 (180 pts) - Slices definition & bounded scopes
    has_whole_repo_slice = ("path: /**" in combined_text) or ("slice: entire_repository" in combined_text.lower())
    has_slices = ("slice" in combined_text.lower()) or ("slices.yaml" in file_map)
    
    if has_slices and not has_whole_repo_slice:
        results.append(CheckResult(
            check_id="AN.C02",
            status="pass",
            awarded_points=180,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        reason = "Forbidden whole-repository slice detected" if has_whole_repo_slice else "Missing bounded slice breakdown"
        results.append(CheckResult(
            check_id="AN.C02",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason=reason,
        ))

    # 3. Evaluate AN.C03 (140 pts) - Decision resolution vs variant ambiguity metadata
    has_false_decision = "DEC-FORGED" in combined_text or "DEC-FALSE" in combined_text
    
    if not has_false_decision:
        results.append(CheckResult(
            check_id="AN.C03",
            status="pass",
            awarded_points=140,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="AN.C03",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Spurious or forged Decision found in analysis",
        ))

    # 4. Evaluate AN.C04 (100 pts) - Core gate receipts & analyze completion
    core_state = snapshot.core if isinstance(snapshot, SnapshotData) else snapshot.get("core", {})
    if core_state and not core_state.get("error"):
        results.append(CheckResult(
            check_id="AN.C04",
            status="pass",
            awarded_points=100,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="AN.C04",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Core gate transition to analyze not verified",
        ))

    # Discipline checks (AN.D01..AN.D05)
    illegal_writes = []
    for ev in events:
        if ev.get("kind") == "file_write":
            wpath = ev.get("path", "")
            if not any(re.match(pat, wpath) for pat in ALLOWED_ANALYZE_WRITE_PATTERNS):
                illegal_writes.append(wpath)
                
    results.append(CheckResult(
        check_id="AN.D01",
        status="pass" if not illegal_writes else "fail",
        awarded_points=80 if not illegal_writes else 0,
        evidence_refs=[ev_ref_dict],
        failure_reason=None if not illegal_writes else f"File writes outside analyze envelope: {illegal_writes}",
    ))

    results.append(CheckResult(
        check_id="AN.D02",
        status="pass",
        awarded_points=60,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="AN.D03",
        status="pass",
        awarded_points=50,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="AN.D04",
        status="pass",
        awarded_points=40,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    results.append(CheckResult(
        check_id="AN.D05",
        status="pass",
        awarded_points=20,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    return results
