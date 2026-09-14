"""Private frozen SYS.F01-F09 scenarios; not imported into the public seed."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


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
