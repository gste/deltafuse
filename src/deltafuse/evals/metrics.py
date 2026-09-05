# Evaluation metrics and report models for DeltaFuse LLM Evals.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseEvalResult:
    case_id: str
    title: str
    category: str
    target_gate: str
    expected_outcome: str
    schema_compliance: bool
    schema_errors: list[str] = field(default_factory=list)
    gate_passed: bool = False
    gate_errors: list[str] = field(default_factory=list)
    routing_match: bool = False
    assigned_capability: str = ""
    expected_capability: str = ""
    extracted_claims: list[str] = field(default_factory=list)
    expected_claims: list[str] = field(default_factory=list)
    claim_precision: float = 0.0
    claim_recall: float = 0.0
    claim_f1: float = 0.0
    latency_ms: float = 0.0
    status: str = "FAIL"  # "PASS" or "FAIL"
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "category": self.category,
            "target_gate": self.target_gate,
            "expected_outcome": self.expected_outcome,
            "status": self.status,
            "schema_compliance": self.schema_compliance,
            "schema_errors": self.schema_errors,
            "gate_passed": self.gate_passed,
            "gate_errors": self.gate_errors,
            "routing_match": self.routing_match,
            "assigned_capability": self.assigned_capability,
            "expected_capability": self.expected_capability,
            "extracted_claims": self.extracted_claims,
            "expected_claims": self.expected_claims,
            "claim_precision": round(self.claim_precision, 4),
            "claim_recall": round(self.claim_recall, 4),
            "claim_f1": round(self.claim_f1, 4),
            "latency_ms": round(self.latency_ms, 2),
            "failure_reasons": self.failure_reasons,
        }


@dataclass
class EvalReport:
    dataset_name: str
    provider_name: str
    scenario: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    schema_compliance_rate: float  # 0.0 to 100.0%
    gate_pass_rate: float          # 0.0 to 100.0%
    routing_accuracy: float        # 0.0 to 100.0%
    average_claim_f1: float        # 0.0 to 1.0
    total_duration_ms: float
    case_results: list[CaseEvalResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "provider_name": self.provider_name,
            "scenario": self.scenario,
            "metrics": {
                "total_cases": self.total_cases,
                "passed_cases": self.passed_cases,
                "failed_cases": self.failed_cases,
                "schema_compliance_rate": round(self.schema_compliance_rate, 2),
                "gate_pass_rate": round(self.gate_pass_rate, 2),
                "routing_accuracy": round(self.routing_accuracy, 2),
                "average_claim_f1": round(self.average_claim_f1, 4),
                "total_duration_ms": round(self.total_duration_ms, 2),
            },
            "cases": [c.to_dict() for c in self.case_results],
        }

    def to_summary_text(self) -> str:
        lines = [
            "=" * 70,
            f" DeltaFuse LLM Eval Summary: {self.dataset_name} ({self.provider_name})",
            "=" * 70,
            f" Total Cases Evaluated   : {self.total_cases}",
            f" Cases Passed (Overall)  : {self.passed_cases} ({self.passed_cases / max(1, self.total_cases) * 100:.1f}%)",
            f" Cases Failed            : {self.failed_cases}",
            "-" * 70,
            f" Schema Compliance Rate  : {self.schema_compliance_rate:.1f}%",
            f" Gate Pass Rate          : {self.gate_pass_rate:.1f}%",
            f" Routing Accuracy        : {self.routing_accuracy:.1f}%",
            f" Claim Extraction Avg F1 : {self.average_claim_f1:.4f}",
            f" Total Duration          : {self.total_duration_ms:.2f} ms",
            "-" * 70,
            f" {'Case ID':<16} | {'Status':<6} | {'Schema':<6} | {'Gate':<6} | {'Routing':<7} | {'F1':<5} | Title",
            "-" * 70,
        ]
        for c in self.case_results:
            schema_s = "OK" if c.schema_compliance else "FAIL"
            gate_s = "OK" if c.gate_passed else "FAIL"
            rout_s = "OK" if c.routing_match else "FAIL"
            title_trunc = (c.title[:25] + "..") if len(c.title) > 27 else c.title
            lines.append(
                f" {c.case_id:<16} | {c.status:<6} | {schema_s:<6} | {gate_s:<6} | {rout_s:<7} | {c.claim_f1:<5.2f} | {title_trunc}"
            )
        lines.append("=" * 70)
        return "\n".join(lines)

    def to_markdown(self) -> str:
        md = [
            f"# DeltaFuse LLM Evaluation Report",
            f"",
            f"- **Dataset**: `{self.dataset_name}`",
            f"- **Provider / Scenario**: `{self.provider_name}` (`{self.scenario}`)",
            f"- **Total Duration**: `{self.total_duration_ms:.2f} ms`",
            f"",
            f"## Aggregate Metrics",
            f"",
            f"| Metric | Value |",
            f"|---|---|",
            f"| **Total Cases** | {self.total_cases} |",
            f"| **Overall Passed** | {self.passed_cases} / {self.total_cases} ({self.passed_cases / max(1, self.total_cases) * 100:.1f}%) |",
            f"| **Schema Compliance Rate** | {self.schema_compliance_rate:.1f}% |",
            f"| **Gate Pass Rate** | {self.gate_pass_rate:.1f}% |",
            f"| **Routing Accuracy** | {self.routing_accuracy:.1f}% |",
            f"| **Claim Extraction F1** | {self.average_claim_f1:.4f} |",
            f"",
            f"## Detailed Case Results",
            f"",
            f"| Case ID | Status | Schema | Gate | Routing | Claim F1 | Title |",
            f"|---|---|---|---|---|---|---|",
        ]
        for c in self.case_results:
            st_str = "PASS" if c.status == "PASS" else "FAIL"
            sc_str = "OK" if c.schema_compliance else "FAIL"
            gt_str = "OK" if c.gate_passed else "FAIL"
            rt_str = "OK" if c.routing_match else "FAIL"
            md.append(f"| `{c.case_id}` | **{st_str}** | {sc_str} | {gt_str} | {rt_str} | `{c.claim_f1:.2f}` | {c.title} |")
        return "\n".join(md)
