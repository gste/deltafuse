"""Tests for shell subprocess command boundary and observation (J03-504)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.document_flow.store import EvidenceStore
from scripts.document_flow.worker.command_boundary import CommandBoundaryRunner


SCHEMAS_DIR = Path("scripts/document_flow/schemas")


def get_event_validator():
    ev_schema = json.loads((SCHEMAS_DIR / "event.schema.json").read_text(encoding="utf-8"))
    ref_schema = json.loads((SCHEMAS_DIR / "evidence-ref.schema.json").read_text(encoding="utf-8"))
    
    registry = Registry().with_resources([
        (ev_schema["$id"], Resource.from_contents(ev_schema)),
        (ref_schema["$id"], Resource.from_contents(ref_schema)),
    ])
    return Draft202012Validator(ev_schema, registry=registry)


def test_command_boundary_runner_success(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    runner = CommandBoundaryRunner(store, product_root=tmp_path)
    validator = get_event_validator()

    res, event = runner.run_command(
        [sys.executable, "-c", "print('hello from sandboxed process')"],
        envelope={"write": ["*"]},
    )

    validator.validate(event)
    assert res.exit_code == 0
    assert res.timed_out is False
    assert res.stdout_ref is not None
    assert store.resolve(res.stdout_ref).decode("utf-8").strip() == "hello from sandboxed process"


def test_command_boundary_runner_timeout(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    runner = CommandBoundaryRunner(store, product_root=tmp_path)
    validator = get_event_validator()

    res, event = runner.run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_sec=1,
        envelope={"write": ["*"]},
    )

    validator.validate(event)
    assert res.timed_out is True
    assert res.exit_code is None
    assert event["payload"]["timed_out"] is True


def test_command_boundary_runner_forbidden_command(tmp_path):
    store = EvidenceStore.create(tmp_path / "store", "run-1", "root-1")
    runner = CommandBoundaryRunner(store, product_root=tmp_path)

    with pytest.raises(PermissionError, match="command boundary violation"):
        runner.run_command(["curl", "http://forbidden-host.com"], envelope={"write": ["*"]})
