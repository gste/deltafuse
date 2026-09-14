"""Hand-worked fixtures for the independent J03 domain interpreter.

Every expectation here is derived by hand from the public contract
(``docs/spec/contracts/``) and the target intake (``input.md`` REQ-*), never
from the Java product code or the variant generator. The interpreter is the
private oracle: it must compute these outcomes itself.
"""

import importlib.util
from pathlib import Path
import sys

import pytest

CASE_ROOT = Path(__file__).parents[3] / (
    "process/bench/cases/J03-document-flow")


def _load_oracle():
    spec = importlib.util.spec_from_file_location(
        "j03_oracle_interpreter", CASE_ROOT / "oracle" / "interpreter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


interpreter = _load_oracle()
InterpreterError = interpreter.InterpreterError
reduce = interpreter.reduce

AUDIT_CREATED = "j03.document.created"
AUDIT_VERSION = "j03.document.version-created"
AUDIT_SUBMITTED = "j03.document.version-submitted"
AUDIT_ROUTE = "j03.workflow.route-created"
AUDIT_SUPERSEDED = "j03.workflow.route-superseded"
AUDIT_DECIDED = "j03.workflow.decision-applied"


def create(document):
    return {"kind": "http", "op": "create-document", "document_id": document,
            "title": "fixture"}


def version(document, version):
    return {"kind": "http", "op": "create-version", "document_id": document,
            "version_id": version, "content": "fixture body"}


def submit(document, version):
    return {"kind": "http", "op": "submit-version", "document_id": document,
            "version_id": version}


def decide(route, document, version, decision_id, actor, role, action,
           event_id=None):
    operation = {"kind": "decision", "op": "decision", "route_id": route,
                 "document_id": document, "version_id": version,
                 "decision_id": decision_id, "actor_id": actor, "role": role,
                 "action": action}
    if event_id:
        operation["event_id"] = event_id
    return operation


def route_created(route, document, version, event_id="evt-route"):
    return {"kind": "delivery", "op": "route-created", "route_id": route,
            "document_id": document, "version_id": version,
            "event_id": event_id}


def route_superseded(route, document, version, event_id="evt-super"):
    return {"kind": "delivery", "op": "route-superseded", "route_id": route,
            "document_id": document, "version_id": version,
            "event_id": event_id}


def baseline(document="d1", version_id="v1", route_id="r1"):
    return [create(document), version(document, version_id),
            submit(document, version_id),
            route_created(route_id, document, version_id)]


def audit_kinds(state, document):
    return [entry.kind for entry in state.audit[document]]


def test_interpreter_is_independent_of_product_and_generator_code():
    interpreter_source = (CASE_ROOT / "oracle" / "interpreter.py").read_text(
        encoding="utf-8")
    for forbidden in ("deltafuse.bench", "variants", "WorkflowCommandService",
                      "jpype", "subprocess"):
        assert forbidden not in interpreter_source, (
            "interpreter must not depend on %s" % forbidden)


def test_normal_approval_reaches_approved_with_ordered_audit():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec2", "a-security", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec3", "a-registrar", "registrar", "APPROVE"),
    ])
    route = state.documents["d1"].routes[("d1", "v1")]
    assert route.state == "APPROVED"
    assert state.audit_kinds("d1") == [
        AUDIT_CREATED, AUDIT_VERSION, AUDIT_SUBMITTED, AUDIT_ROUTE,
        AUDIT_DECIDED, AUDIT_DECIDED, AUDIT_DECIDED]
    assert [entry.sequence for entry in state.audit["d1"]] == [1, 2, 3, 4, 5, 6, 7]
    observation = state.observation("d1")
    assert observation["workflow"] == {"route_id": "r1", "state": "APPROVED"}
    assert observation["open_slots"] == []
    assert observation["active_version"] == {"immutable": True,
                                             "version_id": "v1"}


def test_expert_rejection_closes_the_route_and_rejects_the_rest():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "REJECT"),
        decide("r1", "d1", "v1", "dec2", "a-security", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec3", "a-registrar", "registrar", "APPROVE"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "REJECTED"
    kinds = audit_kinds(state, "d1")
    assert kinds.count(AUDIT_DECIDED) == 1
    assert kinds.count("IDENTITY_MISMATCH") == 2  # closed route: no transition


def test_early_registrar_is_invalid_then_route_completes():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec-early", "a-registrar", "registrar",
               "APPROVE"),
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec2", "a-security", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec3", "a-registrar", "registrar", "APPROVE"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "APPROVED"
    kinds = audit_kinds(state, "d1")
    assert kinds.count("EXPERT_REVIEW_INCOMPLETE") == 1
    assert kinds.count(AUDIT_DECIDED) == 3


def test_registrar_rejection_is_unsupported_action():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec2", "a-security", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec3", "a-registrar", "registrar", "REJECT"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "PENDING"
    assert audit_kinds(state, "d1").count("UNSUPPORTED_ACTION") == 1


