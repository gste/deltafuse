"""Private frozen SYS.F01-F09 scenarios; not imported into the public seed."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import time
from urllib.error import HTTPError

from scripts.document_flow.clients import HttpClient


def _load_interpreter():
    path = Path(__file__).parents[1] / "oracle/interpreter.py"
    spec = spec_from_file_location("j03_hidden_interpreter", path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _base(name, version="v1"):
    doc = name + "-doc"
    return [
        {"kind": "http", "op": "create-document", "document_id": doc, "title": name},
        {"kind": "http", "op": "create-version", "document_id": doc, "version_id": version, "content": name},
        {"kind": "http", "op": "submit-version", "document_id": doc, "version_id": version,
         "route_id": name + "-" + version + "-route"},
    ]


def _decision(name, decision, actor, role, action, version="v1"):
    return {"kind": "decision", "op": "decision", "document_id": name + "-doc",
            "version_id": version, "route_id": name + "-" + version + "-route",
            "decision_id": decision, "actor_id": actor, "role": role, "action": action}


def _normal(name, order=("legal", "security")):
    operations = _base(name)
    for index, role in enumerate(order):
        operations.append(_decision(name, "expert-" + role, "actor-" + str(index), role, "APPROVE"))
    operations.append(_decision(name, "registrar", "registrar-actor", "registrar", "APPROVE"))
    return operations


def _variant(schedule_id, operations):
    return {"schedule_id": schedule_id, "operations": operations}


def _supersede(name, partial=False, late_action=None):
    operations = _base(name)
    if partial:
        operations.append(_decision(name, "legal-first", "legal-actor", "legal", "APPROVE"))
    operations.extend([
        {"kind": "http", "op": "create-version", "document_id": name + "-doc", "version_id": "v2", "content": "next"},
        {"kind": "http", "op": "submit-version", "document_id": name + "-doc", "version_id": "v2",
         "route_id": name + "-v2-route"},
    ])
    if late_action:
        operations.append(_decision(name, "late-" + late_action.lower(), "late-actor", "security", late_action))
    return operations


CHECKS = (
    {"id": "SYS.F01", "points": 300, "assertions": ("F01.approved", "F01.audit-order"),
     "variants": (_variant("f01-legal-first", _normal("f01a")),
                  _variant("f01-security-first", _normal("f01b", ("security", "legal"))))},
    {"id": "SYS.F02", "points": 150, "assertions": ("F02.legal-rejected",),
     "variants": (_variant("f02-legal-reject", _base("f02") + [_decision("f02", "reject", "a", "legal", "REJECT")]),)},
    {"id": "SYS.F03", "points": 150, "assertions": ("F03.security-rejected",),
     "variants": (_variant("f03-security-reject", _base("f03") + [_decision("f03", "reject", "a", "security", "REJECT")]),)},
    {"id": "SYS.F04", "points": 250, "assertions": ("F04.old-superseded", "F04.successor-pending"),
     "variants": (_variant("f04-before-expert", _supersede("f04")),)},
    {"id": "SYS.F05", "points": 250, "assertions": ("F05.partial-superseded", "F05.no-carryover"),
     "variants": (_variant("f05-after-legal", _supersede("f05", partial=True)),
                  _variant("f05-after-security", _base("f05b") + [_decision("f05b", "security-first", "s", "security", "APPROVE")] + _supersede("f05b")[3:]))},
    {"id": "SYS.F06", "points": 150, "assertions": ("F06.late-approve-audited", "F06.late-reject-audited"),
     "variants": (_variant("f06-late-approve", _supersede("f06a", late_action="APPROVE")),
                  _variant("f06-late-reject", _supersede("f06b", late_action="REJECT")))},
    {"id": "SYS.F07", "points": 150, "assertions": ("F07.early-invalid", "F07.pending"),
     "variants": (_variant("f07-early-registrar", _base("f07") + [_decision("f07", "early", "r", "registrar", "APPROVE")]),)},
    {"id": "SYS.F08", "points": 200, "assertions": ("F08.duplicate-no-effect", "F08.identity-bound", "F08.distinct-actors"),
     "variants": (_variant("f08-duplicate", _base("f08a") + [{"kind": "duplicate-delivery", "op": "submit-version"}]),
                  _variant("f08-actor-reuse", _base("f08b") + [_decision("f08b", "legal", "same", "legal", "APPROVE"), _decision("f08b", "security", "same", "security", "APPROVE")]))},
    {"id": "SYS.F09", "points": 200, "assertions": ("F09.independent-documents", "F09.audit-isolated"),
     "variants": (_variant("f09-interleaved-a", _base("f09a")[:2] + _base("f09b")[:2] + _base("f09a")[2:] + _base("f09b")[2:]),
                  _variant("f09-interleaved-b", _base("f09c") + _normal("f09d")))},
)


def expected(variant):
    state = _load_interpreter().reduce(variant["operations"])
    return {
        "documents": {doc: {"active_version": value.active_version,
                              "routes": {version: route.state for (_, version), route in value.routes.items()}}
                      for doc, value in state.documents.items()},
        "audit": {doc: [entry.kind for entry in entries] for doc, entries in state.audit.items()},
    }


def earned_points(facts):
    return sum(check["points"] for check in CHECKS
               if all(facts.get(assertion) is True for assertion in check["assertions"]))


def _request(client, method, path, body):
    try:
        return {"ok": True, "body": client.json(method, path, body)}
    except HTTPError as failure:
        import json
        payload = failure.read().decode("utf-8")
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = {"raw": payload}
        return {"ok": False, "status": failure.code, "body": payload}


def execute_live(document_url, workflow_url, document_sql, workflow_sql, audit_sql,
                 *, settle_seconds=1.0):
    """Execute the frozen schedules via public HTTP and judge read-only SQL.

    This returns assertion facts and complete per-schedule observations.  It
    deliberately does not assert or translate a process exit into points.
    """
    document = HttpClient(document_url)
    workflow = HttpClient(workflow_url)
    observations = {}
    sequence = 0

    def identity(schedule, label):
        nonlocal sequence
        sequence += 1
        return f"{schedule}-{label}-{sequence}"

    def wire_version(operation):
        # The seed schema makes version_id globally unique although the frozen
        # domain schedules intentionally reuse v1/v2 across documents.
        return operation["document_id"] + "-" + operation["version_id"]

    for check in CHECKS:
        for variant in check["variants"]:
            schedule = variant["schedule_id"]
            calls, errors, submitted = [], [], {}
            for operation in variant["operations"]:
                op = operation["op"]
                if operation["kind"] == "duplicate-delivery":
                    path, body = next(reversed(submitted.values()))
                    result = _request(document, "POST", path, body)
                elif op == "create-document":
                    eid = identity(schedule, "create")
                    result = _request(document, "POST", "/api/documents", {
                        "event_id": eid, "operation_id": eid,
                        "document_id": operation["document_id"], "title": operation["title"]})
                elif op == "create-version":
                    eid = identity(schedule, "version")
                    result = _request(document, "POST",
                        f"/api/documents/{operation['document_id']}/versions", {
                            "event_id": eid, "operation_id": eid,
                            "version_id": wire_version(operation), "content": operation["content"]})
                elif op == "submit-version":
                    eid = identity(schedule, "submit")
                    body = {"event_id": eid, "operation_id": eid,
                            "document_id": operation["document_id"],
                            "version_id": wire_version(operation)}
                    path = f"/api/documents/{operation['document_id']}/versions/{wire_version(operation)}/submit"
                    result = _request(document, "POST", path, body)
                    submitted[(operation["document_id"], wire_version(operation))] = (path, body)
                    time.sleep(settle_seconds)
                else:
                    rows = workflow_sql.query(
                        "select route_id from route where document_id='" + operation["document_id"] +
                        "' and version_id='" + wire_version(operation) + "'")
                    if not rows:
                        result = {"ok": False, "body": {"code": "ROUTE_NOT_OBSERVED"}}
                    else:
                        route_id = rows[-1]["route_id"]
                        eid = identity(schedule, "decision")
                        body = {"event_id": eid, "operation_id": eid, "route_id": route_id,
                                "document_id": operation["document_id"], "version_id": wire_version(operation),
                                "decision_id": operation["decision_id"], "actor_id": operation["actor_id"],
                                "role": operation["role"], "action": operation["action"]}
                        result = _request(workflow, "POST", f"/api/workflows/{route_id}/decisions", body)
                calls.append({"operation": operation, "result": result})
                if not result["ok"]:
                    errors.append(result["body"].get("code", "HTTP_" + str(result.get("status", 0))))
                time.sleep(settle_seconds)
            time.sleep(settle_seconds * 2)
            docs = sorted({op.get("document_id") for op in variant["operations"] if op.get("document_id")})
            quoted = ",".join("'" + item + "'" for item in docs)
            routes = workflow_sql.query("select route_id,document_id,version_id,state from route where document_id in (" + quoted + ")")
            decisions = workflow_sql.query("select route_id,decision_id,actor_id,role,action,resulting_state from decision where route_id in (select route_id from route where document_id in (" + quoted + "))")
            audits = audit_sql.query("select event_id,document_id,sequence,kind,aggregate_type,aggregate_id from audit_event where document_id in (" + quoted + ") order by recorded_at")
            versions = document_sql.query("select document_id,version_id,state from document_version where document_id in (" + quoted + ")")
            for row in routes + versions:
                prefix = row["document_id"] + "-"
                if row["version_id"].startswith(prefix):
                    row["version_id"] = row["version_id"][len(prefix):]
            observations[schedule] = {"calls": calls, "errors": errors, "routes": routes,
                                      "decisions": decisions, "audit": audits, "versions": versions,
                                      "expected": expected(variant)}

    facts = derive_facts(observations)
    return {"facts": facts, "points": earned_points(facts), "observations": observations}


def derive_facts(observed):
    route = lambda name, version="v1": next((r for r in observed[name]["routes"] if r["version_id"] == version), {})
    audit_kinds = lambda name: [row["kind"] for row in observed[name]["audit"]]
    facts = {
        "F01.approved": all(route(n).get("state") == "APPROVED" for n in ("f01-legal-first", "f01-security-first")),
        "F01.audit-order": all(audit_kinds(n) == sum(observed[n]["expected"]["audit"].values(), []) for n in ("f01-legal-first", "f01-security-first")),
        "F02.legal-rejected": route("f02-legal-reject").get("state") == "REJECTED",
        "F03.security-rejected": route("f03-security-reject").get("state") == "REJECTED",
        "F04.old-superseded": route("f04-before-expert").get("state") == "SUPERSEDED",
        "F04.successor-pending": route("f04-before-expert", "v2").get("state") == "PENDING",
        "F05.partial-superseded": all(route(n).get("state") == "SUPERSEDED" for n in ("f05-after-legal", "f05-after-security")),
        "F05.no-carryover": all(not [d for d in observed[n]["decisions"] if d["route_id"] == route(n, "v2").get("route_id")] for n in ("f05-after-legal", "f05-after-security")),
        "F06.late-approve-audited": "j03.workflow.decision-ignored" in audit_kinds("f06-late-approve"),
        "F06.late-reject-audited": "j03.workflow.decision-ignored" in audit_kinds("f06-late-reject"),
        "F07.early-invalid": any(call["result"].get("body", {}).get("state") == "EXPERT_REVIEW_INCOMPLETE"
                                 for call in observed["f07-early-registrar"]["calls"]),
        "F07.pending": route("f07-early-registrar").get("state") == "PENDING",
        "F08.duplicate-no-effect": len(observed["f08-duplicate"]["routes"]) == 1,
        "F08.identity-bound": any(call["result"].get("body", {}).get("state") == "ACTOR_ROLE_MISMATCH"
                                  for call in observed["f08-actor-reuse"]["calls"]),
        "F08.distinct-actors": len({d["actor_id"] for d in observed["f08-actor-reuse"]["decisions"]}) == len(observed["f08-actor-reuse"]["decisions"]),
        "F09.independent-documents": all(len({r["document_id"] for r in observed[n]["routes"]}) == 2 for n in ("f09-interleaved-a", "f09-interleaved-b")),
        "F09.audit-isolated": all(all(a["document_id"] in {o.get("document_id") for o in observed[n]["calls"] for o in [o["operation"]] if o.get("document_id")} for a in observed[n]["audit"]) for n in ("f09-interleaved-a", "f09-interleaved-b")),
    }
    return facts


def hardcoded_happy_path_control():
    """Deliberately non-target control; it must not receive functional points."""
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    facts["F01.approved"] = True
    return {"facts": facts, "points": earned_points(facts),
            "expected_failed_ids": [check["id"] for check in CHECKS]}
