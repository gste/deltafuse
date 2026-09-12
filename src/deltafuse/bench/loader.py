"""Load bench case packs. Judge pack is not the worker sandbox."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from deltafuse.bench import BenchError, framework_root
from deltafuse.core.lifecycle import LIFECYCLE

# QF-014: the bench pack reuses the canonical lifecycle contract verbatim.
STAGES = LIFECYCLE

PACK_ENV = "DELTAFUSE_BENCH_PACK"


def normalize_pack(path: Path | str) -> Path:
    """Return the cases/ directory for a pack, framework root, or cases root."""
    pack = Path(path).resolve()
    if not pack.exists():
        raise BenchError(f"Bench pack not found: {pack}")
    if (pack / "process" / "bench" / "cases").is_dir():
        return pack / "process" / "bench" / "cases"
    if (pack / "bench" / "cases").is_dir():
        return pack / "bench" / "cases"
    if (pack / "cases").is_dir() and any((pack / "cases").glob("*/case.yaml")):
        return pack / "cases"
    if (pack / "case.yaml").is_file():
        return pack.parent
    if pack.is_dir() and any(
        child.is_dir() and (child / "case.yaml").is_file() for child in pack.iterdir()
    ):
        return pack
    raise BenchError(
        f"{pack} is not a bench pack (expected process/bench/cases, cases/, or a case directory)"
    )


def resolve_cases_root(
    explicit: Path | str | None = None,
    *,
    default_framework: bool = False,
) -> Path:
    """Locate cases/. Score must pass a pack; init may fall back to this checkout."""
    raw = explicit if explicit not in (None, "") else os.environ.get(PACK_ENV)
    if raw:
        return normalize_pack(raw)
    if default_framework:
        return normalize_pack(framework_root())
    raise BenchError(
        "Judge pack required. Pass --pack or set "
        f"{PACK_ENV}. Do not score from the worker sandbox."
    )


def cases_root(root: Path | None = None) -> Path:
    if root is None:
        return resolve_cases_root(default_framework=True)
    return normalize_pack(root)


def list_cases(root: Path | None = None) -> list[str]:
    base = cases_root(root)
    if not base.is_dir():
        return []
    return sorted(
        p.name for p in base.iterdir() if p.is_dir() and (p / "case.yaml").is_file()
    )


def load_case(
    case_id: str,
    root: Path | None = None,
    *,
    oracle: bool = False,
) -> dict[str, Any]:
    case_dir = cases_root(root) / case_id
    case_file = case_dir / "case.yaml"
    if not case_file.is_file():
        known = ", ".join(list_cases(root)) or "(none)"
        raise BenchError(f"Unknown bench case {case_id!r}. Known: {known}")
    data = yaml.safe_load(case_file.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BenchError(f"{case_file} must be a mapping")
    if oracle:
        oracle_file = case_dir / "oracle.yaml"
        if not oracle_file.is_file():
            raise BenchError(f"{case_id}: oracle.yaml missing from the judge pack")
        extra = yaml.safe_load(oracle_file.read_text(encoding="utf-8")) or {}
        if not isinstance(extra, dict):
            raise BenchError(f"{oracle_file} must be a mapping")
        # V3-FIX-007: Worker-visible case.yaml fields are single-source; the
        # oracle may not redeclare (and silently override) them.
        for reserved in ("score_mix", "stages", "adversarial", "defense_checks", "target_capabilities"):
            if reserved in extra:
                raise BenchError(
                    f"{case_id}: {reserved} belongs to case.yaml only; "
                    "oracle.yaml must not override Worker-visible case fields"
                )
        data.update(extra)
    data["id"] = str(data.get("id") or case_id)
    data["dir"] = case_dir
    stages = data.get("stages") or list(STAGES)
    if not isinstance(stages, list) or not stages:
        raise BenchError(f"{case_id}: stages must be a non-empty list")
    data["stages"] = [str(s) for s in stages]
    return data


def assert_scorecard_outside_sandbox(out_file: Path | str, product: Path) -> None:
    dest = Path(out_file).resolve()
    root = product.resolve()
    if dest == root or dest.is_relative_to(root):
        raise BenchError(
            f"Refuse to write scorecard {dest} inside the worker sandbox {root}"
        )
