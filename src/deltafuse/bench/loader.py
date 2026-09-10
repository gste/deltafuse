"""Load bench case packs from process/bench/cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from deltafuse.bench import BenchError, cases_root


STAGES = (
    "intake",
    "analyze",
    "specify",
    "decompose",
    "declare",
    "implement",
    "verify",
)


def list_cases(root: Path | None = None) -> list[str]:
    base = cases_root(root)
    if not base.is_dir():
        return []
    return sorted(
        p.name for p in base.iterdir() if p.is_dir() and (p / "case.yaml").is_file()
    )


def load_case(case_id: str, root: Path | None = None) -> dict[str, Any]:
    case_dir = cases_root(root) / case_id
    case_file = case_dir / "case.yaml"
    if not case_file.is_file():
        known = ", ".join(list_cases(root)) or "(none)"
        raise BenchError(f"Unknown bench case {case_id!r}. Known: {known}")
    data = yaml.safe_load(case_file.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BenchError(f"{case_file} must be a mapping")
    data["id"] = str(data.get("id") or case_id)
    data["dir"] = case_dir
    stages = data.get("stages") or list(STAGES)
    if not isinstance(stages, list) or not stages:
        raise BenchError(f"{case_id}: stages must be a non-empty list")
    data["stages"] = [str(s) for s in stages]
    return data
