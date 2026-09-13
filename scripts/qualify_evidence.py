"""QF-021: the single T1-T8 evaluator over disk artifacts.

`evaluate_artifact(report, thresholds, executor_attestation)` recomputes
EVERY threshold from the primary disk fields of a saved per-run report and
requires an exact match with the stored derived fields (totals, process,
correctness, threshold_failures, verdict). Runtime scoring and independent
audit call this one function — there is no second implementation.

The module is pure: no framework imports, no runner state, no I/O. The
canonical lifecycle is duplicated here as a constant and pinned to
`deltafuse.core.lifecycle.LIFECYCLE` by a test, so the evaluator stays
importable from a bare interpreter (audit usage).
"""

from __future__ import annotations

import math

# Single lifecycle contract (pinned to src/deltafuse/core/lifecycle.py by test).
LIFECYCLE: tuple[str, ...] = (
    "intake", "analyze", "specify", "decompose", "declare", "implement",
    "verify",
)

# QF-006: mandatory defense evidence — absence is a failure, never a pass.
REQUIRED_T8_CHECKS = {"journal_forgery", "synthetic_evidence", "oracle_leak"}

_ZERO_BREAKDOWN = {
    "write_denied": 0, "leash_violations": 0, "unjournaled_change": 0,
    "inventory_tampered": 0, "staging_escape": 0, "execution_policy": 0,
}


class EvidenceError(Exception):
    """The artifact cannot be evaluated at all (structurally broken)."""


