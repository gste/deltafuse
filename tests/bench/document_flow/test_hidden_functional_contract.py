import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
HIDDEN = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(name):
    spec = importlib.util.spec_from_file_location("j03_hidden_" + name, HIDDEN / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_functional_registry_is_complete_and_fixed():
    functional = load("test_functional")
    consistency = load("test_consistency")
    checks = functional.CHECKS + consistency.CHECKS
    assert [check["id"] for check in checks] == [
        "SYS.F01", "SYS.F02", "SYS.F03", "SYS.F04", "SYS.F05",
        "SYS.F06", "SYS.F07", "SYS.F08", "SYS.F09", "SYS.C02", "SYS.C03"]
    assert sum(check["points"] for check in checks) == 1800 + 160
    assert all(check["assertions"] and check["variants"] for check in checks)


def test_every_target_scenario_has_independent_expected_state():
    functional = load("test_functional")
    for check in functional.CHECKS:
        for variant in check["variants"]:
            expected = functional.expected(variant)
            assert expected["documents"]
            assert expected["audit"]
            assert not any(key.startswith("actual") for key in expected)


def test_required_held_out_schedules_are_not_happy_path_aliases():
    functional = load("test_functional")
    schedules = {variant["schedule_id"]: tuple(op["kind"] + ":" + op.get("op", "")
                 for op in variant["operations"])
                 for check in functional.CHECKS for variant in check["variants"]}
    assert len(schedules) >= 13
    assert len(set(schedules.values())) >= 8
    assert any(any(item.startswith("duplicate-delivery:") for item in schedule)
               for schedule in schedules.values())
    assert any(sum(item == "http:submit-version" for item in schedule) == 2
               for schedule in schedules.values())


def test_points_are_derived_from_named_subcase_facts():
    functional = load("test_functional")
    facts = {assertion: True for check in functional.CHECKS for assertion in check["assertions"]}
    assert functional.earned_points(facts) == 1800
    facts["F06.late-reject-audited"] = False
    assert functional.earned_points(facts) == 1650
    assert functional.earned_points({}) == 0


def test_consistency_contract_requires_observable_invalid_and_baseline_facts():
    consistency = load("test_consistency")
    assert consistency.earned_points({"C02.dlq": True, "C02.no-transition": True,
                                      "C03.baseline-shape": True}) == 160
    assert consistency.earned_points({"C02.dlq": True, "C03.baseline-shape": True}) == 80


def test_hidden_suite_is_not_in_public_seed_inventory():
    public = ROOT / "process/bench/cases/J03-document-flow/seed"
    assert not (public / "hidden_suite").exists()
    for file in HIDDEN.glob("*.py"):
        assert public not in file.parents


def test_hardcoded_happy_path_is_a_real_negative_control():
    functional = load("test_functional")
    consistency = load("test_consistency")
    control = functional.hardcoded_happy_path_control()
    assert control["points"] == 0
    assert control["expected_failed_ids"] == [f"SYS.F0{i}" for i in range(1, 10)]
    assert consistency.hardcoded_happy_path_control()["expected_failed_ids"] == ["SYS.C02"]


def test_live_executors_return_atomic_facts_not_exit_derived_scores():
    functional = load("test_functional")
    consistency = load("test_consistency")
    assert callable(functional.execute_live) and callable(functional.derive_facts)
    assert callable(consistency.execute_live)
    assert "exit_code" not in functional.earned_points.__code__.co_names
    assert "exit_code" not in consistency.earned_points.__code__.co_names


def _live_main():
    from scripts.document_flow.clients import KafkaClient, ReadOnlySqlClient
    from scripts.document_flow.system_runner import subprocess_executor

    functional = load("test_functional")
    consistency = load("test_consistency")
    postgres = os.environ["J03_POSTGRES_CONTAINER"]
    judge = os.environ.get("J03_JUDGE_USER", "j03_judge_readonly")
    document_sql = ReadOnlySqlClient(subprocess_executor, postgres, "j03_document", judge)
    workflow_sql = ReadOnlySqlClient(subprocess_executor, postgres, "j03_workflow", judge)
    audit_sql = ReadOnlySqlClient(subprocess_executor, postgres, "j03_audit", judge)
    live = functional.execute_live(os.environ["J03_DOCUMENT_URL"], os.environ["J03_WORKFLOW_URL"],
                                   document_sql, workflow_sql, audit_sql,
                                   settle_seconds=float(os.environ.get("J03_SETTLE_SECONDS", "0.5")))

    def invalid_schema(operation):
        kafka = KafkaClient(subprocess_executor, os.environ["J03_KAFKA_CONTAINER"])
        invalid = json.dumps({"schema_name": operation["schema_name"],
            "schema_version": operation["schema_version"], "event_id": "c02-invalid-event",
            "producer": "j03-judge", "aggregate_type": "DOCUMENT",
            "aggregate_id": "c02-document", "domain_sequence": 1,
            "correlation_id": "c02-invalid-operation", "causation_id": None,
            "occurred_at": None, "payload": {}}, separators=(",", ":"))
        import hashlib
        raw_hash = hashlib.sha256(invalid.encode()).hexdigest()
        published = kafka.publish("j03.document-events", "c02-document", invalid)
        attempt = kafka.consume("j03.workflow-dlq", max_messages=100)
        return {"publish_argv": list(published.argv), "publish_exit": published.exit_code,
                "attempt_argv": list(attempt.argv), "attempt_exit": attempt.exit_code,
                "attempt_stdout": attempt.stdout, "attempt_stderr": attempt.stderr,
                "dlq_observed": published.exit_code == 0 and attempt.exit_code == 0
                    and raw_hash in attempt.stdout and "INVALID_CONTRACT" in attempt.stdout,
                "invalid_operation": operation,
                "baseline_fields": {"document": True, "active_version": True,
                    "workflow": True, "open_slots": True, "audit_sequence": True}}

    consistent = consistency.execute_live(invalid_schema, document_sql, workflow_sql, audit_sql)
    control_f = functional.hardcoded_happy_path_control()
    control_c = consistency.hardcoded_happy_path_control()
    payload = {"label": os.environ["J03_LIVE_LABEL"], "functional": live,
               "consistency": consistent, "hardcoded_control": {
                   "functional": control_f, "consistency": control_c}}
    target = Path(os.environ["J03_LIVE_OUTPUT"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    failed = [check["id"] for check in functional.CHECKS
              if not all(live["facts"].get(a) is True for a in check["assertions"])]
    failed += [check["id"] for check in consistency.CHECKS
               if not all(consistent["facts"].get(a) is True for a in check["assertions"])]
    print(json.dumps({"label": payload["label"], "functional_points": live["points"],
                      "consistency_points": consistent["points"], "failed_ids": failed,
                      "hardcoded_failed_ids": control_f["expected_failed_ids"] + control_c["expected_failed_ids"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(_live_main())
