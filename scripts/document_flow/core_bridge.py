"""Adapter bridge for DeltaFuse Core state machine and write envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deltafuse.core.queue import (
    WorkItem,
    WorkQueue,
    build_halt,
    build_work_queue,
    load_product_root,
    queue_snapshot,
    select_next,
)
from deltafuse.core.leash import build_envelope, check_paths, load_baseline


@dataclass
class CoreObservation:
    schema_version: int
    step: str | None
    selected: dict[str, Any] | None
    ready: list[dict[str, Any]]
    blocked: list[dict[str, Any]]
    halt: dict[str, Any] | None
    envelope: dict[str, Any] | None
    raw_snapshot: dict[str, Any]


def observe_core(product_root: Path | str, *, step_filter: str | None = None) -> CoreObservation:
    """Observe real, pinned Core state/envelope for a given product root without inventing transitions."""
    root = load_product_root(product_root)
    queue = build_work_queue(root)
    selected = select_next(queue, step=step_filter)
    snapshot = queue_snapshot(queue, selected=selected, product_root=root)
    
    current_step = selected.step if selected else None
    
    return CoreObservation(
        schema_version=snapshot.get("schema_version", 1),
        step=current_step,
        selected=snapshot.get("selected"),
        ready=snapshot.get("ready", []),
        blocked=snapshot.get("blocked", []),
        halt=snapshot.get("halt"),
        envelope=snapshot.get("envelope"),
        raw_snapshot=snapshot,
    )


def validate_diff_in_envelope(product_root: Path | str, diff_paths: list[str], observation: CoreObservation) -> list[str]:
    """Validate that changed paths comply with the observed Core envelope."""
    root = load_product_root(product_root)
    baseline = load_baseline(root)
    envelope = observation.envelope
    return check_paths(diff_paths, envelope=envelope, baseline=baseline)
