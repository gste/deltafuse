"""Machine contract for the seven lifecycle steps (kernel, no LLM)."""

from __future__ import annotations

from deltafuse.core.context import PHASE_CONTRACTS

STEP_CONTRACTS: dict[str, dict[str, str]] = {
    "intake": {"skill": "intake", "gate": "intake", "phase": "intake"},
    "analyze": {"skill": "analyze", "gate": "analyzed", "phase": "analyze"},
    "specify": {"skill": "specify", "gate": "specified", "phase": "specify"},
    "decompose": {"skill": "decompose", "gate": "decomposed", "phase": "decompose"},
    "declare": {"skill": "declare", "gate": "targeting", "phase": "declare"},
    "implement": {"skill": "implement", "gate": "implemented", "phase": "implement"},
    "verify": {"skill": "verify", "gate": "converged", "phase": "verify"},
}

STEP_ORDER = tuple(STEP_CONTRACTS.keys())

THINKER_LLM_MARKERS = (
    "binds the Thinker to an LLM",
    "not the Process",
    "deltafuse next",
    "Do not auto-accept Decisions",
    "Do not choose the next slash command yourself",
)


def step_names() -> tuple[str, ...]:
    return STEP_ORDER


def validate_step_contracts() -> list[str]:
    """Return mismatches between STEP_CONTRACTS and PHASE_CONTRACTS."""
    errors: list[str] = []
    if set(STEP_CONTRACTS) != set(PHASE_CONTRACTS):
        errors.append(
            "STEP_CONTRACTS keys must match PHASE_CONTRACTS: "
            f"{sorted(STEP_CONTRACTS)} vs {sorted(PHASE_CONTRACTS)}"
        )
    for name, spec in STEP_CONTRACTS.items():
        if spec.get("phase") != name:
            errors.append(f"STEP_CONTRACTS[{name!r}] phase must be {name!r}")
        if name not in PHASE_CONTRACTS:
            errors.append(f"STEP_CONTRACTS[{name!r}] missing PHASE_CONTRACTS entry")
    return errors
