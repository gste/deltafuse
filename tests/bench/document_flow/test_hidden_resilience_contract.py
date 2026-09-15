"""Contract tests for bounded, receipt-derived resilience scoring."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[3]
HIDDEN = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"


def _load(name):
    spec = importlib.util.spec_from_file_location("j03_resilience_" + name, HIDDEN / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resilience_registry_is_fixed_and_complete():
    checks = _load("test_resilience.py").CHECKS
    assert [check["id"] for check in checks] == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]
    assert sum(check["points"] for check in checks) == 600
    assert all(check["assertions"] and check["fault"] for check in checks)


def test_atomicity_registry_is_fixed():
    checks = _load("test_atomicity.py").CHECKS
    assert checks[0]["id"] == "SYS.C01"
    assert checks[0]["points"] == 160
    assert len(checks[0]["assertions"]) == 3


def test_missing_fault_receipt_is_fail_closed():
    resilience = _load("test_resilience.py")
    facts = resilience.derive_facts({})
    assert resilience.earned_points(facts) == 0
    assert resilience.expected_failed_ids(facts) == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]


def test_unacknowledged_fault_cannot_earn_points():
    resilience = _load("test_resilience.py")
    observation = {"fault_receipts": [{"point": "after-commit-before-ack",
                                         "acknowledged": False,
                                         "measured_sequence": 4,
                                         "recovered": True, "effect_count": 1}]}
    assert resilience.earned_points(resilience.derive_facts(observation)) == 0


def test_green_requires_all_explicit_receipts_and_atomic_facts():
    resilience = _load("test_resilience.py")
    observation = {"fault_receipts": [
        {"point": "after-commit-before-ack", "acknowledged": True, "measured_sequence": 1,
         "recovered": True, "effect_count": 1},
        {"point": "after-publish-before-sent", "acknowledged": True, "measured_sequence": 2,
         "recovered": True, "published_count": 1},
        {"point": "topic-replay", "acknowledged": True, "measured_sequence": 3,
         "replayed": True, "audit_count": 4, "unique_event_count": 4},
        {"point": "temporary-outage", "acknowledged": True, "measured_sequence": 4,
         "recovered": True, "partial_state": False},
    ]}
    assert resilience.earned_points(resilience.derive_facts(observation)) == 600


def test_hardcoded_control_fails_every_resilience_check():
    control = _load("test_resilience.py").hardcoded_happy_path_control()
    assert control["points"] == 0
    assert control["expected_failed_ids"] == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]
