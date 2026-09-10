"""Append-only bench journal in the worker sandbox. Judge-only to read."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.fsm import find_repo_root

JOURNAL_REL = ".deltafuse/bench-journal.yaml"

GATE_STAGE = {
    "intake": "intake",
    "analyzed": "analyze",
    "specified": "specify",
    "decomposed": "decompose",
    "targeting": "declare",
    "implemented": "implement",
    "converged": "verify",
}


def bench_product_root(start: Path | str) -> Path | None:
    root = find_repo_root(Path(start))
    if (root / ".deltafuse" / "bench.yaml").is_file():
        return root
    return None


def journal_path(product: Path) -> Path:
    return product / JOURNAL_REL


def record_event(start: Path | str, **event: Any) -> None:
    """Best-effort append. Must not fail the Worker command."""
    try:
        product = bench_product_root(start)
        if product is None:
            return
        path = journal_path(product)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": 1, "events": []}
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict) and isinstance(loaded.get("events"), list):
                data = loaded
            elif isinstance(loaded, list):
                data["events"] = loaded
        row = {k: v for k, v in event.items() if v is not None}
        row["at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = data.setdefault("events", [])
        if not isinstance(events, list):
            events = []
            data["events"] = events
        events.append(row)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except Exception:
        return


def load_events(product: Path) -> list[dict[str, Any]]:
    path = journal_path(product)
    if not path.is_file():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(loaded, list):
        return [e for e in loaded if isinstance(e, dict)]
    if isinstance(loaded, dict) and isinstance(loaded.get("events"), list):
        return [e for e in loaded["events"] if isinstance(e, dict)]
    return []


def summarize_journal(events: list[dict[str, Any]]) -> dict[str, Any]:
    gates: dict[str, dict[str, int]] = {}
    evidence = {"attempts": 0, "failures": 0}
    coverage = {"attempts": 0, "failures": 0}
    for ev in events:
        cmd = ev.get("cmd")
        ok = bool(ev.get("ok"))
        if cmd == "check-gate":
            gate = str(ev.get("gate") or "unknown")
            row = gates.setdefault(gate, {"attempts": 0, "failures": 0})
            row["attempts"] += 1
            if not ok:
                row["failures"] += 1
        elif cmd == "evidence":
            evidence["attempts"] += 1
            if not ok:
                evidence["failures"] += 1
        elif cmd == "coverage":
            coverage["attempts"] += 1
            if not ok:
                coverage["failures"] += 1
    by_stage: dict[str, dict[str, int]] = {}
    for gate, row in gates.items():
        stage = GATE_STAGE.get(gate, gate)
        slot = by_stage.setdefault(stage, {"attempts": 0, "retries": 0})
        slot["attempts"] += row["attempts"]
        slot["retries"] += row["failures"]
    gate_attempts = sum(r["attempts"] for r in gates.values())
    gate_retries = sum(r["failures"] for r in gates.values())
    return {
        "observed": bool(events),
        "check_gate": gates,
        "by_stage": by_stage,
        "evidence": evidence,
        "coverage": coverage,
        "gate_attempts": gate_attempts,
        "gate_retries": gate_retries,
        "evidence_retries": evidence["failures"],
        "coverage_retries": coverage["failures"],
        "retries": gate_retries + evidence["failures"] + coverage["failures"],
    }
