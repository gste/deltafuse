"""J03 public baseline end-to-end suite.

Runs the real baseline flow against the pinned compose stack: create,
immutable version, submit, single-step approve or reject, canonical
observation, audit/Kafka observability, idempotent replay guard and the
immutable-version guard. Every assertion is named (J03-PUB-nnn) and every
failure is a specific assertion result, never a bare timeout.

Usage:
  python baseline_suite.py --document-url http://127.0.0.1:18081 \
      --workflow-url http://127.0.0.1:18082 --private-network <run-network> \
      [--kafka-timeout-ms 8000] [--deadline 60]

Exit codes: 0 pass, 1 valid failure, 2 invocation error, 3 infrastructure.
"""

import argparse
import json
import sys

import clients


APPROVE_DOC = {
    "document_id": "pub-doc-approve",
    "version_id": "pub-ver-approve-1",
    "title": "Public approve scenario",
    "content": "approve scenario body",
}
REJECT_DOC = {
    "document_id": "pub-doc-reject",
    "version_id": "pub-ver-reject-1",
    "title": "Public reject scenario",
    "content": "reject scenario body",
}


def assert_named(condition, assertion_id, detail):
    if not condition:
        raise clients.PublicFailure(assertion_id, detail)


def post(url, path, body):
    return clients.request_json(url, "POST", path, body)


def counter(operation, sequence):
    return "%s-op-%d" % (operation, sequence)


def event_id(operation, sequence):
    return "%s-evt-%d" % (operation, sequence)


def create_document(url, doc, operation, sequence):
    status, body = post(url, "/api/documents", {
        "operation_id": counter(operation, sequence),
        "event_id": event_id(operation, sequence),
        "document_id": doc["document_id"],
        "title": doc["title"],
    })
    assert_named(status == 200 and body.get("document_id") == doc["document_id"],
                 "J03-PUB-001",
                 "create document returned %s: %s" % (status, body))


def create_version(url, doc, operation, sequence):
    status, body = post(url, "/api/documents/%s/versions" % doc["document_id"], {
        "operation_id": counter(operation, sequence),
        "event_id": event_id(operation, sequence),
        "version_id": doc["version_id"],
        "content": doc["content"],
    })
    assert_named(status == 200 and body.get("version_id") == doc["version_id"],
                 "J03-PUB-002", "create version returned %s: %s" % (status, body))


def submit_version(url, doc, operation, sequence):
    status, body = post(url, "/api/documents/%s/versions/%s/submit"
                        % (doc["document_id"], doc["version_id"]), {
        "operation_id": counter(operation, sequence),
        "event_id": event_id(operation, sequence),
        "document_id": doc["document_id"],
        "version_id": doc["version_id"],
    })
    assert_named(status == 200, "J03-PUB-003",
                 "submit returned %s: %s" % (status, body))


def await_route(url, doc, deadline):
    observation = clients.wait_for_flow(
        url, doc["document_id"],
        lambda flow: flow["workflow"] is not None,
        deadline, "J03-PUB-004")
    route = observation["workflow"]
    assert_named(route["state"] == "PENDING", "J03-PUB-004",
                 "route did not open pending: %s" % route)
    slots = observation["open_slots"]
    assert_named(len(slots) == 1 and slots[0]["role"] == "approver",
                 "J03-PUB-004",
                 "open slots are not the single approver slot: %s" % slots)
    return route["route_id"], slots[0]["assigned_actor_id"]


def decide(url, doc, route_id, actor_id, operation, sequence, action, decision_id):
    status, body = post(url, "/api/workflows/%s/decisions" % route_id, {
        "operation_id": counter(operation, sequence),
        "event_id": event_id(operation, sequence),
        "route_id": route_id,
        "document_id": doc["document_id"],
        "version_id": doc["version_id"],
        "decision_id": decision_id,
        "actor_id": actor_id,
        "role": "approver",
        "action": action,
    })
    return status, body


def approve_scenario(url, workflow_url, deadline):
    create_document(url, APPROVE_DOC, "pub-a", 1)
    create_version(url, APPROVE_DOC, "pub-a", 2)
    submit_version(url, APPROVE_DOC, "pub-a", 3)
    route_id, actor_id = await_route(url, APPROVE_DOC, deadline)
    status, body = decide(workflow_url, APPROVE_DOC, route_id, actor_id,
                          "pub-a", 4, "APPROVE", "pub-dec-approve-1")
    assert_named(status == 200 and body.get("state") == "APPROVED",
                 "J03-PUB-005", "approve decision returned %s: %s" % (status, body))
    observation = clients.wait_for_flow(
        url, APPROVE_DOC["document_id"],
        lambda flow: flow["workflow"] is not None
        and flow["workflow"]["state"] == "APPROVED",
        deadline, "J03-PUB-006")
    assert_named(observation["open_slots"] == [], "J03-PUB-006",
                 "slots did not close after approval: %s" % observation["open_slots"])
    assert_named(observation["audit_sequence"], "J03-PUB-006",
                 "audit sequence stayed empty after approval")
    return route_id, actor_id


