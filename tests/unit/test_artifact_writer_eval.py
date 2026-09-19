"""Unit tests for paired small-model evaluation harness and corpus (AW-18)."""

import json
from pathlib import Path
import pytest

from scripts.evaluate_artifact_writer import run_evaluation


def test_eval_corpus_fixture_validity():
    """Verify evaluation corpus JSON fixture structure and strata coverage."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    assert corpus_path.is_file(), "eval_corpus.json must exist"

    cases = json.loads(corpus_path.read_text(encoding="utf-8"))
    assert len(cases) >= 8, "eval_corpus.json must contain at least 8 test cases"

    strata = {c["stratum"] for c in cases}
    expected_strata = {"task_create", "routing_update", "spec_delta", "nested_patch", "explicit_removal", "legacy_comments", "semantic_omission", "unauthorized_status"}
    assert expected_strata.issubset(strata), f"Corpus missing strata: {expected_strata - strata}"


def test_evaluate_artifact_writer_harness():
    """Run evaluate_artifact_writer harness on eval_corpus.json and assert unbiased metrics."""
    corpus_path = Path("tests/fixtures/artifact_writer_eval/eval_corpus.json")
    summary = run_evaluation(corpus_path)

    assert summary["total_cases"] >= 8
    assert summary["first_pass_valid_rate"] == 100.0, f"First pass valid rate was {summary['first_pass_valid_rate']}%"
    assert summary["semantic_correct_rate"] == 100.0, f"Semantic correct rate was {summary['semantic_correct_rate']}%"

    # Verify results per case
    for res in summary["results"]:
        assert res["first_pass"] is True, f"Case {res['id']} failed first pass check: {res['error']}"
        assert res["semantic_correct"] is True, f"Case {res['id']} failed semantic correctness check"
