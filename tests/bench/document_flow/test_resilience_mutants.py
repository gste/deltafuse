"""Tests for Java resilience and atomicity mutant calibration (J03-603)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[3]
HIDDEN_DIR = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"

def _load(name: str):
    spec = importlib.util.spec_from_file_location("j03_hidden_" + name, HIDDEN_DIR / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

resilience_mod = _load("test_resilience")
atomicity_mod = _load("test_atomicity")
consistency_mod = _load("test_consistency")

MUT_DIR = Path("process/bench/cases/J03-document-flow/mutations/resilience")


def test_resilience_mutants_manifest_structure():
    manifest = json.loads((MUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    mutants = manifest["mutants"]
    assert len(mutants) == 7
    ids = [m["id"] for m in mutants]
    assert set(ids) == {"M14", "M15", "M16", "M17", "M18", "M19", "M20"}
    assert all(m.get("critical") is True for m in mutants)


def test_m14_non_atomic_inbox_outbox_fails_sys_c01_and_sys_r01():
    # M14: state update commits without atomic inbox/outbox -> fails inbox_outbox_consistent or crash recovery
    atom_obs = {
        "inbox_outbox_consistent": False,
        "delivery_receipt": True,
        "cross_service_write_denied": True,
    }
    facts = atomicity_mod.derive_facts(atom_obs)
    assert facts["C01.atomic-state"] is False
    assert atomicity_mod.earned_points(facts) == 0
    assert "SYS.C01" in atomicity_mod.expected_failed_ids(facts)

    # In resilience R01, unatomic commit leads to duplicate effect or unrecovered state
    res_obs = {
        "fault_receipts": [
            {"point": "after-commit-before-ack", "acknowledged": True, "measured_sequence": 1,
             "recovered": False, "effect_count": 2}
        ]
    }
    r_facts = resilience_mod.derive_facts(res_obs)
    assert r_facts["R01.commit-survives-ack-loss"] is False
    assert "SYS.R01" in resilience_mod.expected_failed_ids(r_facts)


def test_m15_direct_publish_without_outbox_fails_sys_c01_and_sys_r02():
    # M15: publisher sends directly without transactional outbox
    atom_obs = {
        "inbox_outbox_consistent": False,
        "delivery_receipt": True,
        "cross_service_write_denied": True,
    }
    facts = atomicity_mod.derive_facts(atom_obs)
    assert "SYS.C01" in atomicity_mod.expected_failed_ids(facts)

    # In resilience R02, publish failure loses message
    res_obs = {
        "fault_receipts": [
            {"point": "after-publish-before-sent", "acknowledged": True, "measured_sequence": 2,
             "recovered": False, "published_count": 0}
        ]
    }
    r_facts = resilience_mod.derive_facts(res_obs)
    assert r_facts["R02.publish-survives-sent-loss"] is False
    assert "SYS.R02" in resilience_mod.expected_failed_ids(r_facts)


def test_m16_synchronous_http_replaces_kafka_fails_sys_c01():
    # M16: synchronous HTTP lacks asynchronous inbox/outbox delivery receipt & outbox records
    atom_obs = {
        "inbox_outbox_consistent": False,
        "delivery_receipt": False,
        "cross_service_write_denied": True,
    }
    facts = atomicity_mod.derive_facts(atom_obs)
    assert "SYS.C01" in atomicity_mod.expected_failed_ids(facts)


def test_m17_invalid_message_dlq_after_partial_update_fails_sys_c02():
    # M17: invalid message modifies domain state before sending to DLQ
    cons_facts = {
        "C02.dlq": True,
        "C02.no-transition": False, # domain state changed!
        "C03.baseline-shape": True,
    }
    pts = consistency_mod.earned_points(cons_facts)
    assert pts == 80 # C02 failed because C02.no-transition is False


def test_m18_replay_duplicates_audit_rows_fails_sys_r03():
    # M18: topic replay causes duplicate audit events
    res_obs = {
        "fault_receipts": [
            {"point": "topic-replay", "acknowledged": True, "measured_sequence": 3,
             "replayed": True, "audit_count": 10, "unique_event_count": 5}
        ]
    }
    facts = resilience_mod.derive_facts(res_obs)
    assert facts["R03.audit-deduplicated"] is False
    assert "SYS.R03" in resilience_mod.expected_failed_ids(facts)


def test_m19_consumer_restart_loses_or_doubles_effect_fails_sys_r01():
    # M19: crash before ack duplicates effect on restart
    res_obs = {
        "fault_receipts": [
            {"point": "after-commit-before-ack", "acknowledged": True, "measured_sequence": 1,
             "recovered": True, "effect_count": 2}
        ]
    }
    facts = resilience_mod.derive_facts(res_obs)
    assert facts["R01.no-duplicate-effect"] is False
    assert "SYS.R01" in resilience_mod.expected_failed_ids(facts)


def test_m20_shared_db_transaction_fails_sys_c01():
    # M20: cross-service database access permitted
    atom_obs = {
        "inbox_outbox_consistent": True,
        "delivery_receipt": True,
        "cross_service_write_denied": False, # cross-service isolation violated!
    }
    facts = atomicity_mod.derive_facts(atom_obs)
    assert facts["C01.database-separated"] is False
    assert "SYS.C01" in atomicity_mod.expected_failed_ids(facts)
