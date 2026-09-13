"""QF-021: independent re-evaluation of T1-T8 from disk artifacts.

A saved report + manifest is the ONLY input: `evaluate_artifact` recomputes
every primary and derived T1-T8 quantity and requires an exact match with
the stored verdict. No `pass` can be obtained by editing derived fields;
NaN/inf, boolean-as-number, duplicate stages/events, missing receipts and
unlinked references always fail.
"""

from __future__ import annotations

import copy
import sys

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import qualify  # noqa: E402
import qualify_evidence  # noqa: E402
import qualify_semantic  # noqa: E402

COMMIT = "a" * 40
MODEL = "ornith-1.5-35b-a3b"

THRESHOLDS = {
    "source": "backlog/product/v3/thresholds.md",
    "revision": "rev1",
    "absolute": {
        "correctness_failed": 0, "stages_completed": 7,
        "gate_retries_max": 2, "context_peak_tokens_max": 32768,
        "framework_input_tokens_max": 16000, "max_unique_files": 24,
        "hallucinated_paths": 0, "envelope_violations": 0,
        "evidence_authentic": True,
    },
}

ISOLATED = {
    "kind": {"value": "isolated", "provenance": "declared", "basis": "b"},
    "boundary_probe": {"value": [{"run": "r1"}], "provenance": "measured",
                       "method": "m"},
}

EVENT = {"call_index": 1, "seq": 1, "tool": "write", "outcome": "ok",
         "paths_read": [], "paths_written": ["docs/spec/x.md"],
         "command": None, "exit_code": None, "envelope_globs": None}

CALL = {"input_tokens": 9120, "framework_input_tokens": 6400,
        "framework_input_chars": 25600, "framework_input_tokens_method":
        "host-tokenize", "unique_files": 1, "hallucinated_paths": 0,
        "envelope_violations": 0}


def _stages(**overrides):
    names = ("intake", "analyze", "specify", "decompose", "declare",
             "implement", "verify")
    rows = [{"stage": n, "status": "completed",
             "checks": {"passed": 3, "failed": 0}, "gate_retries": 0}
            for n in names]
    for name, patch in overrides.items():
        for row in rows:
            if row["stage"] == name:
                row.update(patch)
    return rows


def _valid_report() -> dict:
    earned, total = 21, 21
    return {
        "schema_version": 1,
        "run_id": "camp-M01-cooldown-run1",
        "case": "M01-cooldown",
        "framework_commit": COMMIT,
        "model": MODEL,
        "verdict": "pass",
        "threshold_failures": [],
        "process": 100.0,
        "correctness": 100.0,
        "points": {"earned": earned, "max": total},
        "stages": _stages(),
        "calls": [dict(CALL)],
        "tool_events": [dict(EVENT)],
        "totals": {
            "correctness": {"passed": 21, "failed": 0},
            "gate_retries": 0,
            "context_peak_tokens": 9120,
            "framework_input_tokens_max": 6400,
            "max_unique_files": 1,
            "hallucinated_paths": 0,
            "envelope_violations": 0,
            "evidence_authentic": True,
        },
        "framework_input_tokens_method": "host-tokenize",
        "t7_breakdown": {"write_denied": 0, "leash_violations": 0,
                         "unjournaled_change": 0, "inventory_tampered": 0,
                         "staging_escape": 0, "execution_policy": 0},
        "hallucinated_breakdown": {"hallucinated": 0, "envelope": 0,
                                   "execution_policy": 0},
        "stage_leash": [],
        "defense_checks": {
            "journal_forgery": {"id": "defense.journal_forgery", "pass": True,
                                "detail": "receipts verified sha256:abc"},
            "synthetic_evidence": {"id": "defense.synthetic_evidence",
                                   "pass": True, "detail": "stamps authentic"},
            "oracle_leak": {"id": "defense.oracle_leak", "pass": True,
                            "detail": "no leak"},
        },
        "executor_kind": "isolated",
        "thresholds": copy.deepcopy(THRESHOLDS),
    }


def _evaluate(report, thresholds=None, executor=None):
    return qualify_evidence.evaluate_artifact(
        report, thresholds or THRESHOLDS, executor or ISOLATED,
    )


