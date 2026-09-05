import pytest
from pathlib import Path
from deltafuse.evals.dataset import EvalDataset, EvalCase
from deltafuse.evals.providers import MockLLMProvider
from deltafuse.evals.runner import run_eval


def test_run_eval_golden_scenario():
    dataset = EvalDataset.get_default_dataset()
    provider = MockLLMProvider(scenario="golden")
    report = run_eval(dataset=dataset, provider=provider)

    assert report.total_cases == len(dataset)
    assert report.passed_cases == len(dataset)
    assert report.failed_cases == 0
    assert report.schema_compliance_rate == 100.0
    assert report.gate_pass_rate == 100.0
    assert report.routing_accuracy == 100.0
    assert report.average_claim_f1 == 1.0

    summary_text = report.to_summary_text()
    assert "Schema Compliance Rate  : 100.0%" in summary_text
    assert "Gate Pass Rate          : 100.0%" in summary_text

    md_report = report.to_markdown()
    assert "# DeltaFuse LLM Evaluation Report" in md_report


def test_run_eval_schema_violation_scenario():
    dataset = EvalDataset.get_default_dataset()
    provider = MockLLMProvider(scenario="schema_violation")
    report = run_eval(dataset=dataset, provider=provider)

    assert report.schema_compliance_rate == 0.0
    assert report.failed_cases == report.total_cases


def test_run_eval_routing_mismatch_scenario():
    dataset = EvalDataset.get_default_dataset()
    provider = MockLLMProvider(scenario="routing_mismatch")
    report = run_eval(dataset=dataset, provider=provider)

    assert report.routing_accuracy == 0.0
    assert report.schema_compliance_rate == 100.0


def test_run_eval_claim_hallucination_scenario():
    dataset = EvalDataset.get_default_dataset()
    provider = MockLLMProvider(scenario="claim_hallucination")
    report = run_eval(dataset=dataset, provider=provider)

    assert report.average_claim_f1 < 0.1
    assert report.failed_cases == report.total_cases
