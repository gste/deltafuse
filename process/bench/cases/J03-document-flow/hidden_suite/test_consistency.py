"""Private fixed consistency assertions executed by J03-306B."""

CHECKS = (
    {"id": "SYS.C02", "points": 80,
     "assertions": ("C02.dlq", "C02.no-transition"),
     "variants": ({"schedule_id": "c02-invalid-schema",
                   "operation": {"schema_name": "j03.workflow.unknown", "schema_version": 99}},)},
    {"id": "SYS.C03", "points": 80,
     "assertions": ("C03.baseline-shape",),
     "variants": ({"schedule_id": "c03-single-step-baseline",
                   "expected_fields": ("document", "active_version", "workflow", "open_slots", "audit_sequence")},)},
)


def earned_points(facts):
    return sum(check["points"] for check in CHECKS
               if all(facts.get(assertion) is True for assertion in check["assertions"]))
