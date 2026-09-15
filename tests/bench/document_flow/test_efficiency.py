"""Tests for measured efficiency factor derivation (J03-407)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from scripts.document_flow.efficiency import STAGE_CONTEXT_BUDGETS, compute_stage_factors
from scripts.document_flow.evaluate import StageFactors


def test_compute_stage_factors_full_perfect():
    measurements = {
        "context_peak_tokens": 20_000,
        "files_read": 10,
        "files_reread": 0,
        "tool_calls": 15,
        "tool_failures": 0,
        "timeouts": 0,
        "rejected_actions": 0,
        "worker_calls": 1,
        "gate_retries": 0,
        "evidence_retries": 0,
        "coverage_retries": 0,
        "provenance_refs": ["ref-1", "ref-2"],
    }
    factors = compute_stage_factors(measurements, stage="intake")
    assert isinstance(factors, StageFactors)
    # Intake budget = 40_000, peak = 20_000 -> (80_000 - 20_000) / 80_000 = 60_000 / 80_000 = 3/4
    assert factors.context == Fraction(3, 4)
    # File focus: 10/10 = 1/1
    assert factors.file_focus == Fraction(1, 1)
    # Tools: 15/15 = 1/1
    assert factors.tools == Fraction(1, 1)
    # Retries: 0 retries -> 1/1
    assert factors.retries == Fraction(1, 1)
    assert factors.provenance_refs == ("ref-1", "ref-2")


def test_compute_stage_factors_missing_telemetry():
    measurements = {}
    factors = compute_stage_factors(measurements, stage="specify")
    assert factors.context is None
    assert factors.file_focus == Fraction(1, 1)  # 0 reads default to 1/1
    assert factors.tools is None
    assert factors.retries is None
    assert factors.provenance_refs is None


def test_compute_stage_factors_edge_cases():
    # Exceeded budget (> 2 * budget)
    measurements = {
        "context_peak_tokens": 200_000,
        "files_read": 10,
        "files_reread": 8,
        "tool_calls": 10,
        "tool_failures": 5,
        "timeouts": 3,
        "rejected_actions": 2,
        "worker_calls": 5,
        "gate_retries": 2,
        "evidence_retries": 2,
        "coverage_retries": 1,
    }
    factors = compute_stage_factors(measurements, stage="analyze")  # budget 60_000, 2*budget = 120_000
    assert factors.context == Fraction(0, 1)
    # 10 read, 8 reread -> 2 unique -> 2/10 = 1/5
    assert factors.file_focus == Fraction(1, 5)
    # tool_calls = 10, bad = 5+3+2 = 10 -> 0/10 = 0/1
    assert factors.tools == Fraction(0, 1)
    # total retries = 5 -> >=5 retries = 0/1
    assert factors.retries == Fraction(0, 1)


def test_compute_stage_factors_partial_retries():
    measurements = {
        "worker_calls": 2,
        "gate_retries": 1,
        "evidence_retries": 1,
        "coverage_retries": 0,
    }
    factors = compute_stage_factors(measurements, stage="declare")
    # total retries = 2 -> (5 - 2)/5 = 3/5
    assert factors.retries == Fraction(3, 5)
