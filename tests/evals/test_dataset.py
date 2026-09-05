import tempfile
from pathlib import Path
import pytest
from deltafuse.evals.dataset import EvalCase, EvalDataset


def test_eval_case_creation():
    case = EvalCase(
        case_id="CHG-201-test",
        title="Test Feature",
        category="feature",
        raw_prompt="Add new auth method",
        expected_primary_capability="auth.core",
        expected_claims=["CR-001"],
    )
    assert case.case_id == "CHG-201-test"
    assert case.expected_target_gate == "converged"
    d = case.to_dict()
    assert d["category"] == "feature"
    case2 = EvalCase.from_dict(d)
    assert case2.title == "Test Feature"


def test_default_dataset_loading():
    dataset = EvalDataset.get_default_dataset()
    assert len(dataset) >= 5
    assert dataset.get_case("CHG-101-ipoffline-retry") is not None
    assert dataset.get_case("NON_EXISTENT") is None

    feats = dataset.filter_by_category("feature")
    assert len(feats) >= 2


def test_dataset_save_and_load(tmp_path: Path):
    ds_path = tmp_path / "custom_cases.yaml"
    ds = EvalDataset(
        name="custom_suite",
        description="Suite description",
        cases=[
            EvalCase(
                case_id="CHG-901-custom",
                title="Custom Feature",
                category="feature",
                raw_prompt="Custom prompt",
                expected_primary_capability="cap.custom",
                expected_claims=["CR-001"],
            )
        ],
    )
    ds.save_to_file(ds_path)
    assert ds_path.is_file()

    loaded = EvalDataset.load_from_file(ds_path)
    assert loaded.name == "custom_suite"
    assert len(loaded) == 1
    assert loaded.cases[0].case_id == "CHG-901-custom"
