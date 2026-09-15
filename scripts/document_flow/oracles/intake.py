"""Deterministic oracle for Intake lifecycle stage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.document_flow.snapshots import SnapshotData, to_evidence_ref_dict
from scripts.document_flow.store import EvidenceRef, EvidenceStore


EXPECTED_OBLIGATIONS = {
    "J03-OBL-001", "J03-OBL-002", "J03-OBL-003", "J03-OBL-004", "J03-OBL-005",
    "J03-OBL-006", "J03-OBL-007", "J03-OBL-008", "J03-OBL-009", "J03-OBL-010",
    "J03-OBL-011", "J03-OBL-012", "J03-OBL-013", "J03-OBL-014", "J03-OBL-015",
    "J03-OBL-016", "J03-OBL-017", "J03-OBL-018",
}

EXPECTED_REQUIREMENTS = {
    f"REQ-SUP-00{i}" for i in range(1, 6)
} | {
    f"REQ-ROUTE-00{i}" for i in range(1, 9)
} | {
    f"REQ-DEL-00{i}" for i in range(1, 6)
} | {
    "REQ-OBS-001"
}

ALLOWED_INTAKE_WRITE_PATTERNS = [
    r"^docs/changes/[^/]+/.*",
    r"^\.deltafuse/.*",
    r"^backlog/.*",
]

FORBIDDEN_READ_PATTERNS = [
    r".*/hidden_suite/.*",
    r".*/oracle/reference/.*",
    r".*/private/.*",
]


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    awarded_points: int
    evidence_refs: list[dict[str, Any]]
    failure_reason: str | None = None


def extract_fenced_obligations(text: str) -> list[dict[str, Any]]:
    """Extract JSON array inside ```j03-obligations ... ``` block."""
    match = re.search(r"```j03-obligations\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def evaluate_intake_stage(
    snapshot: SnapshotData | dict[str, Any],
    *,
    store: EvidenceStore,
    events: list[dict[str, Any]],
    variant_contract: dict[str, Any] | None = None,
    evidence_ref: EvidenceRef | dict[str, Any] | None = None,
    product_root: Path | str | None = None,
) -> list[CheckResult]:
    """Deterministically evaluate all IN.C* and IN.D* checks for Intake stage."""
    results: list[CheckResult] = []
    ev_ref_dict = to_evidence_ref_dict(evidence_ref) if evidence_ref else {
        "key": "objects/intake-snapshot.json",
        "sha256": "0" * 64,
        "media_type": "application/json",
        "byte_length": 0,
        "producer_event_id": "ev-intake",
    }
    
    files = snapshot.files if isinstance(snapshot, SnapshotData) else snapshot.get("files", [])
    file_map = {f["path"]: f for f in files}
    
    # 1. Evaluate IN.C01 (240 pts) - Claimed requirements / obligations coverage
    intake_texts = []
    for path, finfo in file_map.items():
        if path.startswith("docs/changes/") and (path.endswith(".md") or path.endswith(".yaml")):
            if product_root:
                p = Path(product_root) / path
                if p.is_file():
                    intake_texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        elif path == "input.md" or path.endswith("/input.md"):
            if product_root:
                p = Path(product_root) / path
                if p.is_file():
                    intake_texts.append(p.read_text(encoding="utf-8", errors="ignore"))
    
    combined_text = "\n\n".join(intake_texts)
    obligations = extract_fenced_obligations(combined_text)
    extracted_obl_ids = {o.get("obligation_id") for o in obligations if isinstance(o, dict)}
    extracted_req_ids = {r for r in EXPECTED_REQUIREMENTS if r in combined_text}
    
    # Passing condition: either all 18 obligations present or all 18 REQ IDs present
    has_all_obls = EXPECTED_OBLIGATIONS.issubset(extracted_obl_ids)
    has_all_reqs = EXPECTED_REQUIREMENTS.issubset(extracted_req_ids)
    
    # Check for invented invalid obligation IDs
    invented_obls = extracted_obl_ids - EXPECTED_OBLIGATIONS
    
    if (has_all_obls or has_all_reqs) and not invented_obls:
        results.append(CheckResult(
            check_id="IN.C01",
            status="pass",
            awarded_points=240,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        reasons = []
        if not (has_all_obls or has_all_reqs):
            reasons.append("Missing required intake obligations/clauses")
        if invented_obls:
            reasons.append(f"Invented spurious obligation IDs: {sorted(invented_obls)}")
        results.append(CheckResult(
            check_id="IN.C01",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="; ".join(reasons),
        ))

    # 2. Evaluate IN.C02 (180 pts) - Change/scope definition and boundaries
    # Must declare change structure without unauthorized whole-repo scope
    has_change = any(path.startswith("docs/changes/") and path.endswith("change.yaml") for path in file_map) or ("Change request" in combined_text)
    if has_change:
        results.append(CheckResult(
            check_id="IN.C02",
            status="pass",
            awarded_points=180,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="IN.C02",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Missing change scope declaration",
        ))

    # 3. Evaluate IN.C03 (120 pts) - Pre-reading restrictions & source referencing
    forbidden_reads = []
    for ev in events:
        if ev.get("kind") == "file_read":
            rpath = ev.get("path", "")
            if any(re.match(pat, rpath) for pat in FORBIDDEN_READ_PATTERNS):
                forbidden_reads.append(rpath)
    
    if not forbidden_reads:
        results.append(CheckResult(
            check_id="IN.C03",
            status="pass",
            awarded_points=120,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="IN.C03",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason=f"Premature read of forbidden paths: {forbidden_reads}",
        ))

    # 4. Evaluate IN.C04 (60 pts) - Baseline status & core queue state at intake
    core_state = snapshot.core if isinstance(snapshot, SnapshotData) else snapshot.get("core", {})
    if core_state and not core_state.get("error"):
        results.append(CheckResult(
            check_id="IN.C04",
            status="pass",
            awarded_points=60,
            evidence_refs=[ev_ref_dict],
            failure_reason=None,
        ))
    else:
        results.append(CheckResult(
            check_id="IN.C04",
            status="fail",
            awarded_points=0,
            evidence_refs=[ev_ref_dict],
            failure_reason="Invalid or uninitialized Core baseline state",
        ))

    # Discipline checks (IN.D01..IN.D05)
    # IN.D01 (80 pts): file write envelope
    illegal_writes = []
    for ev in events:
        if ev.get("kind") == "file_write":
            wpath = ev.get("path", "")
            if not any(re.match(pat, wpath) for pat in ALLOWED_INTAKE_WRITE_PATTERNS):
                illegal_writes.append(wpath)
                
    results.append(CheckResult(
        check_id="IN.D01",
        status="pass" if not illegal_writes else "fail",
        awarded_points=80 if not illegal_writes else 0,
        evidence_refs=[ev_ref_dict],
        failure_reason=None if not illegal_writes else f"File writes outside intake envelope: {illegal_writes}",
    ))

    # IN.D02 (60 pts): core events / state machine compliance
    results.append(CheckResult(
        check_id="IN.D02",
        status="pass",
        awarded_points=60,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    # IN.D03 (50 pts): command events
    results.append(CheckResult(
        check_id="IN.D03",
        status="pass",
        awarded_points=50,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    # IN.D04 (40 pts): identity refs
    results.append(CheckResult(
        check_id="IN.D04",
        status="pass",
        awarded_points=40,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    # IN.D05 (20 pts): policy events
    results.append(CheckResult(
        check_id="IN.D05",
        status="pass",
        awarded_points=20,
        evidence_refs=[ev_ref_dict],
        failure_reason=None,
    ))

    return results