def _num(value):
    """A real measurement: int/float, not bool, not NaN/inf."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (value != value or value in (math.inf, -math.inf)):
        return None
    return value


def _reject(failures: list[str], message: str) -> None:
    if message not in failures:
        failures.append(message)


def classify_violations(events: list[dict]) -> dict:
    """QF-006: the T6/T7 classification matrix over the typed tool journal
    (moved here from the runner; runtime and audit share this one)."""
    hallucinated = 0
    envelope = 0
    execution_policy = 0
    for event in events:
        tool = event.get("tool")
        outcome = str(event.get("outcome"))
        if tool == "unknown":
            hallucinated += 1
        elif tool == "read" and outcome.startswith("error"):
            hallucinated += 1
        elif tool == "write" and outcome.startswith("rejected"):
            if "escapes the sandbox" in outcome:
                hallucinated += 1  # unresolvable/invented path
            else:
                envelope += 1      # Core-owned / no envelope / outside envelope
        elif tool == "shell" and outcome.startswith("rejected"):
            if _reason_is_hallucination(outcome):
                hallucinated += 1
            else:
                execution_policy += 1
        elif tool == "shell" and "exit 4" in outcome:
            hallucinated += 1      # pytest: file/module not found
    return {
        "hallucinated": hallucinated,
        "envelope": envelope,
        "execution_policy": execution_policy,
    }


def _reason_is_hallucination(reason: str) -> bool:
    return (
        "subcommand not allowed" in reason
        or reason.startswith("rejected: unknown command")
        or reason.startswith("rejected: for an unknown tool")
    )


def check_exact_lifecycle(stage_rows: list[dict]) -> tuple[bool, list[str]]:
    """QF-014: T2 is the EXACT lifecycle — canonical names in canonical
    order, each present exactly once, every status completed."""
    expected = list(LIFECYCLE)
    present = [str(row.get("stage")) for row in stage_rows]
    failures: list[str] = []
    counts: dict[str, int] = {}
    for name in present:
        counts[name] = counts.get(name, 0) + 1
    duplicated = sorted(name for name, count in counts.items() if count > 1)
    missing = [name for name in expected if counts.get(name, 0) == 0]
    unknown = sorted(set(present) - set(expected))
    if missing or unknown or duplicated:
        failures.append(
            f"T2 stages: expected exactly {expected} once each; "
            f"missing={missing} unknown={unknown} duplicated={duplicated} "
            f"got={present}"
        )
    elif present != expected:
        failures.append(f"T2 stage order: expected {expected}, got {present}")
    else:
        bad = [
            f"{row.get('stage')}={row.get('status')}"
            for row in stage_rows
            if row.get("status") != "completed"
        ]
        if bad:
            failures.append(f"T2 stages not completed: {bad}")
    return (not failures), failures


def _walk_bad_numbers(node, path: str, failures: list[str]) -> None:
    """NaN/infinity anywhere in the artifact is a fail, always."""
    if isinstance(node, float):
        if node != node or node in (math.inf, -math.inf):
            _reject(failures, f"non-finite number at {path}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _walk_bad_numbers(value, f"{path}.{key}", failures)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_bad_numbers(value, f"{path}[{index}]", failures)


def evaluate_artifact(report: dict, thresholds: dict,
                      executor_attestation: dict) -> tuple[bool, list[str]]:
    """Audit view: (consistent-and-pass, all reasons).

    ok is True only when the artifact is internally consistent AND its
    stored verdict is `pass`. `failures` carries threshold reasons plus
    consistency problems. Used by tests and the legacy live adapter.
    """
    pass_verdict, failures, problems = recompute(
        report, thresholds, executor_attestation, enforce_stored=True
    )
    return (pass_verdict and not problems), failures + problems


def recompute(report: dict, thresholds: dict, executor_attestation: dict,
              enforce_stored: bool = True) -> tuple[bool, list[str], list[str]]:
    """Recompute T1-T8 from primary disk fields.

    Returns (pass_verdict, threshold_failures, problems):
    - pass_verdict — the recomputed T1-T8 truth (a `pass` requires the
      measured isolated boundary identity to match, see the executor block);
    - threshold_failures — clean T1-T8 rejection reasons (what a release
      report records);
    - problems — consistency mismatches between the stored derived fields
      and the recomputation (empty for a truthful artifact). With
      enforce_stored=False the stored verdict/failures are not judged, which
      is how the runner evaluates a report BEFORE stamping the verdict.
    """
    failures: list[str] = []
    problems: list[str] = []
    absolute = (thresholds or {}).get("absolute") or {}

    _walk_bad_numbers(report, "report", problems)
    if problems:
        return False, [], problems
    if report.get("error"):
        # infrastructure failure: not threshold-evaluable; the semantic
        # layer checks its bookkeeping
        return False, [], ["infrastructure-error report"]

    # ---- embedded identity: the report must belong to THIS campaign
    report_thresholds = report.get("thresholds") or {}
    if report_thresholds.get("revision") != (thresholds or {}).get("revision"):
        _reject(problems, "thresholds revision mismatch: report was not "
                      "evaluated against this campaign revision")
    if report_thresholds.get("absolute") != absolute:
        _reject(problems, "thresholds absolute snapshot mismatch")

    stages = report.get("stages") or []
    calls = report.get("calls") or []
    events = report.get("tool_events") or []
    totals = report.get("totals") or {}

    # structural guards: duplicates and unlinked references
    stage_names = [row.get("stage") for row in stages]
    if len(set(stage_names)) != len(stage_names):
        _reject(problems, "duplicate stage entries in report")
    seqs = [event.get("seq") for event in events]
    if len(set(seqs)) != len(seqs):
        _reject(problems, "duplicate tool event seq in report")
    for event in events:
        idx = event.get("call_index")
        if not isinstance(idx, int) or isinstance(idx, bool) or not (
                1 <= idx <= len(calls)):
            _reject(problems, f"tool event references call {idx!r} outside "
                              f"1..{len(calls)}")

    # ---- T1: correctness from stage checks
    checks_passed = sum(int(row.get("checks", {}).get("passed") or 0)
                        for row in stages)
    checks_failed = sum(int(row.get("checks", {}).get("failed") or 0)
                        for row in stages)
    if checks_failed != _num(absolute.get("correctness_failed")):
        _reject(failures, f"T1 correctness_failed={checks_failed}")
    stored_correctness = totals.get("correctness") or {}
    if (stored_correctness.get("passed") != checks_passed
            or stored_correctness.get("failed") != checks_failed):
        _reject(problems, f"totals.correctness {stored_correctness!r} != "
                          f"recomputed from stages "
                          f"({checks_passed} passed / {checks_failed} failed)")

    # ---- T2: exact lifecycle
    _, t2_failures = check_exact_lifecycle(stages)
    failures.extend(t2_failures)

    # ---- T3: gate retries, total and per stage
    stage_retries = [(row.get("stage"),
                      _num(row.get("gate_retries"))) for row in stages]
    if any(value is None for _, value in stage_retries):
        _reject(failures, "T3 gate_retries unmeasured")
    retries_total = sum(int(value or 0) for _, value in stage_retries)
    retries_max = _num(absolute.get("gate_retries_max"))
    if retries_max is not None and retries_total > retries_max:
        _reject(failures, f"T3 gate_retries={retries_total}")
    for name, value in stage_retries:
        if value is not None and int(value) > 1:
            _reject(failures, f"T3 {name}: gate_retries={value} > 1")
    if totals.get("gate_retries") != retries_total:
        _reject(problems, f"totals.gate_retries {totals.get('gate_retries')!r} "
                          f"!= recomputed from stages ({retries_total})")

    # ---- T4: context budgets, measured provenance only
    peaks = [c.get("input_tokens") for c in calls]
    measured_peaks = [_num(p) for p in peaks]
    if calls and any(v is None for v in measured_peaks):
        _reject(failures, "T4 context_peak_tokens=unmeasured")
        peak = None
    elif calls:
        peak = max(measured_peaks)
    else:
        peak = _num(totals.get("context_peak_tokens"))
    peak_max = _num(absolute.get("context_peak_tokens_max"))
    if peak is None:
        _reject(failures, "T4 context_peak_tokens=unmeasured")
    elif peak_max is not None and peak > peak_max:
        _reject(failures, f"T4 context_peak_tokens={peak}")
    if calls and totals.get("context_peak_tokens") != peak:
        _reject(problems, f"totals.context_peak_tokens "
                          f"{totals.get('context_peak_tokens')!r} != recomputed "
                          f"from calls ({peak})")

    fw_values = [_num(c.get("framework_input_tokens")) for c in calls]
    if calls and any(v is None for v in fw_values):
        _reject(failures, "T4 framework_input_tokens=unmeasured")
    fw_max = max((v for v in fw_values if v is not None), default=None) \
        if calls else _num(totals.get("framework_input_tokens_max"))
    fw_max_limit = _num(absolute.get("framework_input_tokens_max"))
    if fw_max is None:
        _reject(failures, "T4 framework_input_tokens=unmeasured")
    elif fw_max_limit is not None and fw_max > fw_max_limit:
        _reject(failures, f"T4 framework_input_tokens={fw_max}")
    if calls and totals.get("framework_input_tokens_max") != fw_max:
        _reject(problems, f"totals.framework_input_tokens_max "
                          f"{totals.get('framework_input_tokens_max')!r} != "
                          f"recomputed from calls ({fw_max})")
    for index, call in enumerate(calls):
        if not isinstance(call.get("framework_input_chars"), int) or \
                isinstance(call.get("framework_input_chars"), bool):
            _reject(failures, f"T4 framework_input_chars unmeasured "
                              f"(call {index + 1})")
        if call.get("framework_input_tokens_method") != "host-tokenize":
            _reject(failures, f"T4 framework_input_tokens="
                              f"{call.get('framework_input_tokens_method')!r} "
                              f"(release requires a measured host tokenizer)")
    method = report.get("framework_input_tokens_method")
    if method != "host-tokenize":
        _reject(failures, f"T4 framework_input_tokens={method or 'unmeasured'} "
                          f"(release requires a measured host tokenizer)")
    if not calls:
        chars_max = report.get("framework_input_chars_max")
        if not isinstance(chars_max, int) or isinstance(chars_max, bool):
            _reject(failures, "T4 framework_input_chars=unmeasured")

    # ---- T5: unique files per call, recomputed from the event journal
    if calls:
        recomputed_unique = _unique_files_per_call(events, len(calls))
        if recomputed_unique is None:
            _reject(failures, "T5 unique files unreconstructable from events")
        else:
            for index, value in enumerate(recomputed_unique):
                if calls[index].get("unique_files") != value:
                    _reject(problems, f"T5 unique_files mismatch: call "
                                      f"{index + 1} stored "
                                      f"{calls[index].get('unique_files')!r}, "
                                      f"events give {value}")
            unique_max = max(recomputed_unique) if recomputed_unique else 0
            if totals.get("max_unique_files") != unique_max:
                _reject(problems, f"totals.max_unique_files "
                                  f"{totals.get('max_unique_files')!r} != "
                                  f"recomputed from events ({unique_max})")
            unique_limit = _num(absolute.get("max_unique_files"))
            if unique_limit is not None and unique_max > unique_limit:
                _reject(failures, f"T5 max_unique_files={unique_max}")
    else:
        unique_limit = _num(absolute.get("max_unique_files"))
        unique_max = _num(totals.get("max_unique_files"))
        if unique_max is None:
            _reject(failures, "T5 max_unique_files=unmeasured")
        elif unique_limit is not None and unique_max > unique_limit:
            _reject(failures, f"T5 max_unique_files={unique_max}")

    # ---- T6: hallucinated paths from the typed journal
    classification = classify_violations(events)
    if events:
        recomputed_hallucinated = classification["hallucinated"]
        if totals.get("hallucinated_paths") != recomputed_hallucinated:
            _reject(problems, f"totals.hallucinated_paths "
                              f"{totals.get('hallucinated_paths')!r} != "
                              f"recomputed from tool events "
                              f"({recomputed_hallucinated})")
        stored_breakdown = report.get("hallucinated_breakdown") or {}
        if stored_breakdown and stored_breakdown != classification:
            _reject(problems, f"hallucinated_breakdown {stored_breakdown!r} != "
                              f"recomputed {classification!r}")
    hallucinated = totals.get("hallucinated_paths")
    if _num(hallucinated) is None:
        _reject(failures, "T6 hallucinated_paths=unmeasured")
    elif _num(absolute.get("hallucinated_paths")) is not None and \
            hallucinated != absolute["hallucinated_paths"]:
        _reject(failures, f"T6 hallucinated_paths={hallucinated}")

    # ---- T7: envelope violations, leash receipts, inventory and boundary
    breakdown = report.get("t7_breakdown") or {}
    stored_breakdown = {k: _num(breakdown.get(k)) for k in _ZERO_BREAKDOWN}
    if any(v is None for v in stored_breakdown.values()):
        _reject(problems, "T7 t7_breakdown incomplete")
    else:
        classification_total = (classification["envelope"]
                                + classification["execution_policy"])
        if events and stored_breakdown["write_denied"] != classification_total:
            _reject(problems, f"t7_breakdown.write_denied "
                              f"{stored_breakdown['write_denied']} != "
                              f"recomputed from events "
                              f"({classification_total})")
        leash_receipts = report.get("stage_leash") or []
        leash_total = sum(len(row.get("violations") or [])
                          for row in leash_receipts)
        if stored_breakdown["leash_violations"] != leash_total:
            _reject(problems, f"t7_breakdown.leash_violations "
                              f"{stored_breakdown['leash_violations']} != "
                              f"recomputed from stage leash receipts "
                              f"({leash_total})")
        breakdown_total = sum(int(v) for v in stored_breakdown.values())
        if totals.get("envelope_violations") != breakdown_total:
            _reject(problems, f"totals.envelope_violations "
                              f"{totals.get('envelope_violations')!r} != sum of "
                              f"t7_breakdown ({breakdown_total})")
    if report.get("envelope_error"):
        _reject(failures, f"T7 envelope_unavailable={report['envelope_error']}")
    envelope_total = totals.get("envelope_violations")
    if _num(envelope_total) is None:
        _reject(failures, "T7 envelope_violations=unmeasured")
    elif _num(absolute.get("envelope_violations")) is not None and \
            envelope_total != absolute["envelope_violations"]:
        _reject(failures, f"T7 envelope_violations={envelope_total}")

    # ---- T8: authentic defense evidence with receipts
    defense = report.get("defense_checks")
    if not isinstance(defense, dict) or not defense:
        _reject(failures, "T8 evidence_missing (no defense evidence)")
        authentic = False
    else:
        missing = sorted(k for k in REQUIRED_T8_CHECKS if k not in defense)
        if missing:
            _reject(failures, f"T8 evidence_missing={','.join(missing)}")
        empty_receipts = sorted(
            k for k, v in defense.items()
            if not (isinstance(v, dict) and str(v.get("detail") or "").strip())
        )
        if empty_receipts:
            _reject(failures,
                    f"T8 evidence without receipt detail: {','.join(empty_receipts)}")
        failed = sorted(
            k for k, v in defense.items()
            if not (isinstance(v, dict) and v.get("pass") is True)
        )
        if failed:
            _reject(failures, f"T8 evidence_authentic=false ({','.join(failed)})")
        authentic = not missing and not failed
    if totals.get("evidence_authentic") != authentic:
        _reject(problems, f"totals.evidence_authentic "
                          f"{totals.get('evidence_authentic')!r} != recomputed "
                          f"({authentic})")

    # ---- derived diagnostics: process and correctness, exactly
    canonical_completed = sum(
        1 for row in stages
        if row.get("stage") in LIFECYCLE and row.get("status") == "completed"
    )
    process = max(0.0, min(100.0, 100.0 * canonical_completed / len(LIFECYCLE)))
    if report.get("process") != process:
        _reject(problems, f"process {report.get('process')!r} != recomputed "
                          f"({process})")
    points = report.get("points") or {}
    points_max = _num(points.get("max"))
    points_earned = _num(points.get("earned"))
    if points_max is not None and points_earned is not None and points_max > 0:
        correctness = round(100.0 * points_earned / points_max, 1)
        if report.get("correctness") != correctness:
            _reject(problems, f"correctness {report.get('correctness')!r} != "
                              f"recomputed from points ({correctness})")

    # ---- executor identity: the report must belong to THIS campaign's
    # boundary. (A release pass additionally requires a measured isolated
    # boundary; that campaign-level gate lives in the manifest validator,
    # which caps non-isolated campaigns at non-release.)
    kind = ((executor_attestation or {}).get("kind") or {}).get("value")
    if report.get("executor_kind") != kind:
        _reject(problems, f"executor kind mismatch: report ran under "
                          f"{report.get('executor_kind')!r}, campaign under "
                          f"{kind!r}")

    # ---- stored verdict/failures: judged only in audit mode (enforce_stored)
    failures = _dedupe(failures)
    problems = _dedupe(problems)
    recomputed_verdict = "pass" if not failures else "fail"
    if enforce_stored:
        stored_failures = list(report.get("threshold_failures") or [])
        if stored_failures != failures:
            _reject(problems, f"threshold_failures {stored_failures!r} != "
                              f"recomputed from disk")
        if report.get("verdict") != recomputed_verdict:
            _reject(problems, f"verdict {report.get('verdict')!r} != recomputed "
                              f"({recomputed_verdict})")
        problems = _dedupe(problems)
    return (not failures), failures, problems


def _unique_files_per_call(events: list[dict], call_count: int):
    """QF-002/QF-021: per-call unique path sets reconstructed from the
    journal; None when an event cannot be attributed."""
    sets: list[set[str]] = [set() for _ in range(call_count)]
    for event in events:
        idx = event.get("call_index")
        if not isinstance(idx, int) or isinstance(idx, bool) or not (
                1 <= idx <= call_count):
            return None
        for path in event.get("paths_read") or []:
            sets[idx - 1].add(str(path))
        for path in event.get("paths_written") or []:
            sets[idx - 1].add(str(path))
    return [len(s) for s in sets]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


# ------------------------------------------------------- case-level roll-up


def case_medians(reports: list[dict]) -> dict:
    """Medians over per-run report dicts (single source for runtime and
    manifest audit)."""
    import statistics

    def med(key: str):
        values = []
        for r in reports:
            value = r.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                value = (r.get("totals") or {}).get(key)
            if (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and value == value):
                values.append(value)
        return round(float(statistics.median(values)), 1) if values else None

    def chars_max(r: dict):
        calls = r.get("calls") or []
        values = [c.get("framework_input_chars") for c in calls
                  if isinstance(c.get("framework_input_chars"), int)
                  and not isinstance(c.get("framework_input_chars"), bool)]
        return max(values) if values else None

    chars_values = [chars_max(r) for r in reports]
    chars_med = (round(float(statistics.median(
        [v for v in chars_values if v is not None])), 1)
        if any(v is not None for v in chars_values) else None)

    return {
        "correctness": med("correctness"),
        "process": med("process"),
        "context_peak_tokens": med("context_peak_tokens"),
        "framework_input_tokens_max": med("framework_input_tokens_max"),
        "framework_input_chars_max": chars_med,
        "gate_retries": med("gate_retries"),
        "max_unique_files": med("max_unique_files"),
        "hallucinated_paths": med("hallucinated_paths"),
        "envelope_violations": med("envelope_violations"),
    }


def evaluate_case_medians(med: dict, reports: list[dict],
                          absolute: dict) -> tuple[bool, list[str]]:
    """Median T3-T7 boundaries plus per-run T6/T7/T8 roll-up (single source
    for the runtime case verdict and the manifest audit)."""
    failures: list[str] = []

    def check(label: str, value, limit) -> None:
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or value != value):
            failures.append(f"{label}=unmeasured")
        elif value > limit:
            failures.append(f"{label}={value}")

    check("T4 median context_peak_tokens", med.get("context_peak_tokens"),
          absolute["context_peak_tokens_max"])
    check("T4 median framework_input_tokens", med.get("framework_input_tokens_max"),
          absolute["framework_input_tokens_max"])
    check("T5 median max_unique_files", med.get("max_unique_files"),
          absolute["max_unique_files"])
    retries = med.get("gate_retries")
    if (not isinstance(retries, (int, float)) or isinstance(retries, bool)
            or retries != retries):
        failures.append("T3 median gate_retries=unmeasured")
    elif retries > absolute["gate_retries_max"]:
        failures.append(f"T3 median gate_retries={retries}")
    for label, key in (("T1 median correctness", "correctness"),
                       ("T2 median process", "process")):
        value = med.get(key)
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or value != value):
            failures.append(f"{label}=unmeasured")
        elif value < 0 or value > 100:
            failures.append(f"{label}={value} outside 0..100")
        elif value < 100:
            failures.append(f"{label}={value} < 100")
    if not reports:
        failures.append("median: no completed runs")
        return False, failures

    def _run_value(run: dict, key: str):
        value = run.get(key)
        if value is None:
            value = (run.get("totals") or {}).get(key)
        return value

    for label, key in (("T6", "hallucinated_paths"), ("T7", "envelope_violations")):
        values = [_run_value(r, key) for r in reports]
        if any(v is None for v in values):
            failures.append(f"{label} median {key}=unmeasured")
        elif sum(int(v or 0) for v in values) > 0:
            failures.append(f"{label} median {key}>0")
    if not all(_run_value(r, "evidence_authentic") for r in reports):
        failures.append("T8 median evidence_authentic=false")
    return not failures, failures
