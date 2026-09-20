"""Unit tests for paired small-model evaluation harness, negative controls, and independent oracle (AW-27)."""

import json
from pathlib import Path
import pytest
import yaml

from deltafuse.core.artifact_patch import ArtifactPatchError, apply_artifact_patch
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


# AW-46 supplies the executable invariant behind AW39-R3: "Verify JSON Pointer escaping
# and missing nested paths; do not skip a failed lookup or substitute top-level deletion
# checks for nested removals." Routing claims are schema-closed, so the escaped tokens
# are exercised in a nested extension container that the routing schema permits.

SLASH_KEY = "a/b"
TILDE_KEY = "m~n"


def _routing_doc(notes):
    return {
        "change": "CHG-001",
        "claims": {"CR-001": {"primary_capability": "core"}},
        "extension-notes": notes,
    }


def _routing_verdict(change_dir, case, disk_doc):
    (change_dir / "routing.yaml").write_text(
        yaml.safe_dump(disk_doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return evaluate_independent_oracle(
        change_dir, case, passed_op=True, gate_blocked=False, error_msg=None
    )


def test_aw46_escaped_pointer_set_writes_decoded_nested_keys():
    """AW39-R3: ~1 and ~0 must be decoded before the patch addresses a key."""
    outcome = apply_artifact_patch(
        _routing_doc({SLASH_KEY: {TILDE_KEY: "before", "summary": "keep"}}),
        {"set": [{"path": "/extension-notes/a~1b/m~0n", "value": "after"}]},
        kind="routing",
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert list(notes) == [SLASH_KEY], f"escaped pointer created a literal key instead of '{SLASH_KEY}': {notes}"
    assert notes[SLASH_KEY][TILDE_KEY] == "after"
    assert notes[SLASH_KEY]["summary"] == "keep", "sibling of the escaped target must survive the set"
    assert outcome.changed is True and outcome.applied_ops_count == 1


def test_aw46_escaped_pointer_unescaping_follows_rfc6901_order():
    """AW39-R3: ~01 means a literal '~1' key; a swapped replace order resolves it to 'a/b'."""
    outcome = apply_artifact_patch(
        _routing_doc({"a~1b": {"summary": "target"}}),
        {"set": [{"path": "/extension-notes/a~01b/summary", "value": "updated"}]},
        kind="routing",
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert notes["a~1b"]["summary"] == "updated", f"'~01' did not decode to '~1': {notes}"
    assert "a/b" not in notes, f"'~01' was decoded as '~1' then '/', which reorders RFC 6901 unescaping: {notes}"


def test_aw46_escaped_pointer_remove_targets_only_the_nested_key():
    """AW39-R3: a nested removal may not be satisfied by a top-level or same-named key."""
    document = _routing_doc({SLASH_KEY: {TILDE_KEY: "drop", "summary": "keep"}, "other": {TILDE_KEY: "untouched"}})
    outcome = apply_artifact_patch(
        document, {"remove": ["/extension-notes/a~1b/m~0n"]}, kind="routing"
    )
    notes = outcome.updated_metadata["extension-notes"]
    assert SLASH_KEY in notes, "the parent container of a nested removal must remain"
    assert notes[SLASH_KEY] == {"summary": "keep"}, f"nested removal over- or under-matched: {notes}"
    assert notes["other"] == {TILDE_KEY: "untouched"}, "an equally named key elsewhere must not be deleted"
    assert outcome.applied_ops_count == 1


def test_aw46_escaped_pointer_does_not_match_a_literal_tilde_key():
    """AW39-R3: '~1' addresses key 'a/b', never the literal text 'a~1b' on disk."""
    document = _routing_doc({"a~1b": {"summary": "keep"}})
    with pytest.raises(ArtifactPatchError) as excinfo:
        apply_artifact_patch(document, {"remove": ["/extension-notes/a~1b"]}, kind="routing")
    assert excinfo.value.code == "remove_target_missing"
    assert excinfo.value.path == "/extension-notes/a~1b"
    assert document["extension-notes"] == {"a~1b": {"summary": "keep"}}, "denial must not mutate the document"


def test_aw46_missing_nested_path_fails_loudly_instead_of_being_skipped():
    """AW39-R3: a missing nested path is a failed lookup, not a silent no-op."""
    document = _routing_doc({SLASH_KEY: {"summary": "keep"}})
    with pytest.raises(ArtifactPatchError) as excinfo:
        apply_artifact_patch(document, {"remove": ["/extension-notes/a~1b/m~0n"]}, kind="routing")
    assert excinfo.value.code == "remove_target_missing"
    assert document["extension-notes"][SLASH_KEY] == {"summary": "keep"}


def test_aw46_oracle_rejects_literal_tilde_and_missing_nested_set_targets(tmp_path: Path):
    """AW39-R3: the oracle accepts only the decoded nested state for an escaped set."""
    case = {
        "id": "CASE-AW46-SET",
        "operation": "update",
        "kind": "routing",
        "expected_valid": True,
        "input_payload": {"set": [{"path": "/extension-notes/a~1b/m~0n", "value": "after"}]},
    }
    decoded = _routing_doc({SLASH_KEY: {TILDE_KEY: "after", "summary": "keep"}})
    writer_kept_raw_keys = _routing_doc({"a~1b": {"m~0n": "after"}})
    writer_dropped_nested_set = _routing_doc({SLASH_KEY: {"summary": "keep"}})

    dirs = {}
    for name in ("decoded", "raw-keys", "missing"):
        directory = tmp_path / name
        directory.mkdir()
        dirs[name] = directory

    assert _routing_verdict(dirs["decoded"], case, decoded)["semantic_correct"] is True
    stale = _routing_verdict(dirs["raw-keys"], case, writer_kept_raw_keys)
    assert stale["semantic_correct"] is False, "oracle accepted raw ~1/~0 key names for an escaped set"
    dropped = _routing_verdict(dirs["missing"], case, writer_dropped_nested_set)
    assert dropped["semantic_correct"] is False, "oracle skipped the failed nested lookup"


def test_aw46_oracle_checks_nested_removal_location_not_top_level_presence(tmp_path: Path):
    """AW39-R3: both disk states share the same top-level keys, so only a nested check can tell them apart."""
    case = {
        "id": "CASE-AW46-REMOVE",
        "operation": "update",
        "kind": "routing",
        "expected_valid": True,
        "input_payload": {"remove": ["/extension-notes/a~1b/m~0n"]},
    }
    still_present = _routing_doc({SLASH_KEY: {TILDE_KEY: "drop", "summary": "keep"}})
    removed = _routing_doc({SLASH_KEY: {"summary": "keep"}})
    assert set(still_present) == set(removed) == {"change", "claims", "extension-notes"}
    assert set(still_present["extension-notes"]) == set(removed["extension-notes"])

    assert _routing_verdict(tmp_path, case, still_present)["semantic_correct"] is False
    assert _routing_verdict(tmp_path, case, removed)["semantic_correct"] is True

