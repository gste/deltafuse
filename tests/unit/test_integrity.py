import pytest
from pathlib import Path
from deltafuse.core.integrity import (
    extract_claims_from_request,
    find_spec_anchors,
    validate_coverage_completeness,
)

def test_extract_claims_from_request():
    content = "# Request\nThe user wants CR-001 and CR-002.\nRepeat CR-001 and new CR-999."
    claims = extract_claims_from_request(content)
    assert claims == ["CR-001", "CR-002", "CR-999"]

def test_find_spec_anchors(tmp_path: Path):
    spec_md = tmp_path / "spec.md"
    spec_md.write_text("# Spec\n<a name=\"REQ-AUTH-01\"></a>\n## REQ-AUTH-02\nSC-LOGIN-01\nPOL-SEC-01", encoding="utf-8")

    anchors = find_spec_anchors(spec_md)
    assert "REQ-AUTH-01" in anchors
    assert "REQ-AUTH-02" in anchors
    assert "SC-LOGIN-01" in anchors
    assert "POL-SEC-01" in anchors

def test_validate_coverage_completeness_valid():
    request_claims = ["CR-001", "CR-002"]
    coverage_data = {
        "claims": {
            "CR-001": {"slice": "SLICE-01", "tasks": ["TASK-001"]},
            "CR-002": {"slice": "SLICE-01", "tasks": ["TASK-002"]}
        }
    }
    errors = validate_coverage_completeness(request_claims, coverage_data)
    assert errors == []

def test_validate_coverage_completeness_missing_and_orphan():
    request_claims = ["CR-001", "CR-002"]
    coverage_data = {
        "claims": {
            "CR-001": {"slice": "SLICE-01", "tasks": ["TASK-001"]},
            "CR-999": {"slice": "SLICE-02", "tasks": ["TASK-003"]}
        }
    }
    errors = validate_coverage_completeness(request_claims, coverage_data)
    assert any("CR-002" in e and "not mapped" in e for e in errors)
    assert any("CR-999" in e and "orphan" in e for e in errors)
