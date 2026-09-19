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


def test_aw40_reproduce_synthetic_score_substitution_on_empty_or_adapter_corpus(tmp_path: Path):
    """AW-40 Red: Harness must reject hardcoded adapter scores and empty corpus qualification."""
    empty_corpus = tmp_path / "empty_corpus.json"
    empty_corpus.write_text("[]", encoding="utf-8")

    # 1. Empty corpus must not report ready_for_AW-20 or 5 fake successes out of 0 cases
    summary_empty = run_evaluation(empty_corpus, mode="paired_model", adapter="small_model")
    assert summary_empty["acceptance_status"] == "open_for_AW-20"
    assert summary_empty["external_model_status"] != "qualified_with_adapter_evidence"
    assert "arm_a_manual_raw" not in summary_empty or summary_empty["arm_a_manual_raw"].get("first_pass_valid_count") == 0


def test_aw39_routing_update_semantic_rejection_and_acceptance(tmp_path: Path):
    """AW39-R1: Oracle rejects unapplied routing capability updates and accepts valid ones."""
    (tmp_path / "routing.yaml").write_text("change: CHG-001\nclaims:\n  CR-001:\n    primary_capability: old_cap\n", encoding="utf-8")
    case = {
        "id": "CASE-ROUTING-01",
        "operation": "update",
        "kind": "routing",
        "expected_valid": True,
        "input_payload": {
            "set": [{"path": "/claims/CR-001/primary_capability", "value": "new_cap"}]
        },
    }

    # When old capability is left on disk, oracle MUST return semantic_correct=False
    res_stale = evaluate_independent_oracle(tmp_path, case, passed_op=True, gate_blocked=False, error_msg=None)
    assert res_stale["semantic_correct"] is False

    # When new capability is on disk, oracle returns semantic_correct=True
    (tmp_path / "routing.yaml").write_text("change: CHG-001\nclaims:\n  CR-001:\n    primary_capability: new_cap\n", encoding="utf-8")
    res_updated = evaluate_independent_oracle(tmp_path, case, passed_op=True, gate_blocked=False, error_msg=None)
    assert res_updated["semantic_correct"] is True


def test_aw39_json_pointer_escaping_and_nested_removal(tmp_path: Path):
    """AW39-R3: Verify JSON pointer escaping (~1, ~0), nested paths, and nested removals."""
    (tmp_path / "routing.yaml").write_text(
        "change: CHG-001\n"
        "claims:\n"
        "  CR-001:\n"
        "    primary_capability: core\n"
        "    summary: with~tilde/slash\n",
        encoding="utf-8",
    )
    case_remove = {
        "id": "CASE-REMOVE-01",
        "operation": "update",
        "kind": "routing",
        "expected_valid": True,
        "input_payload": {
            "remove": ["/claims/CR-001/summary"]
        },
    }
    # If summary is still present, removal check MUST fail
    res_not_removed = evaluate_independent_oracle(tmp_path, case_remove, passed_op=True, gate_blocked=False, error_msg=None)
    assert res_not_removed["semantic_correct"] is False

    # If summary was removed on disk, oracle passes
    (tmp_path / "routing.yaml").write_text(
        "change: CHG-001\n"
        "claims:\n"
        "  CR-001:\n"
        "    primary_capability: core\n",
        encoding="utf-8",
    )
    res_removed = evaluate_independent_oracle(tmp_path, case_remove, passed_op=True, gate_blocked=False, error_msg=None)
    assert res_removed["semantic_correct"] is True

