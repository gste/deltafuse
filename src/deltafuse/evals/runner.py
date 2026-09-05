# Test Runner and Evaluation Engine for DeltaFuse LLM Evals.

from __future__ import annotations
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any
import yaml

from deltafuse.core.fsm import validate_change_package, check_gate
from deltafuse.core.integrity import extract_claims_from_request
from deltafuse.evals.dataset import EvalCase, EvalDataset
from deltafuse.evals.metrics import CaseEvalResult, EvalReport
from deltafuse.evals.providers import LLMProvider


def calculate_f1(actual: set[str], expected: set[str]) -> tuple[float, float, float]:
    if not expected:
        return (1.0, 1.0, 1.0) if not actual else (0.0, 1.0, 0.0)
    if not actual:
        return (0.0, 0.0, 0.0)
    tp = len(actual & expected)
    precision = tp / len(actual)
    recall = tp / len(expected)
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)
    return precision, recall, f1


def evaluate_single_case(
    case: EvalCase,
    provider: LLMProvider,
    work_dir: Path,
) -> CaseEvalResult:
    case_dir = work_dir / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    provider.generate_change_package(case, case_dir)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    failure_reasons: list[str] = []

    # 1. Schema compliance
    schema_errors = validate_change_package(case_dir)
    schema_compliance = len(schema_errors) == 0
    if not schema_compliance:
        failure_reasons.append(f"Schema errors: {'; '.join(schema_errors)}")

    # 2. Gate checking
    gate_passed = False
    gate_errors: list[str] = []
    if case.expected_target_gate:
        gate_errors = check_gate(case_dir, case.expected_target_gate)
        gate_passed = len(gate_errors) == 0
        if not gate_passed:
            failure_reasons.append(f"Gate {case.expected_target_gate} errors: {'; '.join(gate_errors)}")
    else:
        gate_passed = True

    # 3. Routing evaluation
    routing_match = False
    assigned_capability = ""
    routing_file = case_dir / "routing.yaml"
    if routing_file.is_file():
        try:
            r_data = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
            if isinstance(r_data, dict) and "claims" in r_data and isinstance(r_data["claims"], dict):
                first_claim = next(iter(r_data["claims"].values()), {})
                assigned_capability = first_claim.get("primary_capability", "")
        except Exception:
            pass

    routing_match = (assigned_capability == case.expected_primary_capability)
    if not routing_match:
        failure_reasons.append(f"Routing mismatch: got '{assigned_capability}', expected '{case.expected_primary_capability}'")

    # 4. Claim extraction F1
    extracted_claims: list[str] = []
    request_file = case_dir / "request.md"
    if request_file.is_file():
        try:
            req_content = request_file.read_text(encoding="utf-8")
            extracted_claims = extract_claims_from_request(req_content)
        except Exception:
            pass

    expected_set = set(case.expected_claims)
    extracted_set = set(extracted_claims)
    prec, rec, f1 = calculate_f1(extracted_set, expected_set)
    if f1 < 0.99:
        failure_reasons.append(f"Claim mismatch: extracted {extracted_claims}, expected {case.expected_claims}")

    # Overall case PASS/FAIL
    if case.expected_outcome == "pass":
        overall_pass = schema_compliance and gate_passed and routing_match and (f1 >= 0.99)
    else:
        overall_pass = schema_compliance and gate_passed and (f1 >= 0.99)

    status = "PASS" if overall_pass else "FAIL"

    return CaseEvalResult(
        case_id=case.case_id,
        title=case.title,
        category=case.category,
        target_gate=case.expected_target_gate,
        expected_outcome=case.expected_outcome,
        schema_compliance=schema_compliance,
        schema_errors=schema_errors,
        gate_passed=gate_passed,
        gate_errors=gate_errors,
        routing_match=routing_match,
        assigned_capability=assigned_capability,
        expected_capability=case.expected_primary_capability,
        extracted_claims=extracted_claims,
        expected_claims=case.expected_claims,
        claim_precision=prec,
        claim_recall=rec,
        claim_f1=f1,
        latency_ms=latency_ms,
        status=status,
        failure_reasons=failure_reasons,
    )


def run_eval(
    dataset: EvalDataset,
    provider: LLMProvider,
    output_dir: Path | str | None = None,
) -> EvalReport:
    cleanup_temp = False
    if output_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="deltafuse_eval_"))
        cleanup_temp = True
    else:
        work_dir = Path(output_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    case_results: list[CaseEvalResult] = []
    t_start = time.perf_counter()

    try:
        for case in dataset.cases:
            res = evaluate_single_case(case, provider, work_dir)
            case_results.append(res)
    finally:
        if cleanup_temp:
            shutil.rmtree(work_dir, ignore_errors=True)

    total_duration_ms = (time.perf_counter() - t_start) * 1000.0
    total_cases = len(case_results)
    passed_cases = sum(1 for c in case_results if c.status == "PASS")
    failed_cases = total_cases - passed_cases

    schema_compliance_count = sum(1 for c in case_results if c.schema_compliance)
    gate_pass_count = sum(1 for c in case_results if c.gate_passed)
    routing_match_count = sum(1 for c in case_results if c.routing_match)
    avg_f1 = sum(c.claim_f1 for c in case_results) / max(1, total_cases)

    schema_compliance_rate = (schema_compliance_count / max(1, total_cases)) * 100.0
    gate_pass_rate = (gate_pass_count / max(1, total_cases)) * 100.0
    routing_accuracy = (routing_match_count / max(1, total_cases)) * 100.0

    scenario = getattr(provider, "scenario", "custom")

    return EvalReport(
        dataset_name=dataset.name,
        provider_name=provider.name,
        scenario=scenario,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        schema_compliance_rate=schema_compliance_rate,
        gate_pass_rate=gate_pass_rate,
        routing_accuracy=routing_accuracy,
        average_claim_f1=avg_f1,
        total_duration_ms=total_duration_ms,
        case_results=case_results,
    )
