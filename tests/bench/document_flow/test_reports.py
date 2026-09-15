"""Tests for report rendering and inspection CLI (J03-409)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from types import MappingProxyType

import pytest

from scripts.document_flow.campaign import CampaignComparison, CampaignSummary
from scripts.document_flow.evaluate import Ceiling, RunSummary, StageScore
from scripts.document_flow.report_cli import main as report_cli_main
from scripts.document_flow.reports import (
    render_campaign_markdown,
    render_comparison_markdown,
    render_run_markdown,
)
from tests.bench.document_flow.test_replay import make_full_store


def test_render_run_markdown_golden():
    stages = {
        "intake": StageScore(600, 250, 150, 1000),
        "analyze": StageScore(600, 250, 150, 1000),
        "specify": StageScore(600, 250, 150, 1000),
        "decompose": StageScore(600, 250, 150, 1000),
        "declare": StageScore(600, 250, 150, 1000),
        "implement": StageScore(600, 250, 150, 1000),
        "verify": StageScore(600, 250, 150, 1000),
    }
    sys_groups = {
        "functional": 1800,
        "resilience": 600,
        "compatibility": 400,
        "efficiency": 200,
    }
    summary = RunSummary(
        status="passed",
        raw_score=10000,
        final_score=10000,
        release_verdict="release_pass",
        stages=MappingProxyType(stages),
        system_groups=MappingProxyType(sys_groups),
        applied_ceilings=(),
        hard_failures=(),
        failure_classes=(),
        first_failure=None,
    )
    md = render_run_markdown(summary, title="Golden Run")
    assert "# Golden Run" in md
    assert "**Status**: `passed`" in md
    assert "**Final Score**: `10000`" in md
    assert "| `intake` | 600 | 250 | 150 | **1000** |" in md
    assert "| `functional` | 1800 | 1800 |" in md


def test_render_run_markdown_with_ceilings_and_failures():
    summary = RunSummary(
        status="failed",
        raw_score=8000,
        final_score=4999,
        release_verdict="fail",
        stages=MappingProxyType({}),
        system_groups=MappingProxyType({}),
        applied_ceilings=(Ceiling("incomplete_lifecycle", 4999),),
        hard_failures=("GATE.LIFECYCLE_COMPLETE",),
        failure_classes=("process-failure",),
        first_failure="GATE.LIFECYCLE_COMPLETE",
    )
    md = render_run_markdown(summary)
    assert "**First Failure**: `GATE.LIFECYCLE_COMPLETE`" in md
    assert "incomplete_lifecycle" in md
    assert "limit `4999`" in md


def test_render_campaign_and_comparison_markdown():
    c_sum = CampaignSummary(
        campaign_id="camp-1",
        status="complete",
        campaign_score=9500,
        scores=(10000, 9500, 9000),
        median=Fraction(9500),
        minimum=9000,
        mean=Fraction(9500),
        pass_rate=Fraction(1, 1),
        population_variance=Fraction(50000, 3),
        first_failure_distribution=(),
        stage_deltas=MappingProxyType({"intake": 10}),
        stage_means=MappingProxyType({"intake": Fraction(990)}),
        first_failure=None,
        compatibility_identity=(),
    )
    cmd = render_campaign_markdown(c_sum)
    assert "**Campaign Score**: `9500`" in cmd
    assert "**Pass Rate**: `1`" in cmd

    comp = CampaignComparison(
        status="compatible",
        reason=None,
        score_delta=200,
        stage_deltas=MappingProxyType({"intake": Fraction(20)}),
    )
    comp_md = render_comparison_markdown(comp)
    assert "**Score Delta (Right - Left)**: `200`" in comp_md
    assert "| `intake` | 20 |" in comp_md


def test_report_cli_run_markdown_and_json(tmp_path, capsys):
    store = make_full_store(tmp_path, "run-cli-test")
    
    # Run CLI markdown
    rc = report_cli_main(["run", "--store", str(store.root), "--run-id", "run-cli-test", "--root-id", "root-run-cli-test", "--format", "markdown"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "Benchmark Run Report" in captured
    assert "Status" in captured

    # Run CLI json with out file
    out_file = tmp_path / "report.json"
    rc = report_cli_main(["run", "--store", str(store.root), "--run-id", "run-cli-test", "--root-id", "root-run-cli-test", "--format", "json", "--out", str(out_file)])
    assert rc == 0
    assert out_file.is_file()
    assert '"status": "passed"' in out_file.read_text(encoding="utf-8")
