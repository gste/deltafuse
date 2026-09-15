"""Tests for external worker transport adapter (J03-501)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.document_flow.worker.adapter import (
    LittleCoderTransport,
    WorkerEvent,
    WorkerTransportError,
)


MOCK_WORKER_SCRIPT = """
import sys
import json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue
    
    req_type = req.get("type")
    req_id = req.get("id", "none")
    
    if req_type == "exit":
        resp = {"id": req_id, "status": "ok", "result": "exited"}
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
        break
    elif req_type == "get_state":
        resp = {"id": req_id, "status": "ok", "state": {"model": "poolside/laguna-xs-2.1", "isCompacting": False}}
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    elif req_type == "pause_session":
        resp = {"id": req_id, "status": "ok", "paused": True, "reason": req.get("params", {}).get("reason")}
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    else:
        resp = {"id": req_id, "status": "ok", "received": req}
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
"""


def test_transport_lifecycle(tmp_path):
    mock_script = tmp_path / "mock_worker.py"
    mock_script.write_text(MOCK_WORKER_SCRIPT, encoding="utf-8")
    
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({
        "schema_version": 1,
        "worker_id": "mock-worker",
        "flags": [],
    }), encoding="utf-8")
    
    transport = LittleCoderTransport(
        profile_path=profile_path,
        working_dir=tmp_path,
        custom_launcher=[sys.executable, str(mock_script)],
    )
    
    transport.start()
    
    # 1. get_state
    resp = transport.send_command("get_state")
    assert resp["status"] == "ok"
    assert resp["state"]["model"] == "poolside/laguna-xs-2.1"
    
    # 2. pause_for_gate
    gate_resp = transport.pause_for_gate()
    assert gate_resp["status"] == "ok"
    assert gate_resp["paused"] is True
    assert gate_resp["reason"] == "human_gate"
    
    # 3. halt
    transport.halt()
    assert transport.process is None


def test_transport_rejects_unauthorized_bypass(tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    
    transport = LittleCoderTransport(
        profile_path=profile_path,
        working_dir=tmp_path,
        custom_launcher=[sys.executable, "-c", "import time; time.sleep(1)"],
    )
    transport.start()
    
    with pytest.raises(WorkerTransportError, match="unauthorized shell execution bypass"):
        transport.send_command("bash", {"command": "bypass check"})
    
    transport.halt()
