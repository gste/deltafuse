"""Tests for verifying external worker adapter process boundary (J03-508)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from scripts.document_flow.worker.adapter import LittleCoderTransport, WorkerTransportError


def test_external_adapter_process_protocol(tmp_path):
    # Verified scripted worker process executing exact Pi RPC protocol
    mock_py = tmp_path / "rpc_server.py"
    mock_py.write_text("""
import sys, json

for line in sys.stdin:
    if not line.strip():
        continue
    req = json.loads(line)
    req_type = req.get("type")
    req_id = req.get("id")
    
    if req_type == "get_state":
        res = {"id": req_id, "status": "ok", "state": {"model": "poolside/laguna-xs-2.1", "isCompacting": False}}
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif req_type == "pause_session":
        res = {"id": req_id, "status": "ok", "paused": True}
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
    elif req_type == "exit":
        res = {"id": req_id, "status": "ok"}
        sys.stdout.write(json.dumps(res) + "\\n")
        sys.stdout.flush()
        break
""", encoding="utf-8")

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({
        "schema_version": 1,
        "flags": [],
    }), encoding="utf-8")

    transport = LittleCoderTransport(
        profile_path=profile_path,
        working_dir=tmp_path,
        custom_launcher=[sys.executable, str(mock_py)],
    )

    transport.start()
    
    # 1. State check
    st = transport.send_command("get_state")
    assert st["status"] == "ok"
    assert st["state"]["model"] == "poolside/laguna-xs-2.1"
    
    # 2. Gate pause check
    p = transport.pause_for_gate()
    assert p["status"] == "ok"
    assert p["paused"] is True
    
    # 3. Clean exit
    transport.halt()
    assert transport.process is None