def test_one_actor_cannot_fill_two_expert_roles():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec2", "a-legal", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec3", "a-security", "security", "APPROVE"),
        decide("r1", "d1", "v1", "dec4", "a-registrar", "registrar", "APPROVE"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "APPROVED"
    kinds = audit_kinds(state, "d1")
    assert kinds.count("ACTOR_ROLE_MISMATCH") == 1
    assert kinds.count(AUDIT_DECIDED) == 3


def test_wrong_version_binding_is_identity_mismatch():
    state = reduce(baseline() + [
        version("d1", "v2"),
        decide("r1", "d1", "v2", "dec-wrong", "a-legal", "legal", "APPROVE"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "PENDING"
    assert audit_kinds(state, "d1").count("IDENTITY_MISMATCH") == 1


def test_supersede_closes_old_route_and_late_decisions_are_ignored():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec-partial", "a-legal", "legal", "APPROVE"),
        version("d1", "v2"),
        submit("d1", "v2"),
        route_created("r2", "d1", "v2", "evt-route-2"),
        route_superseded("r1", "d1", "v1", "evt-super-1"),
        decide("r1", "d1", "v1", "dec-late", "a-legal", "legal", "REJECT"),
        decide("r1", "d1", "v1", "dec-late-2", "a-registrar", "registrar",
               "APPROVE"),
        decide("r2", "d1", "v2", "dec-r2-legal", "a-legal", "legal", "APPROVE"),
        decide("r2", "d1", "v2", "dec-r2-sec", "a-security", "security",
               "APPROVE"),
        decide("r2", "d1", "v2", "dec-r2-reg", "a-registrar", "registrar",
               "APPROVE"),
    ])
    documents = state.documents["d1"]
    assert documents.routes[("d1", "v1")].state == "SUPERSEDED"
    assert documents.routes[("d1", "v2")].state == "APPROVED"
    assert documents.active_version == "v2"
    kinds = audit_kinds(state, "d1")
    assert kinds.count("IGNORED_LATE_DECISION") == 2
    assert kinds.count(AUDIT_SUPERSEDED) == 1


def test_duplicate_decision_id_replays_without_a_second_effect():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE",
               event_id="evt-dec-1"),
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
    ])
    kinds = audit_kinds(state, "d1")
    assert kinds.count(AUDIT_DECIDED) == 1


def test_same_decision_id_with_different_payload_conflicts():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "REJECT"),
    ])
    assert state.documents["d1"].routes[("d1", "v1")].state == "PENDING"
    assert audit_kinds(state, "d1").count("IDEMPOTENCY_CONFLICT") == 1


def test_filled_slot_rejects_a_second_decision_for_the_same_role():
    state = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec-other", "a-legal-2", "legal", "APPROVE"),
    ])
    assert audit_kinds(state, "d1").count("IDENTITY_MISMATCH") == 1


def test_interleaved_documents_stay_independent():
    state = reduce([
        create("dA"), create("dB"),
        version("dA", "vA1"), version("dB", "vB1"),
        submit("dA", "vA1"), submit("dB", "vB1"),
        route_created("rA", "dA", "vA1"),
        route_created("rB", "dB", "vB1"),
        decide("rA", "dA", "vA1", "decA", "aA-legal", "legal", "REJECT"),
        decide("rB", "dB", "vB1", "decB1", "aB-legal", "legal", "APPROVE"),
        decide("rB", "dB", "vB1", "decB2", "aB-security", "security", "APPROVE"),
        decide("rB", "dB", "vB1", "decB3", "aB-registrar", "registrar", "APPROVE"),
    ])
    assert state.documents["dA"].routes[("dA", "vA1")].state == "REJECTED"
    assert state.documents["dB"].routes[("dB", "vB1")].state == "APPROVED"
    assert len(state.audit["dA"]) == 5
    assert len(state.audit["dB"]) == 7


def test_duplicate_deliveries_and_crash_markers_change_nothing():
    operations = baseline() + [
        route_created("r1", "d1", "v1", "evt-route"),
        {"kind": "duplicate-delivery", "op": "route-created",
         "route_id": "r1", "document_id": "d1", "version_id": "v1",
         "event_id": "evt-route", "valid": True,
         "label": "duplicate-delivery"},
        {"kind": "crash", "point": "after-commit-before-ack",
         "service": "workflow-service"},
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
    ]
    plain = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE")])
    with_noise = reduce(operations)
    assert with_noise.audit_kinds("d1") == plain.audit_kinds("d1")
    assert (with_noise.documents["d1"].routes[("d1", "v1")].state
            == plain.documents["d1"].routes[("d1", "v1")].state == "PENDING")
    assert (with_noise.documents["d1"].routes[("d1", "v1")].filled
            == plain.documents["d1"].routes[("d1", "v1")].filled
            == {"legal": "a-legal"})


def test_barrier_reduce_matches_the_prefix_of_the_full_reduction():
    operations = baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE"),
        decide("r1", "d1", "v1", "dec2", "a-security", "security", "APPROVE"),
    ]
    full = reduce(operations)
    at_barrier = reduce(operations, stop_before=5)
    assert audit_kinds(at_barrier, "d1") == audit_kinds(full, "d1")[:5]
    assert at_barrier.documents["d1"].routes[("d1", "v1")].state == "PENDING"
    assert at_barrier.consumed == 5


def test_open_slots_follow_the_route_order_and_filling():
    state = reduce(baseline())
    observation = state.observation("d1")
    assert [slot["role"] for slot in observation["open_slots"]] == [
        "legal", "security"]
    partial = reduce(baseline() + [
        decide("r1", "d1", "v1", "dec1", "a-legal", "legal", "APPROVE")])
    partial_slots = partial.observation("d1")["open_slots"]
    assert [slot["role"] for slot in partial_slots] == ["security"]


def test_out_of_contract_input_is_rejected():
    with pytest.raises(InterpreterError):
        reduce([decide("r-none", "d-none", "v-none", "dec-x", "a", "legal",
                       "APPROVE")])
    with pytest.raises(InterpreterError):
        reduce([{"kind": "quantum", "op": "teleport"}])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__]))
