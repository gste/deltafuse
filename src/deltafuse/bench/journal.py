"""Append-only Core journal in a bench sandbox. Judge reads; Workers are not asked to write it."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.fsm import find_repo_root

JOURNAL_JSONL = ".deltafuse/bench-journal.jsonl"
JOURNAL_YAML = ".deltafuse/bench-journal.yaml"
EVENT_VERSION = 1
MAX_ERRORS = 12
MAX_ERROR_CHARS = 240

GATE_STAGE = {
    "intake": "intake",
    "analyzed": "analyze",
    "specified": "specify",
    "decomposed": "decompose",
    "declaring": "declare",
    "implemented": "implement",
    "converged": "verify",
}

WORKER_CMDS = (
    "next",
    "check-gate",
    "evidence",
    "coverage",
    "archive",
    "validate",
    "validate-layout",
    "lint-context",
    "board",
    "leash",
)


def bench_product_root(start: Path | str) -> Path | None:
    root = find_repo_root(Path(start))
    if (root / ".deltafuse" / "bench.yaml").is_file():
        return root
    return None


def journal_path(product: Path) -> Path:
    return product / JOURNAL_JSONL


def clip_errors(errors: list[Any] | None) -> list[str]:
    out: list[str] = []
    for raw in list(errors or [])[:MAX_ERRORS]:
        text = " ".join(str(raw).split())
        if not text:
            continue
        out.append(text[:MAX_ERROR_CHARS])
    return out


def _change_fields(start: Path) -> dict[str, str]:
    path = start / "change.yaml" if start.is_dir() else start
    if path.name != "change.yaml" or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    row: dict[str, str] = {}
    cid = data.get("id")
    status = data.get("status")
    if isinstance(cid, str) and cid:
        row["change"] = cid
    if isinstance(status, str) and status:
        row["status"] = status
    return row


def _next_seq(path: Path) -> int:
    if not path.is_file():
        return 1
    seq = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        seq += 1
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("seq"), int):
            seq = max(seq, row["seq"])
    return seq + 1


def record_event(start: Path | str, **event: Any) -> None:
    """Best-effort append. Must not fail the Worker command."""
    try:
        product = bench_product_root(start)
        if product is None:
            return
        path = journal_path(product)
        path.parent.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {
            "v": EVENT_VERSION,
            "seq": _next_seq(path),
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        row.update(_change_fields(Path(start)))
        extra_errors: list[str] | None = None
        n_errors: int | None = None
        for key, value in event.items():
            if value is None:
                continue
            if key == "errors":
                extra_errors = clip_errors(value if isinstance(value, list) else [value])
                continue
            if key == "n_errors":
                n_errors = int(value)
                continue
            row[key] = value
        if extra_errors is not None:
            row["errors"] = extra_errors
            row["n_errors"] = n_errors if n_errors is not None else len(extra_errors)
        elif n_errors is not None:
            row["n_errors"] = n_errors
        if "ok" in row:
            row["ok"] = bool(row["ok"])
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        return


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def _load_yaml_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(loaded, list):
        return [row for row in loaded if isinstance(row, dict)]
    if isinstance(loaded, dict) and isinstance(loaded.get("events"), list):
        return [row for row in loaded["events"] if isinstance(row, dict)]
    return []


def load_events(product: Path) -> list[dict[str, Any]]:
    jsonl = _load_jsonl(product / JOURNAL_JSONL)
    if jsonl:
        return jsonl
    return _load_yaml_events(product / JOURNAL_YAML)


def _cycle_key(event: dict[str, Any]) -> tuple[str, str]:
    cmd = str(event.get("cmd") or "")
    if cmd == "check-gate":
        return cmd, str(event.get("gate") or "")
    if cmd == "evidence":
        return cmd, str(event.get("phase") or "")
    return cmd, ""


# A gate that is only waiting for the human's verdict. The Worker cannot act
# on it: counting the refusal as a retry blamed the model for the queue's own
# halt (M01 on qwen/qwen3.8-27b, 2026-09-22 - two of its three retries).
HUMAN_WAIT_MARKERS = (
    "accepted via deltafuse decide",
    "without deltafuse decide",
    "is blocked-on-decision",
)


def waits_for_human(event: dict[str, Any]) -> bool:
    """True when every error of a refused gate is the human's verdict."""
    if str(event.get("cmd") or "") != "check-gate" or event.get("ok"):
        return False
    errors = [str(e) for e in (event.get("errors") or [])]
    if not errors or len(errors) != int(event.get("n_errors") or len(errors)):
        return False  # clipped list: some error may be the Worker's
    return all(any(marker in error for marker in HUMAN_WAIT_MARKERS) for error in errors)


