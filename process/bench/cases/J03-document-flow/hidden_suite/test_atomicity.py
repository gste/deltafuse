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


def expected_failed_ids(facts):
    return [check["id"] for check in CHECKS
            if not all(facts.get(assertion) is True for assertion in check["assertions"])]


def hardcoded_happy_path_control():
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    return {"facts": facts, "points": 0, "expected_failed_ids": [check["id"] for check in CHECKS]}


def execute_live(document_url, document_sql, workflow_sql, audit_sql, denial,
                 *, settle_seconds=1.0):
    """Observe C01 on a live stack: atomic state, delivery receipt, separation.

    ``denial(role, database, sql)`` executes one judge-owned negative write
    probe as a named database role and returns its argv/exit/stderr receipt.
    Points come only from the recorded observations below; nothing is derived
    from process exit codes of the suite itself.
    """
    import time

    document = _http_post(document_url, "/api/documents", {
        "event_id": "c01-create", "operation_id": "c01-create",
        "document_id": "c01-doc", "title": "c01"})
    version = _http_post(document_url, "/api/documents/c01-doc/versions", {
        "event_id": "c01-version", "operation_id": "c01-version",
        "version_id": "c01-v1", "content": "c01"})
    submit = {"event_id": "c01-submit", "operation_id": "c01-submit",
              "document_id": "c01-doc", "version_id": "c01-v1"}
    first = _http_post(document_url, "/api/documents/c01-doc/versions/c01-v1/submit", submit)
    duplicate = _http_post(document_url, "/api/documents/c01-doc/versions/c01-v1/submit", submit)
    deadline = time.monotonic() + 45
    routes = []
    while time.monotonic() < deadline:
        routes = workflow_sql.query(
            "select route_id,document_id,version_id,state from route where document_id='c01-doc'")
        if routes:
            break
        time.sleep(settle_seconds)
    versions = document_sql.query(
        "select document_id,version_id,state from document_version where document_id='c01-doc'")

    def consistent():
        document_ids = {row["event_id"] for row in document_sql.query(
            "select event_id from outbox_event where aggregate_id='c01-doc'")}
        # Workflow route events carry the route UUID as aggregate id; correlate
        # them to the document through the payload member instead.
        workflow_ids = {row["event_id"] for row in workflow_sql.query(
            "select event_id from outbox_event where payload->>'document_id'='c01-doc'")}
        audit_rows = audit_sql.query(
            "select event_id from audit_event where document_id='c01-doc'")
        audit_ids = {row["event_id"] for row in audit_rows}
        expected = document_ids | workflow_ids
        if not expected or audit_ids != expected or len(audit_rows) != len(audit_ids):
            return None
        return {"document_outbox": sorted(document_ids), "workflow_outbox": sorted(workflow_ids),
                "audit": sorted(audit_ids)}
    time.sleep(settle_seconds * 2)
    coherence = None
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        coherence = consistent()
        if coherence:
            break
        time.sleep(settle_seconds)

    delivery_receipt = (first["ok"] and duplicate["ok"]
                        and first["body"] == duplicate["body"]
                        and len(versions) == 1 and versions[0]["state"] == "SUBMITTED"
                        and len(routes) == 1)
    probes = [
        denial("j03_judge_readonly", "j03_document",
               "INSERT INTO document (document_id,title) VALUES ('c01-denial-probe','denial')"),
        denial("j03_workflow_app", "j03_document",
               "INSERT INTO document (document_id,title) VALUES ('c01-denial-probe','denial')"),
        denial("j03_document_app", "j03_workflow",
               "INSERT INTO route (route_id,document_id,version_id,approver_actor_id,state) "
               "VALUES ('c01-denial-route','c01-doc','c01-v1','denial','PENDING')"),
    ]
    cross_service_write_denied = all(
        probe["exit_code"] != 0
        and ("permission denied" in probe["stderr"].lower()
             or "read-only" in probe["stderr"].lower())
        for probe in probes)
    observation = {"inbox_outbox_consistent": coherence is not None,
                   "delivery_receipt": delivery_receipt,
                   "cross_service_write_denied": cross_service_write_denied}
    facts = derive_facts(observation)
    return {"facts": facts, "points": earned_points(facts), "observations": {
        "flow": {"create": document, "version": version, "submit": first,
                 "duplicate_submit": duplicate},
        "routes": routes, "versions": versions, "coherence": coherence,
        "denial_probes": probes}, "observation": observation}


def _http_post(document_url, path, body):
    from urllib.error import HTTPError, URLError
    from scripts.document_flow.clients import HttpClient
    try:
        return {"ok": True, "status": 200,
                "body": HttpClient(document_url).json("POST", path, body)}
    except HTTPError as failure:
        try:
            payload = failure.read().decode("utf-8")
        except Exception:
            payload = ""
        return {"ok": False, "status": failure.code, "body": {"raw": payload}}
    except (URLError, OSError) as failure:
        return {"ok": False, "status": 0, "body": {"code": "CONNECTION_FAILURE",
                                                   "detail": str(failure)}}
