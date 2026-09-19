"""Unit tests for paired small-model evaluation harness, negative controls, and independent oracle (AW-27)."""

import json
from pathlib import Path
import pytest

from scripts.evaluate_artifact_writer import run_evaluation, evaluate_independent_oracle


def test_eval_corpus_fixture_validity():
    """Verify evaluation corpus JSON fixture structure and strata coverage."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    assert corpus_path.is_file(), "eval_corpus.json must exist"

    cases = json.loads(corpus_path.read_text(encoding="utf-8"))
    assert len(cases) >= 8, "eval_corpus.json must contain at least 8 test cases"

    strata = {c["stratum"] for c in cases}
    expected_strata = {
        "task_create",
        "routing_update",
        "spec_delta",
        "nested_patch",
        "explicit_removal",
        "legacy_comments",
        "semantic_omission",
        "unauthorized_status",
    }
    assert expected_strata.issubset(strata), f"Corpus missing strata: {expected_strata - strata}"


def test_evaluate_artifact_writer_harness_baseline():
    """Run evaluate_artifact_writer harness on eval_corpus.json and assert mode labeling & metrics."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    summary = run_evaluation(corpus_path, mode="harness_baseline")

    assert summary["evaluation_mode"] == "harness_baseline"
    assert "Deterministic serializer" in summary["mode_description"]
    assert summary["total_cases"] >= 8
    assert summary["first_pass_valid_rate"] == 100.0, f"First pass valid rate was {summary['first_pass_valid_rate']}%"
    assert summary["semantic_correct_rate"] == 100.0, f"Semantic correct rate was {summary['semantic_correct_rate']}%"

    for res in summary["results"]:
        assert res["first_pass"] is True, f"Case {res['id']} failed first pass check: {res['error']}"
        assert res["semantic_correct"] is True, f"Case {res['id']} failed semantic correctness check"


def test_independent_oracle_detects_weakened_writer_dropped_semantics():
    """Independent oracle MUST detect a weakened writer that drops required title property."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    summary = run_evaluation(corpus_path, mode="harness_baseline", weakened_mode="drop_title")

    # The task_create case (CASE-01) had title removed in payload, so it must fail validation
    case_01 = next(r for r in summary["results"] if r["id"] == "CASE-01")
    assert case_01["first_pass"] is False, "Independent oracle failed to catch dropped title property"
    assert case_01["semantic_correct"] is False


def test_independent_oracle_detects_weakened_writer_unauthorized_status():
    """Independent oracle MUST detect a weakened writer that attempts unauthorized status patch."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    summary = run_evaluation(corpus_path, mode="harness_baseline", weakened_mode="force_verified")

    # Updating status on task must be blocked by policy
    case_04 = next(r for r in summary["results"] if r["id"] == "CASE-04")
    assert case_04["gate_blocked"] is True
    assert case_04["semantic_correct"] is False  # Weakened writer failed valid update by injecting status patch


def test_paired_model_mode_reports_unavailable_endpoint_without_fake_claims():
    """Paired model evaluation mode cleanly reports unavailable endpoint and keeps acceptance open for AW-20."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    summary = run_evaluation(corpus_path, mode="paired_model")

    assert summary["evaluation_mode"] == "paired_model"
    assert summary["external_model_status"] == "unavailable_no_endpoint"
    assert summary["acceptance_status"] == "open_for_AW-20"
