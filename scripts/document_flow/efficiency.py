"""Measured efficiency factor derivation for DeltaFuse benchmark."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

from scripts.document_flow.evaluate import StageFactors


STAGE_CONTEXT_BUDGETS = {
    "intake": 40_000,
    "analyze": 60_000,
    "specify": 80_000,
    "decompose": 60_000,
    "declare": 60_000,
    "implement": 120_000,
    "verify": 60_000,
}


def compute_stage_factors(
    measurements: Mapping[str, Any],
    stage: str,
    provenance_refs: tuple[str, ...] | None = None,
) -> StageFactors:
    """Derive exact rational efficiency factors from stage measurements."""
    prov = provenance_refs or tuple(measurements.get("provenance_refs", ()))
    
    # 1. Context factor
    peak_tokens = measurements.get("context_peak_tokens")
    budget = STAGE_CONTEXT_BUDGETS.get(stage, 100_000)
    
    if peak_tokens is None:
        context_factor = None
    elif peak_tokens <= 0:
        context_factor = Fraction(1, 1)
    elif peak_tokens > 2 * budget:
        context_factor = Fraction(0, 1)
    else:
        # Linear decay from 1.0 down to 0 at 2 * budget
        context_factor = Fraction(max(0, 2 * budget - peak_tokens), 2 * budget)

    # 2. File focus factor
    files_read = measurements.get("files_read", 0)
    files_reread = measurements.get("files_reread", 0)
    if files_read is None:
        file_factor = None
    elif files_read == 0:
        file_factor = Fraction(1, 1)
    else:
        # unique / total ratio
        unique_files = max(1, files_read - files_reread)
        file_factor = Fraction(min(unique_files, files_read), files_read)

    # 3. Tool factor
    tool_calls = measurements.get("tool_calls")
    tool_failures = measurements.get("tool_failures", 0)
    timeouts = measurements.get("timeouts", 0)
    rejected_actions = measurements.get("rejected_actions", 0)
    
    if tool_calls is None:
        tool_factor = None
    elif tool_calls == 0:
        tool_factor = Fraction(1, 1)
    else:
        bad_calls = tool_failures + timeouts + rejected_actions
        tool_factor = Fraction(max(0, tool_calls - bad_calls), tool_calls)

    # 4. Retry factor
    gate_retries = measurements.get("gate_retries", 0)
    evidence_retries = measurements.get("evidence_retries", 0)
    coverage_retries = measurements.get("coverage_retries", 0)
    total_retries = gate_retries + evidence_retries + coverage_retries
    
    if measurements.get("worker_calls") is None:
        retry_factor = None
    elif total_retries == 0:
        retry_factor = Fraction(1, 1)
    elif total_retries >= 5:
        retry_factor = Fraction(0, 1)
    else:
        retry_factor = Fraction(5 - total_retries, 5)

    return StageFactors(
        context=context_factor,
        file_focus=file_factor,
        tools=tool_factor,
        retries=retry_factor,
        provenance_refs=prov if prov else None,
    )
