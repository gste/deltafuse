import copy
import json
from pathlib import Path

import pytest

from scripts.document_flow.registry import RegistryError, load_registry


REGISTRY_PATH = Path("scripts/document_flow/contracts/checks.json")


def _document():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _write(tmp_path, document):
    path = tmp_path / "checks.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_published_group_totals_and_hard_gates_are_frozen():
    registry = load_registry(REGISTRY_PATH)

    assert registry.version == "J03-checks-1"
    assert registry.group_totals == {
        **{f"stage.{stage}.correctness": 600 for stage in registry.stages},
        **{f"stage.{stage}.discipline": 250 for stage in registry.stages},
        "system.functional": 1800,
        "system.resilience": 600,
        "system.compatibility": 400,
        "system.efficiency": 200,
    }
    assert registry.hard_gate_ids == frozenset(
        {"GATE.CONTEXT_CAP", "GATE.TELEMETRY_COMPLETE", "GATE.LIFECYCLE_COMPLETE", "GATE.QUALIFIED_PROVENANCE"}
    )
    assert all(check.hard_gate for check in registry.checks)
    assert registry.sha256 == registry.compute_sha256()
    expected_correctness = {
        *(f"{prefix}.C{number:02d}" for prefix in ("IN", "AN", "SP", "DE", "RD", "IM", "VE") for number in range(1, 5))
    }
    expected_discipline = {
        *(f"{prefix}.D{number:02d}" for prefix in ("IN", "AN", "SP", "DE", "RD", "IM", "VE") for number in range(1, 6))
    }
    expected_system = {
        *(f"SYS.F{number:02d}" for number in range(1, 10)),
        *(f"SYS.R{number:02d}" for number in range(1, 5)),
        *(f"SYS.C{number:02d}" for number in range(1, 5)),
        *(f"SYS.E{number:02d}" for number in range(1, 5)),
    }
    assert {check.id for check in registry.checks} == expected_correctness | expected_discipline | expected_system


def test_duplicate_id_is_rejected(tmp_path):
    document = _document()
    document["checks"].append(copy.deepcopy(document["checks"][0]))

    with pytest.raises(RegistryError, match="duplicate check id"):
        load_registry(_write(tmp_path, document))


def test_changed_group_total_is_rejected(tmp_path):
    document = _document()
    document["checks"][0]["points"] -= 1

    with pytest.raises(RegistryError, match="group total"):
        load_registry(_write(tmp_path, document))


def test_missing_category_is_rejected(tmp_path):
    document = _document()
    document["checks"] = [
        check for check in document["checks"] if check["category"] != "discipline"
    ]

    with pytest.raises(RegistryError, match="missing category"):
        load_registry(_write(tmp_path, document))


def test_unknown_outcome_id_is_rejected():
    registry = load_registry(REGISTRY_PATH)

    with pytest.raises(RegistryError, match="unknown outcome check id"):
        registry.validate_outcome_ids(["IN.C01", "NOT.REGISTERED"])


def test_runtime_data_cannot_override_points():
    registry = load_registry(REGISTRY_PATH)

    with pytest.raises(RegistryError, match="outcomes may contain only"):
        registry.validate_outcomes([{"check_id": "IN.C01", "status": "pass", "points": 9999}])
