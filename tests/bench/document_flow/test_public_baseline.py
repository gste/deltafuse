"""Judge-side contract tests for the J03 public baseline suite.

Without a live stack these checks stay portable: the suite sources and
fixtures must exist, parse, carry the named public assertions, and reject a
simulated duplicate-audit observation with the named replay-guard assertion.
With J03_PUBLIC_BASELINE_LIVE=1 the full suite is executed against the live
stack identified by J03_PUBLIC_BASELINE_ARGS (its exact command line).
"""

import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[3]
CASE = ROOT / "process/bench/cases/J03-document-flow"
SUITE = CASE / "public_suite"
SYSTEM = CASE / "seed/tests/system"

ASSERTION_IDS = [
    "J03-PUB-001", "J03-PUB-002", "J03-PUB-003", "J03-PUB-004",
    "J03-PUB-005", "J03-PUB-006", "J03-PUB-007", "J03-PUB-008",
    "J03-PUB-009", "J03-PUB-010", "J03-PUB-011", "J03-PUB-012",
]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _suite_source(path):
    return (SUITE / path).read_text(encoding="utf-8")


def test_public_suite_files_exist_and_parse():
    for path in ("clients.py", "baseline_suite.py"):
        ast.parse(_suite_source(path), filename=path)
    for fixture in ("approve.json", "reject.json"):
        json.loads((SYSTEM / "fixtures" / fixture).read_text(encoding="utf-8"))


def test_suite_covers_every_named_public_assertion():
    source = _suite_source("baseline_suite.py") + _suite_source("clients.py")
    for assertion_id in ASSERTION_IDS:
        assert assertion_id in source, "missing named assertion " + assertion_id
    assert "J03-PUB-INF-001" in _suite_source("clients.py")
    assert "VERSION_IMMUTABLE" in _suite_source("baseline_suite.py")
    assert "IDEMPOTENCY_CONFLICT" in _suite_source("baseline_suite.py")


def test_fixtures_match_the_suite_scenarios():
    approve = json.loads((SYSTEM / "fixtures" / "approve.json").read_text(encoding="utf-8"))
    reject = json.loads((SYSTEM / "fixtures" / "reject.json").read_text(encoding="utf-8"))
    _load_module("clients", SUITE / "clients.py")
    suite = _load_module("j03_baseline_suite", SUITE / "baseline_suite.py")
    assert approve["document"]["document_id"] == suite.APPROVE_DOC["document_id"]
    assert approve["decision"]["decision_id"] == "pub-dec-approve-1"
    assert reject["document"]["document_id"] == suite.REJECT_DOC["document_id"]
    assert reject["expected"]["resubmit_error"] == "VERSION_IMMUTABLE"
    assert approve["decision"]["action"] in ("APPROVE", "REJECT")


def test_duplicate_audit_observation_fails_the_named_replay_guard():
    _load_module("clients", SUITE / "clients.py")
    suite = _load_module("j03_baseline_suite", SUITE / "baseline_suite.py")
    clients = sys.modules["clients"]
    stable = [{"event_id": "evt-1", "kind": "j03.workflow.decision-applied"}]
    suite.assert_audit_unchanged(stable, list(stable))
    duplicated = stable + [dict(stable[0], event_id="evt-1-replayed")]
    with pytest.raises(clients.PublicFailure) as failure:
        suite.assert_audit_unchanged(stable, duplicated)
    assert failure.value.assertion_id == "J03-PUB-010"


def test_exit_contract_is_the_published_one():
    clients = _load_module("j03_public_clients", SUITE / "clients.py")
    assert (clients.EXIT_PASS, clients.EXIT_VALID_FAILURE,
            clients.EXIT_INVOCATION, clients.EXIT_INFRASTRUCTURE) == (0, 1, 2, 3)

def test_live_suite_passes_against_the_pinned_stack_when_selected():
    if os.environ.get("J03_PUBLIC_BASELINE_LIVE") != "1":
        pytest.skip("live public stack not selected; portable checks passed")
    args = os.environ.get("J03_PUBLIC_BASELINE_ARGS")
    assert args, "J03_PUBLIC_BASELINE_ARGS must carry the suite command line"
    finished = subprocess.run(
        [sys.executable, str(SUITE / "baseline_suite.py")] + args.split(),
        capture_output=True, text=True, timeout=600)
    assert finished.returncode == 0, (
        "public suite failed (%s):\nstdout=%s\nstderr=%s"
        % (finished.returncode, finished.stdout, finished.stderr))
