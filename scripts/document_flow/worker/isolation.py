"""Worker container and host isolation policy verification (J03-505)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class IsolationVerificationResult:
    valid: bool
    mismatches: list[str]
    policy_snapshot: dict[str, Any]


# Required Worker container isolation policy
EXPECTED_WORKER_ISOLATION = {
    "network_mode": "none",
    "read_only_rootfs": True,
    "user": "1000:1000",
    "cap_drop": "ALL",
    "no_new_privileges": True,
}


def verify_worker_isolation_policy(
    measured_policy: Mapping[str, Any],
    *,
    expected: Mapping[str, Any] | None = None,
    allow_proxy_network: bool = False,
) -> IsolationVerificationResult:
    """Verify runtime inspect facts of Worker container against isolation contract."""
    target_exp = expected or EXPECTED_WORKER_ISOLATION
    mismatches: list[str] = []

    # 1. Network policy
    net_mode = measured_policy.get("network_mode")
    if allow_proxy_network:
        if net_mode not in ("none", "bridge", "container:proxy"):
            mismatches.append(f"unexpected network mode: {net_mode}")
    else:
        if net_mode != target_exp.get("network_mode", "none"):
            mismatches.append(f"network_mode={net_mode} (expected {target_exp.get('network_mode')})")

    # 2. Read-only rootfs
    if not measured_policy.get("read_only_rootfs"):
        mismatches.append("rootfs is writable (expected read-only)")

    # 3. Non-root user
    user = str(measured_policy.get("user", ""))
    if user in ("", "0", "0:0", "root"):
        mismatches.append(f"running as root user: {user}")

    # 4. Capabilities
    cap_drop = measured_policy.get("cap_drop", [])
    if isinstance(cap_drop, str):
        cap_drop = [cap_drop]
    if "ALL" not in cap_drop:
        mismatches.append(f"cap_drop={cap_drop} (expected ALL)")

    # 5. Privileges
    if not measured_policy.get("no_new_privileges"):
        mismatches.append("no_new_privileges is false")

    # 6. Mounts check: forbid mounting docker socket or judge pack
    mounts = measured_policy.get("mounts", [])
    for m in mounts:
        dest = m.get("destination", "")
        src = m.get("source", "")
        if "docker.sock" in dest or "docker.sock" in src:
            mismatches.append(f"docker socket mounted: {dest}")
        if "process/bench" in src or "backlog" in src:
            mismatches.append(f"judge material mounted: {src}")

    return IsolationVerificationResult(
        valid=len(mismatches) == 0,
        mismatches=mismatches,
        policy_snapshot=dict(measured_policy),
    )