def collect_attempts(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll Core journal lines into command counts and gate/evidence cycles."""
    commands: dict[str, dict[str, int]] = {
        cmd: {"n": 0, "ok": 0, "fail": 0} for cmd in WORKER_CMDS
    }
    gates: dict[str, dict[str, Any]] = {}
    cycles: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            cycles.append(current)
            current = None

    human_waits = 0
    for event in events:
        cmd = str(event.get("cmd") or "unknown")
        ok = bool(event.get("ok"))
        if waits_for_human(event):
            # Not an attempt and not a retry: the Worker asked a gate that only
            # the human can close, and the skills tell it to stop there.
            human_waits += 1
            continue
        slot = commands.setdefault(cmd, {"n": 0, "ok": 0, "fail": 0})
        slot["n"] += 1
        slot["ok" if ok else "fail"] += 1
        if cmd == "check-gate":
            gate = str(event.get("gate") or "unknown")
            row = gates.setdefault(
                gate, {"n": 0, "ok": 0, "fail": 0, "last_ok": False, "redundant": 0}
            )
            row["n"] += 1
            # DF3-009 / C-01: querying an already-passed gate is not forward
            # progress. Count it as a redundant retry so spam lowers, never
            # raises, the process score.
            if ok and row["last_ok"]:
                row["redundant"] += 1
            else:
                row["ok" if ok else "fail"] += 1
                row["last_ok"] = ok
        key = _cycle_key(event)
        if current is not None and (current["cmd"], current.get("key") or "") != key:
            flush()
        if current is None:
            current = {
                "cmd": key[0],
                "key": key[1],
                "n": 0,
                "fail": 0,
                "ok": False,
                "seq": [],
            }
            if key[0] == "check-gate":
                current["gate"] = key[1]
            elif key[0] == "evidence":
                current["phase"] = key[1]
        current["n"] += 1
        current["seq"].append(event.get("seq"))
        if ok:
            current["ok"] = True
            flush()
        else:
            current["fail"] += 1
    flush()
    for cycle in cycles:
        cycle.pop("key", None)
        cycle["seq"] = [item for item in cycle["seq"] if item is not None]
    gate_fail = sum(int(row["fail"]) for row in gates.values())
    gate_fail += sum(int(row.get("redundant") or 0) for row in gates.values())
    evidence_fail = int((commands.get("evidence") or {}).get("fail") or 0)
    coverage_fail = int((commands.get("coverage") or {}).get("fail") or 0)
    return {
        "schema_version": 1,
        "source": "core",
        "events": len(events),
        "commands": commands,
        "gates": gates,
        "cycles": cycles,
        "human_waits": human_waits,
        "retries": {
            "check_gate": gate_fail,
            "evidence": evidence_fail,
            "coverage": coverage_fail,
            "total": gate_fail + evidence_fail + coverage_fail,
        },
    }


def summarize_journal(events: list[dict[str, Any]]) -> dict[str, Any]:
    collected = collect_attempts(events)
    gates = collected.get("gates") or {}
    by_stage: dict[str, dict[str, int]] = {}
    for gate, row in gates.items():
        stage = GATE_STAGE.get(str(gate), str(gate))
        slot = by_stage.setdefault(stage, {"attempts": 0, "retries": 0})
        slot["attempts"] += int(row.get("n") or 0) - int(row.get("redundant") or 0)
        slot["retries"] += int(row.get("fail") or 0) + int(row.get("redundant") or 0)
    retries = collected.get("retries") or {}
    return {
        "observed": bool(events),
        # Gate refusals that only wait for the human: reported, never charged
        # to the model.
        "human_waits": int(collected.get("human_waits") or 0),
        "check_gate": {
            name: {"attempts": int(row.get("n") or 0), "failures": int(row.get("fail") or 0)}
            for name, row in gates.items()
        },
        "by_stage": by_stage,
        "evidence": {
            "attempts": int((collected.get("commands") or {}).get("evidence", {}).get("n") or 0),
            "failures": int(retries.get("evidence") or 0),
        },
        "coverage": {
            "attempts": int((collected.get("commands") or {}).get("coverage", {}).get("n") or 0),
            "failures": int(retries.get("coverage") or 0),
        },
        "gate_attempts": sum(int(row.get("n") or 0) for row in gates.values()),
        "gate_retries": int(retries.get("check_gate") or 0),
        "evidence_retries": int(retries.get("evidence") or 0),
        "coverage_retries": int(retries.get("coverage") or 0),
        "retries": int(retries.get("total") or 0),
        "commands": collected.get("commands") or {},
        "cycles": collected.get("cycles") or [],
    }
