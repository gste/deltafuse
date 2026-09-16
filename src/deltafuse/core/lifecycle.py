"""Canonical lifecycle — the single ordered contract (AGENTS.md vocabulary).

`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`

Every consumer (bench pack, qualification T2, validators) must import this
tuple instead of restating stage names; the qualification T2 gate compares
exact equality of names, order and completion.
"""

from __future__ import annotations

LIFECYCLE: tuple[str, ...] = (
    "intake",
    "analyze",
    "specify",
    "decompose",
    "declare",
    "implement",
    "verify",
)
