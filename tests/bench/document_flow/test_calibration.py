"""Tests for complete mutation calibration and judge pack freezing (J03-605)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.document_flow.calibrate import run_calibration


MANIFEST_PATH = Path("process/bench/cases/J03-document-flow/mutations/manifest.json")


def test_frozen_calibration_manifest_completeness():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["matrix_version"] == "J03-mutants-1"
    assert manifest["total_candidates"] == 28
    assert manifest["required_kills"] == 26
    
    mutants = manifest["mutants"]
    assert len(mutants) == 28
    
    critical_mutants = [m for m in mutants if m.get("critical")]
    assert len(critical_mutants) == 27
    
    # Check that each mutant has valid fields and expected checks
    for m in mutants:
        assert m["id"].startswith("M")
        assert len(m["expected_checks"]) >= 1
        assert m["surface"] in ("process", "Java functional", "Java resilience", "process/boundary", "boundary", "integrity", "campaign")


def test_complete_calibration_run(tmp_path):
    report_dir = tmp_path / "reports"
    summary = run_calibration(manifest_path=MANIFEST_PATH, out_dir=report_dir)
    
    assert summary.total_candidates == 28
    assert summary.killed_count == 28
    assert summary.survived_count == 0
    assert summary.invalid_count == 0
    assert summary.critical_killed == 27
    assert summary.kill_rate >= 0.90
    assert summary.acceptable is True
    
    # Check generated report artifacts
    assert (report_dir / "calibration-summary.json").is_file()
    assert (report_dir / "calibration-index.md").is_file()
    
    md_text = (report_dir / "calibration-index.md").read_text(encoding="utf-8")
    assert "**Status**: ACCEPTED" in md_text
    assert "| M01 |" in md_text
    assert "| M28 |" in md_text
