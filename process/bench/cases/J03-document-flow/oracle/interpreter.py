"""Independent pure domain oracle for the J03 document flow.

This module is the private judge-side model of the product semantics. It is
deliberately written from the public contract and the target intake alone:
it shares no code, imports or state machine with the Java services and it
never consults the variant generator. ``reduce`` folds an operation stream
into the expected final state and per-document audit; ``stop_before`` folds
only a prefix so callers can derive the expected state at a crash barrier.

Modeling boundaries (recorded for the judge):
- a submission immediately opens (or supersedes to) the route; delivery and
  crash operations only carry transport identity and change nothing;
- route ids are opaque: the model binds an id when an operation reveals it
  and matches decisions by (document, version) binding;
- slot *assignment* is workflow-internal, so open slots carry ``None``
  assignments and actor binding is enforced by role-fill history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXPERT_ROLES = ("legal", "security")
ROLE_ORDER = {"legal": 0, "security": 1, "registrar": 2}

AUDIT_CREATED = "j03.document.created"
AUDIT_VERSION = "j03.document.version-created"
AUDIT_SUBMITTED = "j03.document.version-submitted"
AUDIT_ROUTE = "j03.workflow.route-created"
AUDIT_SUPERSEDED = "j03.workflow.route-superseded"
AUDIT_DECIDED = "j03.workflow.decision-applied"


class InterpreterError(ValueError):
    """The operation stream violates the contract the model understands."""


@dataclass
class Route:
    document_id: str
    version_id: str
    route_id: str | None = None
    state: str = "PENDING"
    filled: dict[str, str] = field(default_factory=dict)
    approved_experts: set[str] = field(default_factory=set)
    decisions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Document:
    document_id: str
    title: str
    versions: list[str] = field(default_factory=list)
    active_version: str | None = None
    routes: dict[tuple[str, str], Route] = field(default_factory=dict)
    route_order: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class AuditEntry:
    sequence: int
    kind: str
    event_id: str | None = None
    detail: str | None = None


@dataclass
class ExpectedState:
    documents: dict[str, Document] = field(default_factory=dict)
    audit: dict[str, list[AuditEntry]] = field(default_factory=dict)
    consumed: int = 0

    def audit_kinds(self, document_id: str) -> list[str]:
        return [entry.kind for entry in self.audit.get(document_id, [])]

    def observation(self, document_id: str) -> dict[str, Any]:
        document = self.documents[document_id]
        active_key = (document.document_id, document.active_version) \
            if document.active_version else None
        route = document.routes.get(active_key) if active_key else None
        open_slots: list[dict[str, Any]] = []
        if route is not None and route.state == "PENDING":
            if any(expert not in route.filled for expert in EXPERT_ROLES):
                open_slots = [{"role": role, "assigned_actor_id": None}
                              for role in EXPERT_ROLES
                              if role not in route.filled]
            else:
                open_slots = [{"role": "registrar", "assigned_actor_id": None}]
        audit = [{"sequence": entry.sequence, "event_id": entry.event_id,
                  "kind": entry.kind}
                 for entry in self.audit.get(document_id, [])]
        return {
            "document": {"document_id": document.document_id},
            "active_version": ({"immutable": True,
                                "version_id": document.active_version}
                               if document.active_version else None),
            "workflow": ({"route_id": route.route_id, "state": route.state}
                         if route is not None else None),
            "open_slots": open_slots,
            "audit_sequence": audit,
        }


def reduce(operations: list[dict[str, Any]], *,
           stop_before: int | None = None) -> ExpectedState:
    state = ExpectedState()
    selected = operations if stop_before is None else list(operations)[:stop_before]
    for operation in selected:
        _apply(state, operation)
        state.consumed += 1
    return state


def _audit(state: ExpectedState, document_id: str, kind: str, *,
           event_id: str | None = None, detail: str | None = None) -> None:
    entries = state.audit.setdefault(document_id, [])
    entries.append(AuditEntry(len(entries) + 1, kind, event_id, detail))


def _open_route(document: Document) -> Route | None:
    for key in reversed(document.route_order):
        route = document.routes[key]
        if route.state == "PENDING":
            return route
    return None


def _apply(state: ExpectedState, operation: dict[str, Any]) -> None:
    kind = operation.get("kind")
    if kind in ("delivery", "duplicate-delivery"):
        route = _find_route(state, operation)
        if route is not None and route.route_id is None \
                and operation.get("route_id"):
            route.route_id = operation["route_id"]
        return
    if kind == "crash":
        return
    if kind == "http":
        _apply_command(state, operation)
        return
    if kind == "decision":
        _apply_decision(state, operation)
        return
    raise InterpreterError("unknown operation kind: %r" % (kind,))


def _find_route(state: ExpectedState, operation: dict[str, Any]) -> Route | None:
    document = state.documents.get(operation.get("document_id"))
    if document is None:
        return None
    return document.routes.get(
        (document.document_id, operation.get("version_id")))


def _apply_command(state: ExpectedState, operation: dict[str, Any]) -> None:
    op = operation["op"]
    document_id = operation["document_id"]
    if op == "create-document":
        if document_id in state.documents:
            raise InterpreterError("document created twice: " + document_id)
        state.documents[document_id] = Document(document_id,
                                                operation.get("title", ""))
        state.audit.setdefault(document_id, [])
        _audit(state, document_id, AUDIT_CREATED,
               event_id=operation.get("event_id"))
        return
    document = state.documents.get(document_id)
    if document is None:
        raise InterpreterError("command for unknown document: " + document_id)
    if op == "create-version":
        document.versions.append(operation["version_id"])
        document.active_version = operation["version_id"]
        _audit(state, document_id, AUDIT_VERSION,
               event_id=operation.get("event_id"))
        return
    if op == "submit-version":
        version_id = operation["version_id"]
        if version_id not in document.versions:
            raise InterpreterError("submitted version was never created: "
                                   + version_id)
        document.active_version = version_id
        _audit(state, document_id, AUDIT_SUBMITTED,
               event_id=operation.get("event_id"))
        open_route = _open_route(document)
        if open_route is not None:
            open_route.state = "SUPERSEDED"
            _audit(state, document_id, AUDIT_SUPERSEDED,
                   event_id=operation.get("event_id"),
                   detail=open_route.version_id)
        key = (document_id, version_id)
        if key in document.routes:
            _audit(state, document_id, "VERSION_IMMUTABLE",
                   detail="version already carries a route")
            return
        document.routes[key] = Route(document_id=document_id,
                                     version_id=version_id)
        document.route_order.append(key)
        _audit(state, document_id, AUDIT_ROUTE,
               event_id=operation.get("event_id"))
        return
    raise InterpreterError("unknown command: %r" % (op,))


def _apply_decision(state: ExpectedState, operation: dict[str, Any]) -> None:
    document_id = operation["document_id"]
    version_id = operation["version_id"]
    document = state.documents.get(document_id)
    if document is None:
        raise InterpreterError("decision for unknown document: " + document_id)
    key = (document_id, version_id)
    route = document.routes.get(key)
    if route is None:
        # The route id may have been revealed by a delivery before the
        # (document, version) binding could match; fall back to the id.
        for candidate_key, candidate in document.routes.items():
            if candidate.route_id == operation.get("route_id"):
                route = candidate
                key = candidate_key
                break
    if route is None:
        raise InterpreterError("decision for unknown route: "
                               + str(operation.get("route_id")))
    event_id = operation.get("event_id")

    def invalid(code: str, detail: str) -> None:
        _audit(state, document_id, code, event_id=event_id, detail=detail)

    if (route.route_id and operation.get("route_id")
            and route.route_id != operation["route_id"]):
        invalid("IDENTITY_MISMATCH", "route id does not address this route")
        return
    if route.document_id != document_id or route.version_id != version_id:
        invalid("IDENTITY_MISMATCH", "document or version binding differs")
        return
    role = operation["role"]
    action = operation["action"]
    if role not in EXPERT_ROLES and role != "registrar":
        invalid("INVALID_SCHEMA", "unknown role: " + str(role))
        return
    if action not in ("APPROVE", "REJECT"):
        invalid("INVALID_SCHEMA", "unknown action: " + str(action))
        return

    prior = next((entry for entry in route.decisions
                  if entry["decision_id"] == operation["decision_id"]), None)
    if prior is not None:
        same = all(prior[name] == operation[name]
                   for name in ("actor_id", "role", "action"))
        if same:
            return  # idempotent replay: prior result, no new effect
        invalid("IDEMPOTENCY_CONFLICT",
                "decision id replayed with a different payload")
        return

    if route.state == "SUPERSEDED":
        invalid("IGNORED_LATE_DECISION", "route was superseded")
        return
    if route.state in ("APPROVED", "REJECTED"):
        invalid("IDENTITY_MISMATCH", "route is already closed")
        return

    if role == "registrar":
        if action == "REJECT":
            invalid("UNSUPPORTED_ACTION", "registrar rejection is not a decision")
            return
        if route.approved_experts != set(EXPERT_ROLES):
            invalid("EXPERT_REVIEW_INCOMPLETE",
                    "expert review has not completed")
            return
        route.state = "APPROVED"
    else:
        if role in route.filled:
            invalid("IDENTITY_MISMATCH", "expert slot already filled")
            return
        other = next((expert for expert in EXPERT_ROLES
                      if expert != role and route.filled.get(expert)
                      == operation["actor_id"]), None)
        if other is not None:
            invalid("ACTOR_ROLE_MISMATCH",
                    "actor already filled the %s role" % other)
            return
        route.filled[role] = operation["actor_id"]
        if action == "REJECT":
            route.state = "REJECTED"
        else:
            route.approved_experts.add(role)

    route.decisions.append({
        "decision_id": operation["decision_id"],
        "actor_id": operation["actor_id"],
        "role": role,
        "action": action,
    })
    _audit(state, document_id, AUDIT_DECIDED, event_id=event_id)
