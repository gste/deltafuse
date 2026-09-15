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


# ---------------------------------------------------------------------------
# Run-scoped fault arming for the operator-materialized reference stack.
#
# The seed exposes the J03-206 DeliveryBarrier seams but wires DeliveryHook.NONE
# in production, so a live barrier cannot be measured externally.  The fault
# harness therefore arms the named seams only inside its own run tree: a
# dedicated hook class plus three bean-wiring substitutions.  Arming is inert
# unless J03_FAULT_BARRIER names the exact barrier, and it never touches the
# committed seed or the committed reference patches.
# ---------------------------------------------------------------------------

HOOK_RELATIVE = "shared-contracts/src/main/java/dev/deltafuse/bench/messaging/J03FaultArm.java"

HOOK_SOURCE = """package dev.deltafuse.bench.messaging;

/** Judge fault-harness arming for named DeliveryBarrier points; inert unless J03_FAULT_BARRIER matches. */
public final class J03FaultArm implements DeliveryHook {
    private final String service;

    private J03FaultArm(String service) {
        this.service = service;
    }

    public static DeliveryHook hook(String service) {
        return new J03FaultArm(service);
    }

    @Override
    public void reached(DeliveryBarrier barrier) {
        String armed = System.getenv("J03_FAULT_BARRIER");
        if (armed == null || !armed.equals(barrier.name())) {
            return;
        }
        System.err.println("J03_FAULT_BARRIER_REACHED " + service + " " + barrier.name());
        System.err.flush();
        Runtime.getRuntime().halt(97);
    }
}
"""

BARRIER_ENV = "J03_FAULT_BARRIER"
HALT_EXIT_CODE = 97
BARRIER_MARKER = "J03_FAULT_BARRIER_REACHED"

ARMING_TARGETS = (
    {"path": "workflow-service/src/main/java/dev/deltafuse/bench/workflow/messaging/"
             "WorkflowMessagingConfiguration.java",
     "original": "new WorkflowEventConsumer(commands,workflowKafkaProducer,dlq,Duration.ofSeconds(15))",
     "replacement": 'new WorkflowEventConsumer(commands,workflowKafkaProducer,dlq,Duration.ofSeconds(15),'
                    'dev.deltafuse.bench.messaging.J03FaultArm.hook("workflow-service"))'},
    {"path": "workflow-service/src/main/java/dev/deltafuse/bench/workflow/messaging/"
             "WorkflowMessagingConfiguration.java",
     "original": "new OutboxPublisher(data,workflowKafkaProducer,topic,100,Duration.ofSeconds(15))",
     "replacement": 'new OutboxPublisher(data,workflowKafkaProducer,topic,100,Duration.ofSeconds(15),'
                    'dev.deltafuse.bench.messaging.J03FaultArm.hook("workflow-service"))'},
    {"path": "document-service/src/main/java/dev/deltafuse/bench/document/messaging/"
             "DocumentMessagingConfiguration.java",
     "original": "new OutboxPublisher(data,documentKafkaProducer,topic,100,Duration.ofSeconds(15))",
     "replacement": 'new OutboxPublisher(data,documentKafkaProducer,topic,100,Duration.ofSeconds(15),'
                    'dev.deltafuse.bench.messaging.J03FaultArm.hook("document-service"))'},
)

COMPOSE_ARM = """services:
  workflow-service:
    environment:
      J03_FAULT_BARRIER: ""
  document-service:
    environment:
      J03_FAULT_BARRIER: ""
"""


