import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[3]
HIDDEN_PATH = ROOT / "process/bench/cases/J03-document-flow/hidden_suite/test_functional.py"

def _load_functional_module():
    spec = importlib.util.spec_from_file_location("j03_hidden_test_functional", HIDDEN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

_func_mod = _load_functional_module()
CHECKS = _func_mod.CHECKS
derive_facts = _func_mod.derive_facts
earned_points = _func_mod.earned_points
expected = _func_mod.expected


MUT_DIR = Path("process/bench/cases/J03-document-flow/mutations/functional")


def test_functional_mutants_manifest_structure():
    manifest = json.loads((MUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    mutants = manifest["mutants"]
    assert len(mutants) == 6
    ids = [m["id"] for m in mutants]
    assert set(ids) == {"M09", "M10", "M11", "M12", "M13", "M22"}
    critical_ids = {m["id"] for m in mutants if m.get("critical")}
    assert critical_ids == {"M09", "M10", "M11", "M12", "M13"}


def _mock_observations():
    """Helper creating standard base observations structure."""
    obs = {}
    for check in CHECKS:
        for variant in check["variants"]:
            s = variant["schedule_id"]
            exp = expected(variant)
            routes = []
            for doc, dval in exp["documents"].items():
                for ver, st in dval["routes"].items():
                    routes.append({"route_id": f"r-{doc}-{ver}", "document_id": doc, "version_id": ver, "state": st})
            decisions = []
            audit = []
            calls = []
            for op in variant["operations"]:
                calls.append({"operation": op, "result": {"ok": True, "body": {}}})
                if op.get("op") == "decision":
                    decisions.append({
                        "route_id": f"r-{op.get('document_id')}-{op.get('version_id', 'v1')}",
                        "decision_id": op.get("decision_id"),
                        "actor_id": op.get("actor_id"),
                        "role": op.get("role"),
                        "action": op.get("action"),
                        "resulting_state": "APPROVED"
                    })
            for doc, kinds in exp["audit"].items():
                for k in kinds:
                    audit.append({"kind": k, "document_id": doc})
            obs[s] = {
                "calls": calls,
                "errors": [],
                "routes": routes,
                "decisions": decisions,
                "audit": audit,
                "versions": [],
                "expected": exp,
            }
    return obs


def test_m09_duplicate_event_applied_twice_fails_sys_f08():
    # M09: duplicate submission creates two routes instead of one
    obs = _mock_observations()
    obs["f08-duplicate"]["routes"].append({
        "route_id": "r-duplicate-2",
        "document_id": "f08a-doc",
        "version_id": "v1",
        "state": "PENDING"
    })
    facts = derive_facts(obs)
    assert facts["F08.duplicate-no-effect"] is False
    # Check that SYS.F08 failed
    f08_check = next(c for c in CHECKS if c["id"] == "SYS.F08")
    assert not all(facts[a] for a in f08_check["assertions"])


def test_m10_decision_bound_only_to_document_fails_sys_f06_f08():
    # M10: late decision alters state or identity mismatch not raised
    obs = _mock_observations()
    # In M10, audit kinds for late decisions lack ignored audit or identity bound fails
    obs["f06-late-approve"]["audit"] = [
        {"kind": "j03.workflow.decision-applied", "document_id": "f06a-doc"}
    ]
    facts = derive_facts(obs)
    assert facts["F06.late-approve-audited"] is False
    f06_check = next(c for c in CHECKS if c["id"] == "SYS.F06")
    assert not all(facts[a] for a in f06_check["assertions"])


def test_m11_superseded_route_accepts_late_decision_fails_sys_f06():
    # M11: late decisions are not ignored
    obs = _mock_observations()
    obs["f06-late-approve"]["audit"] = [
        {"kind": "j03.workflow.decision-applied", "document_id": "f06a-doc"}
    ]
    facts = derive_facts(obs)
    assert facts["F06.late-approve-audited"] is False
    f06_check = next(c for c in CHECKS if c["id"] == "SYS.F06")
    assert not all(facts[a] for a in f06_check["assertions"])


def test_m12_registrar_opens_after_one_expert_approval_fails_sys_f07():
    # M12: early registrar call accepted without EXPERT_REVIEW_INCOMPLETE error
    obs = _mock_observations()
    obs["f07-early-registrar"]["calls"] = [
        {"result": {"body": {"state": "APPROVED"}}}
    ]
    facts = derive_facts(obs)
    assert facts["F07.early-invalid"] is False
    f07_check = next(c for c in CHECKS if c["id"] == "SYS.F07")
    assert not all(facts[a] for a in f07_check["assertions"])


def test_m13_one_actor_closes_two_roles_fails_sys_f08():
    # M13: actor reuse permitted and not rejected
    obs = _mock_observations()
    obs["f08-actor-reuse"]["calls"] = [
        {"result": {"body": {"state": "APPROVED"}}}
    ]
    # actor_id is duplicated in decisions
    obs["f08-actor-reuse"]["decisions"] = [
        {"actor_id": "same_actor", "role": "legal"},
        {"actor_id": "same_actor", "role": "security"},
    ]
    facts = derive_facts(obs)
    assert facts["F08.distinct-actors"] is False or facts["F08.identity-bound"] is False
    f08_check = next(c for c in CHECKS if c["id"] == "SYS.F08")
    assert not all(facts[a] for a in f08_check["assertions"])


def test_m22_hardcoded_public_scenario_fails_sys_f09():
    # M22: fails on interleaved documents
    obs = _mock_observations()
    # Simulate single shared document / missing isolation for interleaved
    obs["f09-interleaved-a"]["routes"] = [{"route_id": "r1", "document_id": "only_one_doc", "version_id": "v1"}]
    facts = derive_facts(obs)
    assert facts["F09.independent-documents"] is False
    f09_check = next(c for c in CHECKS if c["id"] == "SYS.F09")
    assert not all(facts[a] for a in f09_check["assertions"])
