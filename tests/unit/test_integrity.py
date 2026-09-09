import pytest
from pathlib import Path
from deltafuse.core.integrity import (
    extract_claims_from_request,
    find_spec_anchors,
    validate_coverage_completeness,
    validate_spec_ref,
    validate_decision_ref,
)


def test_extract_claims_from_request():
    content = "# Request\nThe user wants CR-001 and CR-002.\nRepeat CR-001 and new CR-999."
    claims = extract_claims_from_request(content)
    assert claims == ["CR-001", "CR-002", "CR-999"]


def test_extract_claims_from_request_s02_labels():
    """F-008 / S02 r2: observation/expectation IDs are claims, not only CR-*."""
    content = (
        "## Claims\n\n"
        "### Observation\n"
        "- O1: limiter consume returns False when empty.\n"
        "- O2: no penalty parameter today.\n\n"
        "### Expectation\n"
        "- E1: accept optional penalty_seconds.\n\n"
        "### Unknowns\n"
        "- U3: concurrency is unspecified.\n"
    )
    claims = extract_claims_from_request(content)
    assert claims == ["O1", "O2", "E1", "U3"]
    assert extract_claims_from_request("TokenBucketLimiter and HTTP 200") == []

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


def test_source_uses_private_symbols_detects_attr_and_import():
    from deltafuse.core.integrity import test_source_uses_private_symbols
    assert test_source_uses_private_symbols("limiter._blocked_until['u'] = 0.0\n")
    assert test_source_uses_private_symbols("from limiter import _blocked_until\n")
    assert not test_source_uses_private_symbols("from __future__ import annotations\n")
    assert not test_source_uses_private_symbols("assert limiter.is_blocked('u') is False\n")


def test_validate_spec_ref_success(tmp_path: Path):
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Spec\n### REQ-01\n", encoding="utf-8")
    assert validate_spec_ref("docs/spec/core.md#REQ-01", tmp_path) is None
    assert validate_spec_ref("docs/spec/core.md", tmp_path) is None


def test_validate_spec_ref_rejects_path_traversal(tmp_path: Path):
    outside = tmp_path / "outside_spec.md"
    outside.write_text("# leaked\n", encoding="utf-8")
    repo = tmp_path / "repo"
    spec_dir = repo / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "core.md").write_text("# Spec\n### REQ-01\n", encoding="utf-8")

    err = validate_spec_ref("../outside_spec.md", repo)
    assert err is not None
    assert "Path traversal forbidden" in err
    assert "does not exist" not in err

    missing_outside = validate_spec_ref("../no-such-file.md", repo)
    assert missing_outside is not None
    assert "Path traversal forbidden" in missing_outside
    assert "does not exist" not in missing_outside

    assert validate_spec_ref("docs/spec/core.md#REQ-01", repo) is None


def test_validate_decision_ref_rejects_path_traversal(tmp_path: Path):
    outside = tmp_path / "DEC-999.md"
    outside.write_text("---\nstatus: accepted\n---\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    errs = validate_decision_ref("../DEC-999.md", repo)
    assert any("Path traversal forbidden" in e for e in errs)