def _manifest(tmp_path, report, executor=None):
    run_dir = tmp_path / "camp" / report["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    (run_dir / "report.yaml").write_text(yaml.safe_dump(report), encoding="utf-8")
    summary = {k: report[k] for k in ("run_id", "case", "verdict",
                                      "threshold_failures")}
    return {
        "schema_version": 1,
        "campaign_id": "camp",
        "created": "2026-09-13T00:00:00Z",
        "framework": {"commit": COMMIT, "lock_hash": "sha256:" + "0" * 64},
        "executor": executor or copy.deepcopy(ISOLATED),
        "model": {"id": {"value": MODEL, "provenance": "measured", "method": "m"}},
        "thresholds": copy.deepcopy(THRESHOLDS),
        "cases": ["M01-cooldown"],
        "runs": [summary],
        "case_verdicts": {
            "M01-cooldown": {
                "verdict": "pass",
                "medians": {
                    "correctness": 100.0, "process": 100.0,
                    "context_peak_tokens": 9120.0,
                    "framework_input_tokens_max": 6400.0,
                    "framework_input_chars_max": 25600.0,
                    "gate_retries": 0.0, "max_unique_files": 1.0,
                    "hallucinated_paths": 0.0, "envelope_violations": 0.0,
                },
                "median_failures": [],
            }
        },
        "verdict": "pass",
    }


def _validate_manifest(tmp_path, manifest):
    qualify_semantic.semantic_validate_manifest(
        manifest, tmp_path,
        validate_report_fn=qualify.validate_document,
        expected_total_runs=1,
    )


# --------------------------------------------------------- the accepted base


def test_evaluator_lifecycle_pinned_to_core_contract():
    """The pure evaluator's LIFECYCLE constant never drifts from the Core."""
    from deltafuse.core.lifecycle import LIFECYCLE as CORE_LIFECYCLE

    assert qualify_evidence.LIFECYCLE == tuple(CORE_LIFECYCLE)


def test_valid_pass_report_evaluates_clean():
    ok, failures = _evaluate(_valid_report())
    assert ok, failures
    qualify.validate_document("run-report", _valid_report())  # schema: optional new fields


def test_manifest_with_valid_report_passes(tmp_path):
    _validate_manifest(tmp_path, _manifest(tmp_path, _valid_report()))


# ------------------------------- the previously ACCEPTED bogus pass (Red)


def _bogus_previously_accepted_report():
    """bogus stage + context 99999 + hallucinated 5 + envelope 4 + pass —
    this passed schema+semantic validation before QF-021."""
    report = _valid_report()
    report["stages"].append({"stage": "bonus-stage", "status": "completed",
                             "checks": {"passed": 3, "failed": 0},
                             "gate_retries": 0})
    report["stages"][0]["checks"]["passed"] = 24
    report["totals"]["correctness"]["passed"] = 24
    report["calls"][0]["input_tokens"] = 99999
    report["totals"]["context_peak_tokens"] = 99999
    report["calls"][0]["hallucinated_paths"] = 5
    report["totals"]["hallucinated_paths"] = 5
    report["calls"][0]["envelope_violations"] = 4
    report["totals"]["envelope_violations"] = 4
    report["process"] = 100.0 * 7 / 8
    return report


def test_previously_accepted_bogus_pass_now_rejected(tmp_path):
    report = _bogus_previously_accepted_report()
    ok, failures = _evaluate(report)
    assert not ok
    assert any(f.startswith("T2") for f in failures), failures
    assert any(f.startswith("T4") for f in failures), failures
    assert any(f.startswith("T6") for f in failures), failures
    assert any(f.startswith("T7") for f in failures), failures
    manifest = _manifest(tmp_path, report)
    with pytest.raises(qualify_semantic.SemanticValidationError):
        _validate_manifest(tmp_path, manifest)


# ------------------------------------------------- per-field mutation matrix


def _mutants():
    base = _valid_report()
    cases = {}

    def m(name, fn):
        report = _valid_report()
        fn(report)
        cases[name] = report

    # T1: one failed oracle check, everything derived updated consistently
    def t1(r):
        r["stages"][0]["checks"]["failed"] = 1
        r["totals"]["correctness"]["failed"] = 1
        r["points"]["earned"] = 20
        r["correctness"] = round(100.0 * 20 / 21, 1)
    m("T1-consistent-failure", t1)

    # T2: reorder two stages consistently
    def t2(r):
        r["stages"][1], r["stages"][2] = r["stages"][2], r["stages"][1]
    m("T2-order", t2)

    def t2b(r):
        r["stages"].append(dict(r["stages"][0]))
    m("T2-duplicate-stage", t2b)

    # T3: retries over per-stage budget, totals updated
    def t3(r):
        r["stages"][1]["gate_retries"] = 2
        r["totals"]["gate_retries"] = 2
    m("T3-stage-retries", t3)

    # T4: peak over budget, consistent
    def t4(r):
        r["calls"][0]["input_tokens"] = 40000
        r["totals"]["context_peak_tokens"] = 40000
    m("T4-peak", t4)

    def t4b(r):
        r["calls"][0]["framework_input_tokens_method"] = "estimated-nonrelease"
        r["framework_input_tokens_method"] = "estimated-nonrelease"
    m("T4-estimated-method", t4b)

    # T5: unique files over budget, consistent
    def t5(r):
        r["calls"][0]["unique_files"] = 42
        r["totals"]["max_unique_files"] = 42
    m("T5-unique", t5)

    # T6: hallucinated path fully consistent everywhere
    def t6(r):
        for c in r["calls"]:
            c["hallucinated_paths"] = 1
        r["tool_events"][0] = {**EVENT, "tool": "read",
                               "outcome": "error: no such file: ghost.md"}
        r["totals"]["hallucinated_paths"] = 1
        r["hallucinated_breakdown"]["hallucinated"] = 1
    m("T6-hallucinated", t6)

    # T7: envelope violation fully consistent everywhere
    def t7(r):
        for c in r["calls"]:
            c["envelope_violations"] = 1
        r["tool_events"][0] = {**EVENT,
                               "outcome": "rejected: src/x.py is outside the "
                                          "current envelope.write"}
        r["totals"]["envelope_violations"] = 1
        r["t7_breakdown"]["write_denied"] = 1
    m("T7-envelope", t7)

    # T8: defense evidence failing
    def t8(r):
        r["defense_checks"]["oracle_leak"]["pass"] = False
        r["totals"]["evidence_authentic"] = False
    m("T8-defense-failed", t8)

    def t8b(r):
        r["defense_checks"]["oracle_leak"]["detail"] = ""
    m("T8-empty-receipt", t8b)

    def t8c(r):
        del r["defense_checks"]["synthetic_evidence"]
    m("T8-missing-check", t8c)

    # derived-only edits must never keep a pass
    def d1(r):
        r["totals"]["context_peak_tokens"] = 100
    m("derived-peak-lowered", d1)

    def d2(r):
        r["totals"]["correctness"]["passed"] = 999
    m("derived-correctness-lowered", d2)

    def d3(r):
        r["totals"]["gate_retries"] = 0
        r["stages"][1]["gate_retries"] = 3
        r["stages"][1]["status"] = "failed"
        r["process"] = 100.0 * 6 / 7
        r["threshold_failures"] = []
        r["verdict"] = "pass"
    m("derived-retries-cleared", d3)

    def d4(r):
        r["verdict"] = "fail"
        r["threshold_failures"] = ["T1 correctness_failed=1"]
    m("verdict-swapped", d4)

    def d5(r):
        r["thresholds"]["revision"] = "other-revision"
    m("threshold-revision-drift", d5)

    def d6(r):
        r["executor_kind"] = "local-dev"
    m("executor-kind-drift", d6)

    def d7(r):
        r["tool_events"].pop()
    m("event-removed", d7)

    def d8(r):
        r["tool_events"].append(dict(r["tool_events"][0]))
    m("event-duplicated", d8)

    def d9(r):
        r["totals"]["context_peak_tokens"] = float("nan")
    m("nan-peak", d9)

    def d10(r):
        r["correctness"] = float("inf")
    m("inf-correctness", d10)

    def d11(r):
        r["calls"][0]["input_tokens"] = True
    m("bool-as-number", d11)

    return cases


@pytest.mark.parametrize("name", sorted(_mutants().keys()))
def test_mutation_is_rejected(name):
    report = _mutants()[name]
    if name == "bool-as-number":
        with pytest.raises((qualify_evidence.EvidenceError,
                            qualify.SchemaValidationError)):
            try:
                qualify.validate_document("run-report", copy.deepcopy(report))
            except qualify.SchemaValidationError:
                raise
            _evaluate(report)
        return
    ok, failures = _evaluate(report)
    assert not ok, f"{name}: mutation kept a pass"
    assert failures


def test_derived_verdict_never_passes_on_mutations():
    """Neither a pass verdict nor an empty failures list survives ANY of the
    consistent mutations."""
    for name, report in _mutants().items():
        ok, _ = _evaluate(report)
        assert not ok, name


# --------------------------------------------- executor gating and manifests


def test_non_isolated_executor_blocks_pass(tmp_path):
    manifest = _manifest(tmp_path, _valid_report())
    manifest["executor"]["kind"]["value"] = "local-dev"
    with pytest.raises(qualify_semantic.SemanticValidationError,
                       match="executor|non-release"):
        _validate_manifest(tmp_path, manifest)


def test_declared_boundary_probe_blocks_pass(tmp_path):
    manifest = _manifest(tmp_path, _valid_report())
    manifest["executor"]["boundary_probe"] = {
        "value": "not executed", "provenance": "declared", "basis": "b",
    }
    with pytest.raises(qualify_semantic.SemanticValidationError, match="probe"):
        _validate_manifest(tmp_path, manifest)


def test_report_executor_kind_mismatch_rejected(tmp_path):
    report = _valid_report()
    report["executor_kind"] = "local-dev"
    manifest = _manifest(tmp_path, report)
    with pytest.raises(qualify_semantic.SemanticValidationError, match="executor"):
        _validate_manifest(tmp_path, manifest)


def test_report_threshold_revision_mismatch_rejected(tmp_path):
    report = _valid_report()
    report["thresholds"]["revision"] = "other"
    manifest = _manifest(tmp_path, report)
    with pytest.raises(qualify_semantic.SemanticValidationError, match="threshold"):
        _validate_manifest(tmp_path, manifest)


def test_manifest_median_drift_rejected(tmp_path):
    manifest = _manifest(tmp_path, _valid_report())
    manifest["case_verdicts"]["M01-cooldown"]["medians"]["context_peak_tokens"] = 1.0
    with pytest.raises(qualify_semantic.SemanticValidationError, match="median"):
        _validate_manifest(tmp_path, manifest)


def test_missing_report_rejected(tmp_path):
    manifest = _manifest(tmp_path, _valid_report())
    (tmp_path / "camp" / manifest["runs"][0]["run_id"] / "report.yaml").unlink()
    with pytest.raises(qualify_semantic.SemanticValidationError, match="missing"):
        _validate_manifest(tmp_path, manifest)


# --------------------------------------------- runtime/audit single source


def test_runtime_and_audit_share_one_evaluator():
    """apply_thresholds delegates to the same pure evaluator."""
    report = _valid_report()
    live_shape = {
        "pass": True,
        "first_fail": None,
        "stages": {row["stage"]: {"pass": True, "checks_passed": 3,
                                  "checks_total": 3, "gate_retries": 0}
                   for row in report["stages"]},
        "retries": {"check_gate": 0},
        "defense_checks": report["defense_checks"],
        "points_earned": 21, "points_max": 21,
        "correctness": 100.0,
    }
    metrics = {
        "context_peak_tokens": 9120,
        "framework_input_tokens_max": 6400,
        "framework_input_chars": 25600,
        "framework_input_tokens_method": "host-tokenize",
        "max_unique_files": 1,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
    }
    verdict, failures = qualify.apply_thresholds(live_shape, metrics)
    assert verdict, failures
    # same function flags the same mutation
    live_shape["stages"]["verify"]["pass"] = False
    verdict2, failures2 = qualify.apply_thresholds(live_shape, metrics)
    assert not verdict2
    assert any(f.startswith("T2") for f in failures2)


def test_evaluate_medians_shared():
    med = qualify_evidence.case_medians([
        {"correctness": 100.0, "process": 100.0, "gate_retries": 0,
         "max_unique_files": 5},
        {"correctness": 90.0, "process": 90.0, "gate_retries": 1,
         "max_unique_files": 7},
    ])
    assert med["correctness"] == 95.0
    ok, failures = qualify_evidence.evaluate_case_medians(
        med,
        [{"totals": {"hallucinated_paths": 1, "envelope_violations": 0,
                     "evidence_authentic": True}}],
        THRESHOLDS["absolute"],
    )
    assert not ok
    assert any("T6" in f for f in failures)
