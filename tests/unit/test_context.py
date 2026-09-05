"""Unit tests for DeltaFuse context contract and budget linter."""

from pathlib import Path
from deltafuse.core.context import (
    estimate_tokens,
    estimate_files_tokens,
    validate_context_budget,
    PHASE_CONTRACTS,
)


def test_estimate_tokens_heuristic():
    text = "Hello world from DeltaFuse framework"
    # 5 words * 1.3 = 6.5 -> ceil(6.5) = 7
    tokens = estimate_tokens(text)
    assert tokens == 7


def test_validate_context_budget(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("word " * 100, encoding="utf-8")  # ~130 tokens
    f2.write_text("word " * 200, encoding="utf-8")  # ~260 tokens

    budget_ok = {"max_tokens": 1000, "max_files": 5}
    assert validate_context_budget(budget_ok, [f1, f2]) == []

    budget_file_exceeded = {"max_tokens": 1000, "max_files": 1}
    errs = validate_context_budget(budget_file_exceeded, [f1, f2])
    assert any("files loaded, maximum allowed is 1" in e for e in errs)

    budget_token_exceeded = {"max_tokens": 200, "max_files": 5}
    errs2 = validate_context_budget(budget_token_exceeded, [f1, f2])
    assert any("tokens loaded, maximum allowed is 200" in e for e in errs2)


def test_phase_contracts_completeness():
    phases = ["intake", "analyze", "specify", "decompose", "target", "implement", "verify"]
    for p in phases:
        assert p in PHASE_CONTRACTS
        assert "allowed_read" in PHASE_CONTRACTS[p]
        assert "allowed_write" in PHASE_CONTRACTS[p]
