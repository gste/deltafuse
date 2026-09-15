"""Private frozen SYS.R01-R04 resilience scenarios and fact scoring."""

CHECKS = (
    {"id": "SYS.R01", "points": 180,
     "assertions": ("R01.commit-survives-ack-loss", "R01.no-duplicate-effect"),
     "fault": {"point": "after-commit-before-ack", "service": "workflow-service"}},
    {"id": "SYS.R02", "points": 160,
     "assertions": ("R02.publish-survives-sent-loss", "R02.no-duplicate-publish"),
     "fault": {"point": "after-publish-before-sent", "service": "document-service"}},
    {"id": "SYS.R03", "points": 160,
     "assertions": ("R03.replay-completes", "R03.audit-deduplicated"),
     "fault": {"point": "topic-replay"}},
    {"id": "SYS.R04", "points": 100,
     "assertions": ("R04.outage-recovered", "R04.no-partial-state"),
     "fault": {"point": "temporary-outage", "services": ("postgres", "kafka")}},
)


def earned_points(facts):
    return sum(check["points"] for check in CHECKS
               if all(facts.get(assertion) is True for assertion in check["assertions"]))


def expected_failed_ids(facts):
    return [check["id"] for check in CHECKS
            if not all(facts.get(assertion) is True for assertion in check["assertions"])]


def derive_facts(observation):
    """Derive only from explicit fault receipts and before/after observations."""
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    for receipt in observation.get("fault_receipts", ()):
        if receipt.get("acknowledged") is not True or receipt.get("measured_sequence", -1) < 0:
            continue
        point = receipt.get("point")
        if point == "after-commit-before-ack":
            facts["R01.commit-survives-ack-loss"] = receipt.get("recovered") is True
            facts["R01.no-duplicate-effect"] = receipt.get("effect_count") == 1
        elif point == "after-publish-before-sent":
            facts["R02.publish-survives-sent-loss"] = receipt.get("recovered") is True
            facts["R02.no-duplicate-publish"] = receipt.get("published_count") == 1
        elif point == "topic-replay":
            facts["R03.replay-completes"] = receipt.get("replayed") is True
            facts["R03.audit-deduplicated"] = receipt.get("audit_count") == receipt.get("unique_event_count")
        elif point == "temporary-outage":
            facts["R04.outage-recovered"] = receipt.get("recovered") is True
            facts["R04.no-partial-state"] = receipt.get("partial_state") is False
    return facts


def hardcoded_happy_path_control():
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    return {"facts": facts, "points": 0, "expected_failed_ids": [check["id"] for check in CHECKS]}
