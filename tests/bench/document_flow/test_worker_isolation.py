"""Tests for Worker network and filesystem isolation policy (J03-505)."""

from __future__ import annotations

import pytest

from scripts.document_flow.worker.isolation import verify_worker_isolation_policy
from scripts.document_flow.worker.proxy.allowlist import InferenceAllowlistProxy


def test_proxy_allowlist_matching():
    proxy = InferenceAllowlistProxy([
        "https://api.poolside.ai/v1",
        "http://127.0.0.1:8000/v1",
    ])

    # 1. Allowed external endpoint
    d1 = proxy.evaluate_request("https://api.poolside.ai/v1/chat/completions")
    assert d1.allowed is True

    # 2. Allowed local endpoint
    d2 = proxy.evaluate_request("http://127.0.0.1:8000/v1/models")
    assert d2.allowed is True

    # 3. Forbidden external endpoint
    d3 = proxy.evaluate_request("https://api.openai.com/v1/chat/completions")
    assert d3.allowed is False
    assert "forbidden by benchmark proxy policy" in d3.reason

    # 4. Forbidden internal port
    d4 = proxy.evaluate_request("http://127.0.0.1:5432/db")
    assert d4.allowed is False


def test_worker_isolation_policy_verification_clean():
    measured = {
        "network_mode": "none",
        "read_only_rootfs": True,
        "user": "1000:1000",
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "mounts": [
            {"destination": "/sandbox", "source": "/tmp/sandbox-1", "rw": True}
        ],
    }
    res = verify_worker_isolation_policy(measured)
    assert res.valid is True
    assert len(res.mismatches) == 0


def test_worker_isolation_policy_verification_violations():
    measured = {
        "network_mode": "bridge",
        "read_only_rootfs": False,
        "user": "root",
        "cap_drop": [],
        "no_new_privileges": False,
        "mounts": [
            {"destination": "/var/run/docker.sock", "source": "/var/run/docker.sock", "rw": True},
            {"destination": "/judge", "source": "/repo/process/bench", "rw": False},
        ],
    }
    res = verify_worker_isolation_policy(measured)
    assert res.valid is False
    assert any("network_mode" in m for m in res.mismatches)
    assert any("writable" in m for m in res.mismatches)
    assert any("root user" in m for m in res.mismatches)
    assert any("docker socket" in m for m in res.mismatches)
    assert any("judge material" in m for m in res.mismatches)
