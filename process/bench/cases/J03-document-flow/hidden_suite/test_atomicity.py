"""Private SYS.C01 atomicity and separation facts."""

CHECKS = ({"id": "SYS.C01", "points": 160,
           "assertions": ("C01.atomic-state", "C01.delivery-receipt",
                           "C01.database-separated")},)


def earned_points(facts):
    return sum(check["points"] for check in CHECKS
               if all(facts.get(assertion) is True for assertion in check["assertions"]))


def derive_facts(observation):
    return {
        "C01.atomic-state": observation.get("inbox_outbox_consistent") is True,
        "C01.delivery-receipt": observation.get("delivery_receipt") is True,
        "C01.database-separated": observation.get("cross_service_write_denied") is True,
    }


def hardcoded_happy_path_control():
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    return {"facts": facts, "points": 0, "expected_failed_ids": ["SYS.C01"]}