def arm_run_stack(run_tree):
    """Apply fault arming to an operator-materialized run tree, fail-closed."""
    import hashlib
    from pathlib import Path

    run_tree = Path(run_tree)
    applied = []
    if (run_tree / HOOK_RELATIVE).is_file():
        raise RuntimeError("fault arming appears already applied: " + HOOK_RELATIVE)
    for target in ARMING_TARGETS:
        source = run_tree / target["path"]
        text = source.read_text(encoding="utf-8")
        if text.count(target["original"]) != 1:
            raise RuntimeError("arming target not found exactly once in " + target["path"])
    hook = run_tree / HOOK_RELATIVE
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK_SOURCE, encoding="utf-8")
    applied.append({"path": HOOK_RELATIVE,
                    "sha256": hashlib.sha256(HOOK_SOURCE.encode("utf-8")).hexdigest()})
    for target in ARMING_TARGETS:
        source = run_tree / target["path"]
        text = source.read_text(encoding="utf-8")
        source.write_text(text.replace(target["original"], target["replacement"], 1),
                          encoding="utf-8")
        applied.append({"path": target["path"],
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    compose_arm = run_tree / "compose-arm.yaml"
    compose_arm.write_text(COMPOSE_ARM, encoding="utf-8")
    applied.append({"path": "compose-arm.yaml",
                    "sha256": hashlib.sha256(compose_arm.read_bytes()).hexdigest()})
    return {"armed": True, "barrier_env": BARRIER_ENV, "files": applied}


class BarrierTimeout(RuntimeError):
    """Harness deadline expiry; never converts into a product fact."""


def execute_live(context):
    """Run SYS.R01-R04 against a live armed stack and derive receipt-bound facts.

    The context is prepared by the external judge driver: executor, run and
    compose identities, container names, read-only SQL clients, Kafka client,
    loopback URLs and settle timing.  Points come only from recorded fault
    receipts; harness deadlines raise and classify as infrastructure errors.
    """
    receipts, observations = [], {}
    for scenario, label in ((_r01_consumer_restart, "r01"),
                            (_r02_publisher_restart, "r02"),
                            (_r03_topic_replay, "r03"),
                            (_r04_outage_recovery, "r04")):
        receipt, observation = scenario(context)
        receipts.append(receipt)
        observations[label] = observation
    observation = {"fault_receipts": receipts}
    facts = derive_facts(observation)
    return {"facts": facts, "points": earned_points(facts),
            "receipts": receipts, "observations": observations}


def _r01_consumer_restart(ctx):
    """Kill the workflow consumer between database commit and Kafka ack."""
    _arm(ctx, "workflow-service", "AFTER_COMMIT_BEFORE_ACK")
    flow = _submit_flow(ctx, "r01")
    _await_barrier_halt(ctx, "workflow")
    marker = ctx["logs"]("workflow")
    state = ctx["container_state"]("workflow")
    route_before = ctx["workflow_sql"].query(
        "select route_id,document_id,state from route where document_id='r01-doc'")
    _disarm_and_restart(ctx, "workflow-service", "workflow")
    _await(ctx, "workflow redelivery", 60,
           lambda: ctx["workflow_sql"].query(
               "select route_id,state from route where document_id='r01-doc'"))
    routes = ctx["workflow_sql"].query(
        "select route_id,document_id,version_id,state from route where document_id='r01-doc'")
    audit = _await(ctx, "r01 audit projection", 30,
                   lambda: ctx["audit_sql"].query(
                       "select event_id,kind from audit_event where document_id='r01-doc'") or None)
    healthy = ctx["await_healthy"]("workflow", 90)
    document_rows = ctx["document_sql"].query(
        "select document_id,title from document where document_id='r01-doc'")
    receipt = {"point": "after-commit-before-ack",
               "acknowledged": BARRIER_MARKER in marker and state["exit_code"] == HALT_EXIT_CODE
                   and bool(route_before),
               "measured_sequence": len(audit),
               "recovered": healthy is True and bool(routes)
                   and routes[0]["state"] == "PENDING" and bool(audit) and bool(document_rows),
               "effect_count": len(routes)}
    observation = {"flow": flow, "halt_state": state, "marker": marker,
                   "route_rows_before_recovery": route_before, "routes": routes,
                   "audit": audit, "document_rows": document_rows}
    return receipt, observation


def _r02_publisher_restart(ctx):
    """Kill the document outbox publisher between broker publish and sent marking."""
    _arm(ctx, "document-service", "AFTER_PUBLISH_BEFORE_SENT")
    flow = _create_document(ctx, "r02")
    _await_barrier_halt(ctx, "document")
    marker = ctx["logs"]("document")
    state = ctx["container_state"]("document")
    outbox = ctx["document_sql"].query(
        "select event_id,aggregate_id,domain_sequence,schema_name from outbox_event "
        "where aggregate_id='r02-doc'")
    event_id = outbox[0]["event_id"] if outbox else ""
    before = _count_topic_occurrences(ctx, event_id)
    _disarm_and_restart(ctx, "document-service", "document")
    def republished():
        counts = _count_topic_occurrences(ctx, event_id)
        return counts if counts.get("occurrences", 0) > before.get("occurrences", 0) else None
    after = _await(ctx, "r02 outbox republication", 60, republished)
    audit = _await(ctx, "r02 audit projection", 30,
                   lambda: ctx["audit_sql"].query(
                       "select event_id,kind from audit_event where document_id='r02-doc'") or None)
    healthy = ctx["await_healthy"]("document", 90)
    distinct = {row["event_id"] for row in ctx["document_sql"].query(
        "select event_id from outbox_event where aggregate_id='r02-doc'")}
    receipt = {"point": "after-publish-before-sent",
               "acknowledged": BARRIER_MARKER in marker and state["exit_code"] == HALT_EXIT_CODE
                   and bool(outbox) and before.get("occurrences", 0) >= 1,
               "measured_sequence": len(outbox),
               "recovered": healthy is True and bool(audit)
                   and after.get("occurrences", 0) > before.get("occurrences", 0),
               "published_count": len(distinct)}
    observation = {"flow": flow, "halt_state": state, "marker": marker, "outbox": outbox,
                   "topic_before": before, "topic_after": after, "audit": audit,
                   "distinct_published_events": sorted(distinct)}
    return receipt, observation


def _r03_topic_replay(ctx):
    """Replay both domain topics and measure audit deduplication."""
    def audit_counts():
        rows = ctx["audit_sql"].query(
            "select count(*) as total,count(distinct event_id) as unique_events from audit_event")
        return rows[0] if rows else None
    before = _await(ctx, "audit quiescence before replay", 30,
                    lambda: _stable_audit(ctx, audit_counts))
    before_routes = ctx["workflow_sql"].query("select count(*) as routes from route")[0]["routes"]
    replayed, records_observed = [], 0
    for topic in ("j03.document-events", "j03.workflow-events"):
        consumed = ctx["kafka"].consume(topic, max_messages=1000)
        records = _topic_records(consumed.stdout)
        records_observed += len(records)
        for record in records:
            aggregate_id = _record_aggregate(record)
            published = ctx["kafka"].publish(topic, aggregate_id, record)
            replayed.append({"topic": topic, "aggregate_id": aggregate_id,
                             "publish_exit": published.exit_code,
                             "publish_argv": list(published.argv)})
    def settled():
        counts = audit_counts()
        if counts and counts["total"] == before["total"] and counts["unique_events"] == before["unique_events"]:
            return counts
        return None
    after = _await(ctx, "audit deduplication after replay", 60, settled)
    after_routes = ctx["workflow_sql"].query("select count(*) as routes from route")[0]["routes"]
    publish_exits_ok = all(item["publish_exit"] == 0 for item in replayed)
    counts_complete = bool(after) and after["total"] == before["total"] \
        and after["unique_events"] == before["unique_events"]
    receipt = {"point": "topic-replay",
               "acknowledged": publish_exits_ok and counts_complete
                   and len(replayed) == records_observed,
               "measured_sequence": len(replayed),
               "replayed": publish_exits_ok and counts_complete
                   and len(replayed) == records_observed,
               "audit_count": after["total"] if after else -1,
               "unique_event_count": after["unique_events"] if after else -2}
    observation = {"audit_before": before, "audit_after": after,
                   "routes_before": before_routes, "routes_after": after_routes,
                   "replayed_records": replayed}
    return receipt, observation


def _r04_outage_recovery(ctx):
    """Temporary PostgreSQL then Kafka outage with bounded recovery."""
    flow = _submit_flow(ctx, "r04")
    stop_kafka = ctx["fault"]("kafka", "stop")
    committed = _submit_flow(ctx, "r04b", settle=0.0)
    stop_postgres = ctx["fault"]("postgres", "stop")
    rejected = _create_document(ctx, "r04rejected", expect_failure=True)
    recover_postgres = ctx["fault"]("postgres", "recover")
    recover_kafka = ctx["fault"]("kafka", "recover")
    # The route for the document committed during the Kafka outage is the
    # actual recovery proof; r04 itself flowed before the outage began.
    _await(ctx, "r04b route creation after recovery", 90,
           lambda: ctx["workflow_sql"].query(
               "select route_id,state from route where document_id='r04b-doc'") or None)
    audit = _await(ctx, "r04 audit projection", 60,
                   lambda: ctx["audit_sql"].query(
                       "select event_id,kind from audit_event where document_id='r04-doc'") or None)
    # The outage probe's outcome may resolve after postgres returns (client
    # timeout is not a server failure); either way the command must be atomic:
    # every committed r04* command carries its own outbox event, and every
    # such event reaches audit after recovery.
    def coherent():
        rows = ctx["document_sql"].query(
            "select event_id,aggregate_id,schema_name from outbox_event where aggregate_id like 'r04%'")
        if not rows:
            return None
        audited = {row["event_id"] for row in ctx["audit_sql"].query(
            "select event_id from audit_event where document_id like 'r04%'")}
        if not all(row["event_id"] in audited for row in rows):
            return None
        return {"outbox": rows, "audited": sorted(audited)}
    coherence = _await(ctx, "r04 outbox/audit coherence", 120, coherent)
    outbox = coherence["outbox"]
    probe_rows = ctx["document_sql"].query(
        "select document_id,title from document where document_id='r04rejected-doc'")
    healthy = all(ctx["await_healthy"](name, 120)
                  for name in ("postgres", "kafka", "document", "workflow", "audit"))
    delivered = bool(outbox)
    probe_atomic = (not probe_rows) or any(row["aggregate_id"] == "r04rejected-doc"
                                           for row in outbox)
    partial_state = not (delivered and probe_atomic)
    receipt = {"point": "temporary-outage",
               "acknowledged": all(result["exit"] == 0
                                   for result in (stop_kafka, stop_postgres,
                                                  recover_postgres, recover_kafka)),
               "measured_sequence": len(audit),
               "recovered": healthy and bool(audit) and delivered,
               "partial_state": partial_state}
    observation = {"flow": flow, "committed_during_kafka_outage": committed,
                   "probe_during_postgres_outage": rejected,
                   "stop_recover": {"stop_kafka": stop_kafka, "stop_postgres": stop_postgres,
                                    "recover_postgres": recover_postgres,
                                    "recover_kafka": recover_kafka},
                   "probe_rows": probe_rows, "outbox": outbox,
                   "audit": audit, "stack_healthy": healthy}
    return receipt, observation


# ---------------------------------------------------------------------------
# Live primitives; the driver binds these to run-owned resources.
# ---------------------------------------------------------------------------

def _submit_flow(ctx, name, settle=None):
    from scripts.document_flow.clients import ClientError
    settle = ctx["settle_seconds"] if settle is None else settle
    version_id = name + "-v1"
    calls = []
    calls.append(_http(ctx, "POST", "/api/documents", {
        "event_id": name + "-create", "operation_id": name + "-create",
        "document_id": name + "-doc", "title": name}))
    calls.append(_http(ctx, "POST", "/api/documents/" + name + "-doc/versions", {
        "event_id": name + "-version", "operation_id": name + "-version",
        "version_id": version_id, "content": name}))
    calls.append(_http(ctx, "POST",
        "/api/documents/" + name + "-doc/versions/" + version_id + "/submit", {
            "event_id": name + "-submit", "operation_id": name + "-submit",
            "document_id": name + "-doc", "version_id": version_id}))
    ctx["sleep"](settle * 2)
    return {"calls": calls,
            "errors": [call.get("body", {}).get("code")
                       for call in calls if not call["ok"]]}


def _create_document(ctx, name, expect_failure=False):
    result = _http(ctx, "POST", "/api/documents", {
        "event_id": name + "-create", "operation_id": name + "-create",
        "document_id": name + "-doc", "title": name})
    return {"calls": [result],
            "expected_failure_observed": expect_failure and not result["ok"]}


def _http(ctx, method, path, body):
    from urllib.error import HTTPError, URLError
    from scripts.document_flow.clients import ClientError, HttpClient
    client = ctx["http"](ctx["document_url"])
    try:
        return {"ok": True, "status": 200, "body": client.json(method, path, body)}
    except HTTPError as failure:
        try:
            payload = failure.read().decode("utf-8")
        except Exception:
            payload = ""
        return {"ok": False, "status": failure.code, "body": {"raw": payload}}
    except (URLError, OSError, ClientError) as failure:
        return {"ok": False, "status": 0, "body": {"code": "CONNECTION_FAILURE",
                                                   "detail": str(failure)}}


def _arm(ctx, service, barrier):
    ctx["arm"](service, barrier)


def _disarm_and_restart(ctx, service, container):
    ctx["arm"](service, "")
    if not ctx["await_healthy"](container, 120):
        raise BarrierTimeout("service did not return healthy: " + service)


def _await_barrier_halt(ctx, container):
    def halted():
        state = ctx["container_state"](container)
        return state if state.get("status") == "exited" else None
    state = _await(ctx, "barrier halt of " + container, 60, halted)
    if state.get("exit_code") != HALT_EXIT_CODE:
        raise BarrierTimeout("container halted with unexpected exit: " + str(state))


def _count_topic_occurrences(ctx, event_id):
    if not event_id:
        return {"occurrences": 0, "event_id": event_id}
    consumed = ctx["kafka"].consume("j03.document-events", max_messages=1000)
    records = _topic_records(consumed.stdout)
    occurrences = sum(1 for record in records if '"event_id":"' + event_id + '"' in record)
    return {"occurrences": occurrences, "event_id": event_id, "records": len(records),
            "consume_argv": list(consumed.argv), "consume_exit": consumed.exit_code}


def _topic_records(stdout):
    """Extract envelope records from probe stdout.

    The container classpath binds slf4j to logback, so the probe's stdout
    mixes kafka client INFO logs with the printed record values.  A record is
    a line that parses as a JSON object carrying an event_id; everything else
    is client logging and is never replayed or counted.
    """
    import json
    records = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "event_id" in parsed:
            records.append(line)
    return records


def _record_aggregate(record):
    import json
    try:
        return json.loads(record).get("aggregate_id", "")
    except ValueError:
        return ""


def _stable_audit(ctx, counts):
    first = counts()
    if not first or not first["total"]:
        return None
    ctx["sleep"](ctx["settle_seconds"])
    second = counts()
    return second if second == first else None


def _await(ctx, description, timeout_seconds, probe):
    """Bounded deadline polling; expiry is a harness error, never a fact."""
    deadline = ctx["monotonic"]() + timeout_seconds
    last = None
    while ctx["monotonic"]() < deadline:
        last = probe()
        if last is not None:
            return last
        ctx["sleep"](0.5)
    raise BarrierTimeout("deadline exceeded while waiting for " + description
                         + "; last observation: " + repr(last)[:400])