def reject_scenario(url, workflow_url, deadline):
    create_document(url, REJECT_DOC, "pub-r", 1)
    create_version(url, REJECT_DOC, "pub-r", 2)
    submit_version(url, REJECT_DOC, "pub-r", 3)
    route_id, actor_id = await_route(url, REJECT_DOC, deadline)
    status, body = decide(workflow_url, REJECT_DOC, route_id, actor_id,
                          "pub-r", 4, "REJECT", "pub-dec-reject-1")
    assert_named(status == 200 and body.get("state") == "REJECTED",
                 "J03-PUB-007", "reject decision returned %s: %s" % (status, body))
    clients.wait_for_flow(
        url, REJECT_DOC["document_id"],
        lambda flow: flow["workflow"] is not None
        and flow["workflow"]["state"] == "REJECTED",
        deadline, "J03-PUB-008")


def immutable_version_guard(url):
    status, body = post(url, "/api/documents/%s/versions/%s/submit"
                        % (REJECT_DOC["document_id"], REJECT_DOC["version_id"]), {
        "operation_id": "pub-r-op-9",
        "event_id": "pub-r-evt-9",
        "document_id": REJECT_DOC["document_id"],
        "version_id": REJECT_DOC["version_id"],
    })
    assert_named(status == 409 and body.get("code") == "VERSION_IMMUTABLE",
                 "J03-PUB-009",
                 "resubmitting a decided version returned %s: %s" % (status, body))


def assert_audit_unchanged(before_sequence, after_sequence):
    """Named replay guard: a replayed decision must not add audit effects."""
    if before_sequence != after_sequence:
        raise clients.PublicFailure(
            "J03-PUB-010",
            "replay changed the audit sequence: %s -> %s"
            % (json.dumps(before_sequence, sort_keys=True),
               json.dumps(after_sequence, sort_keys=True)))


def replay_guard(url, workflow_url, route_id, actor_id):
    replay_body = {
        "operation_id": "pub-a-op-10",
        "event_id": "pub-a-evt-10",
        "route_id": route_id,
        "document_id": APPROVE_DOC["document_id"],
        "version_id": APPROVE_DOC["version_id"],
        "decision_id": "pub-dec-approve-1",
        "actor_id": actor_id,
        "role": "approver",
        "action": "APPROVE",
    }
    before = clients.get_flow(url, APPROVE_DOC["document_id"])
    status, body = post(workflow_url, "/api/workflows/%s/decisions" % route_id,
                        replay_body)
    assert_named(status == 200 and body.get("decision_id") == "pub-dec-approve-1"
                 and body.get("state") == "APPROVED", "J03-PUB-010",
                 "idempotent replay returned %s: %s" % (status, body))
    after = clients.get_flow(url, APPROVE_DOC["document_id"])
    assert_audit_unchanged(before["audit_sequence"], after["audit_sequence"])
    conflict = dict(replay_body, operation_id="pub-a-op-11",
                    event_id="pub-a-evt-11", action="REJECT")
    status, body = post(workflow_url, "/api/workflows/%s/decisions" % route_id,
                        conflict)
    assert_named(status == 409 and body.get("code") == "IDEMPOTENCY_CONFLICT",
                 "J03-PUB-011",
                 "same decision id with different payload returned %s: %s"
                 % (status, body))


def kafka_observability(private_network, kafka_timeout_ms):
    document_events = clients.kafka_events(
        private_network, "j03.document-events", kafka_timeout_ms)
    workflow_events = clients.kafka_events(
        private_network, "j03.workflow-events", kafka_timeout_ms)
    names = {event.get("schema_name") for event in document_events
             if isinstance(event, dict)}
    needed = {"j03.document.created", "j03.document.version-created",
              "j03.document.version-submitted"}
    assert_named(needed <= names, "J03-PUB-012",
                 "document topic missing baseline events: %s" % sorted(names))
    decisions = [event for event in workflow_events if isinstance(event, dict)
                 and event.get("schema_name") == "j03.workflow.decision-applied"]
    assert_named(decisions, "J03-PUB-012",
                 "no decision events on the workflow topic")
    for decision_id in ("pub-dec-approve-1", "pub-dec-reject-1"):
        count = sum(1 for event in decisions
                    if event.get("payload", {}).get("decision_id") == decision_id)
        assert_named(count == 1, "J03-PUB-010",
                     "decision %s appears %d times on the topic"
                     % (decision_id, count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-url", required=True)
    parser.add_argument("--workflow-url", required=True)
    parser.add_argument("--private-network", required=True)
    parser.add_argument("--kafka-timeout-ms", type=int, default=8000)
    parser.add_argument("--deadline", type=int, default=60)
    arguments = parser.parse_args()
    try:
        approve_route, approve_actor = approve_scenario(
            arguments.document_url, arguments.workflow_url, arguments.deadline)
        reject_scenario(arguments.document_url, arguments.workflow_url,
                        arguments.deadline)
        immutable_version_guard(arguments.document_url)
        replay_guard(arguments.document_url, arguments.workflow_url,
                     approve_route, approve_actor)
        kafka_observability(arguments.private_network,
                            arguments.kafka_timeout_ms)
    except clients.PublicFailure as failure:
        print("PUBLIC FAILURE %s" % failure, file=sys.stderr)
        return clients.EXIT_VALID_FAILURE
    except clients.InfrastructureFailure as failure:
        print("INFRASTRUCTURE FAILURE %s" % failure, file=sys.stderr)
        return clients.EXIT_INFRASTRUCTURE
    print("J03 public baseline suite: all named assertions passed")
    return clients.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
