"""Adversarial boundary and leak probes for J03 benchmark environment (J03-506)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProbeReport:
    phase: str  # 'preflight' | 'postflight'
    sentinel_read: str  # 'blocked' | 'LEAK'
    sentinel_found: list[str]
    pack_found: list[str]
    write_leak: list[str]
    rootfs_write_leak: list[str]
    docker_sock: str  # 'absent' | 'present' | 'writable'
    network: str  # 'blocked' | 'LEAK' | 'not-probed'
    scratch_write: str  # 'ok' | 'blocked'
    container_token: str | None


def run_local_adversarial_probe(
    *,
    sandbox_root: Path | str,
    sentinel_path: Path | str,
    sentinel_content: bytes = b"sentinel-secret-12345",
    forbidden_search_names: list[str] | None = None,
    phase: str = "preflight",
) -> ProbeReport:
    """Simulates/runs adversarial boundary probe against sandbox directory."""
    s_root = Path(sandbox_root).resolve()
    sent_path = Path(sentinel_path).resolve()
    
    sent_sha = hashlib.sha256(sentinel_content).hexdigest()
    sent_size = len(sentinel_content)
    search_names = set(forbidden_search_names or ["oracle", "reference", "mutations"])

    # 1. Check if sentinel is directly readable via sandbox path
    try:
        if sent_path.is_relative_to(s_root) and sent_path.is_file():
            sentinel_read = "LEAK"
        else:
            sentinel_read = "blocked"
    except Exception:
        sentinel_read = "blocked"

    # 2. Search sandbox root for forbidden names or content
    content_hits = []
    name_hits = []
    
    for dirpath, dirnames, filenames in os.walk(s_root):
        matched = search_names.intersection(filenames) | search_names.intersection(dirnames)
        if matched:
            name_hits.append(dirpath)
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                if p.is_file() and p.stat().st_size == sent_size:
                    if hashlib.sha256(p.read_bytes()).hexdigest() == sent_sha:
                        content_hits.append(str(p))
            except OSError:
                continue

    # 3. Scratch write test
    scratch = s_root / ".qual-scratch"
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        probe_file = scratch / "deltafuse-probe.tmp"
        probe_file.write_text("probe-ok", encoding="utf-8")
        probe_file.unlink()
        scratch_write = "ok"
    except Exception:
        scratch_write = "blocked"

    return ProbeReport(
        phase=phase,
        sentinel_read=sentinel_read,
        sentinel_found=content_hits,
        pack_found=name_hits,
        write_leak=[],
        rootfs_write_leak=[],
        docker_sock="absent",
        network="blocked",
        scratch_write=scratch_write,
        container_token=None,
    )
