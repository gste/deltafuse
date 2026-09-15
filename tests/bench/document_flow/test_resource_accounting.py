"b""Contract tests for bounded load, resource checks (SYS.C04, SYS.E01-SYS.E04) and budget accounting."""

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
HIDDEN = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"
ORACLE = ROOT / "process/bench/cases/J03-document-flow/oracle"
BUDGETS_FILE = ORACLE / "resource-budgets.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_resources():
    spec = importlib.util.spec_from_file_location("j03_resources", HIDDEN / "test_resources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resource_registry_is_fixed_and_complete():
    resources = _load_resources()
    checks = resources.CHECKS
    assert [check["id"] for check in checks] == ["SYS.C04", "SYS.E01", "SYS.E02", "SYS.E03", "SYS.E04"]
    assert sum(check["points"] for check in checks) == 80 + 70 + 50 + 40 + 40
    assert all(check["assertions"] for check in checks)


def test_resource_budgets_file_is_valid_and_frozen():
    assert BUDGETS_FILE.is_file(), "resource-budgets.json must exist"
    data = json.loads(BUDGETS_FILE.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["budget_revision"] == "J03-resource-budgets-1"
    assert "budgets" in data
    budgets = data["resources"] if "resources" in data else data["budgets"]
    assert "max_sql_statements_per_command" in budgets
    assert "max_replayed_messages_on_request" in budgets
    assert "max_completion_seconds_per_operation" in budgets
    assert "max_heap_mb_per_service" in budgets
    assert "max_restarts_allowed" in budgets
    assert budgets["max_restarts_allowed"] == 0


def test_missing_measurements_is_fail_closed():
    resources = _load_resources()
    facts = resources.derive_facts({})
    assert resources.earned_points(facts) == 0
    assert resources.expected_failed_ids(facts) == ["SYS.C04", "SYS.E01", "SYS.E02", "SYS.E03", "SYS.E04"]


def test_green_requires_all_measurements_within_budget_and_consistent_state():
    resources = _load_resources()
    observation = {
        "workload_completed": True,
        "final_state_consistent": True,
        "event_stream_consistent": True,
        "measured_sql_statements_per_command": 4,
        "measured_replayed_messages_on_request": 0,
        "measured_completion_seconds_per_operation": 0.5,
        "measured_heap_mb": {"workflow": 128, "document": 128, "audit": 128},
        "measured_restarts": 0,
        "oom_detected": False,
    }
    facts = resources.derive_facts(observation, budget_path=BUDGETS_FILE)
    assert resources.earned_points(facts) == 280
    assert resources.expected_failed_ids(facts) == []


def test_inflated_or_exceeded_metrics_fail_exact_checks():
    resources = _load_resources()
    base = {
        "workload_completed": True,
        "final_state_consistent": True,
        "event_stream_consistent": True,
        "measured_sql_statements_per_command": 4,
        "measured_replayed_messages_on_request": 0,
        "measured_completion_seconds_per_operation": 0.5,
        "measured_heap_mb": {"workflow": 128, "document": 128, "audit": 128},
        "measured_restarts": 0,
        "oom_detected": False,
    }

    obs = dict(base, final_state_consistent=False)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.C04"]

    obs = dict(base, measured_sql_statements_per_command=500)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.E01"]

    obs = dict(base, measured_replayed_messages_on_request=100)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.E02"]

    obs = dict(base, measured_completion_seconds_per_operation=60.0)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.E03"]

    obs = dict(base, oom_detected=True)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.E04"]

    obs = dict(base, measured_restarts=1)
    assert resources.expected_failed_ids(resources.derive_facts(obs, budget_path=BUDGETS_FILE)) == ["SYS.E04"]


def test_hardcoded_control_fails_every_resource_check():
    resources = _load_resources()
    control = resources.hardcoded_happy_path_control()
    assert control["points"] == 0
    assert control["expected_failed_ids"] == ["SYS.C04", "SYS.E01", "SYS.E02", "SYS.E03", "SYS.E04"]


def test_live_executors_return_atomic_facts_not_exit_derived_scores():
    resources = _load_resources()
    assert callable(resources.execute_live) and callable(resources.derive_facts)
    assert "exit_code" not in resources.earned_points.__code__.co_names
