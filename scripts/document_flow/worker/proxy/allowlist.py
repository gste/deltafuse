"""Inference allow-list proxy for isolating external Worker egress (J03-505)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProxyDecision:
    allowed: bool
    reason: str | None
    target_host: str | None
    target_port: int | None


class InferenceAllowlistProxy:
    """Restricts outbound HTTP/RPC traffic to pre-registered inference endpoints."""

    def __init__(self, allowed_endpoints: list[str] | tuple[str, ...]) -> None:
        self.allowed_endpoints = tuple(allowed_endpoints)
        self._parsed_endpoints = [urlparse(ep) for ep in self.allowed_endpoints]

    def evaluate_request(self, target_url: str, method: str = "POST") -> ProxyDecision:
        """Evaluate if an outbound request URL matches allowed inference endpoints."""
        try:
            parsed = urlparse(target_url)
        except Exception as exc:
            return ProxyDecision(allowed=False, reason=f"malformed URL: {exc}", target_host=None, target_port=None)

        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # Disallow internal loopback bypasses unless explicitly specified
        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            is_explicit_local = any(
                p.hostname in ("localhost", "127.0.0.1", "::1") and (p.port or 80) == port
                for p in self._parsed_endpoints
            )
            if not is_explicit_local:
                return ProxyDecision(allowed=False, reason="loopback host not in allowed endpoints", target_host=host, target_port=port)

        # Check against allowed endpoints
        for allowed in self._parsed_endpoints:
            a_host = allowed.hostname
            a_port = allowed.port or (443 if allowed.scheme == "https" else 80)
            if host == a_host and port == a_port:
                # Check path prefix
                if not allowed.path or parsed.path.startswith(allowed.path):
                    return ProxyDecision(allowed=True, reason=None, target_host=host, target_port=port)

        return ProxyDecision(
            allowed=False,
            reason=f"egress to {host}:{port} is forbidden by benchmark proxy policy",
            target_host=host,
            target_port=port,
        )
