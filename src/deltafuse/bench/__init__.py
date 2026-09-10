"""Agent-agnostic Worker bench: Core prepares a product and scores the disk. No LLM."""

from __future__ import annotations

from pathlib import Path


def framework_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def cases_root(root: Path | None = None) -> Path:
    return (root or framework_root()) / "process" / "bench" / "cases"


class BenchError(Exception):
    pass
