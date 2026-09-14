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


def execute_live(invalid_schema_producer, document_sql, workflow_sql, audit_sql):
    """Run C02/C03 through judge-owned boundaries and retain atomic facts."""
    before = workflow_sql.query("select route_id,state from route")
    produced = invalid_schema_producer(CHECKS[0]["variants"][0]["operation"])
    after = workflow_sql.query("select route_id,state from route")
    documents = document_sql.query("select document_id from document")
    routes = workflow_sql.query("select route_id,document_id,version_id,state from route")
    audits = audit_sql.query("select document_id,sequence,kind from audit_event order by recorded_at")
    facts = {
        "C02.dlq": produced.get("dlq_observed") is True,
        "C02.no-transition": before == after,
        "C03.baseline-shape": all(key in produced.get("baseline_fields", {}) for key in
                                  CHECKS[1]["variants"][0]["expected_fields"]),
    }
    return {"facts": facts, "points": earned_points(facts), "producer": produced,
            "observations": {"documents": documents, "routes": routes, "audit": audits}}


def hardcoded_happy_path_control():
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    facts["C03.baseline-shape"] = True
    return {"facts": facts, "points": earned_points(facts),
            "expected_failed_ids": ["SYS.C02"]}
