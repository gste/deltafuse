import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[3]
HIDDEN = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"


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
