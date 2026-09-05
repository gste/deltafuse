import pytest
from pathlib import Path
from deltafuse.evals.dataset import EvalCase
from deltafuse.evals.providers import MockLLMProvider
from deltafuse.core.fsm import validate_change_package, check_gate


@pytest.fixture
def sample_case() -> EvalCase:
    return EvalCase(
        case_id="CHG-301-sample",
        title="Test feature case",
        category="feature",
        raw_prompt="Implement test capability",
        expected_primary_capability="test.cap",
        expected_claims=["CR-001", "CR-002"],
        expected_slices=["SLICE-01"],
        expected_target_gate="converged",
    )


def test_mock_provider_golden_scenario(sample_case: EvalCase, tmp_path: Path):
    provider = MockLLMProvider(scenario="golden")
    target_dir = tmp_path / sample_case.case_id
    provider.generate_change_package(sample_case, target_dir)

    errors = validate_change_package(target_dir)
    assert errors == [], f"Golden package validation errors: {errors}"

    gate_errs = check_gate(target_dir, "converged")
    assert gate_errs == [], f"Golden gate errors: {gate_errs}"


def test_mock_provider_schema_violation_scenario(sample_case: EvalCase, tmp_path: Path):
    provider = MockLLMProvider(scenario="schema_violation")
    target_dir = tmp_path / sample_case.case_id
    provider.generate_change_package(sample_case, target_dir)

    errors = validate_change_package(target_dir)
    assert len(errors) > 0, "Schema violation scenario should produce validation errors"


def test_mock_provider_fsm_violation_scenario(sample_case: EvalCase, tmp_path: Path):
    provider = MockLLMProvider(scenario="fsm_violation")
    target_dir = tmp_path / sample_case.case_id
    provider.generate_change_package(sample_case, target_dir)

    gate_errs = check_gate(target_dir, "targeting")
    assert len(gate_errs) > 0, "FSM violation scenario should fail targeting gate due to missing red evidence"


def test_real_llm_provider_requires_api_key(tmp_path: Path):
    from deltafuse.evals.providers import RealLLMProvider
    from deltafuse.evals.dataset import EvalCase
    provider = RealLLMProvider(api_key=None)
    case = EvalCase(
        case_id="CHG-TEST",
        title="Test",
        category="feature",
        raw_prompt="Test",
        expected_claims=["CR-001"],
        expected_primary_capability="system.core",
    )
    with pytest.raises(RuntimeError) as exc_info:
        provider.generate_change_package(case, tmp_path)
    assert "requires DELTAFUSE_API_KEY or OPENAI_API_KEY" in str(exc_info.value)
