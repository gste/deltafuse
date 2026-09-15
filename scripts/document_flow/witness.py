"""Typed witness parser and validator for DeltaFuse benchmark obligations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


VACOUS_PATTERNS = [
    r"^\s*true\s*==\s*true\s*$",
    r"^\s*1\s*==\s*1\s*$",
    r"^\s*pass\s*$",
    r"^\s*always_true\s*$",
    r"^\s*$",
]

CONTRADICTORY_PATTERNS = [
    r"status\s*==\s*['\"]approved['\"].*status\s*==\s*['\"]rejected['\"]",
    r"status\s*==\s*['\"]rejected['\"].*status\s*==\s*['\"]approved['\"]",
]


@dataclass(frozen=True)
class WitnessEntry:
    obligation_id: str
    source_anchor: str
    predicate: str | None = None
    target_capability: str | None = None


@dataclass(frozen=True)
class WitnessValidationResult:
    valid: bool
    entries: list[WitnessEntry]
    errors: list[str]


def parse_witness_block(text: str) -> list[dict[str, Any]]:
    """Parse JSON array from ```j03-obligations ... ``` fenced block."""
    match = re.search(r"```j03-obligations\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def validate_witnesses(text: str) -> WitnessValidationResult:
    """Validate witness entries and reject vacuous, tautological, or contradictory predicates."""
    raw_entries = parse_witness_block(text)
    if not raw_entries:
        return WitnessValidationResult(valid=False, entries=[], errors=["No valid j03-obligations block found"])
    
    entries: list[WitnessEntry] = []
    errors: list[str] = []
    
    for idx, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            errors.append(f"Entry {idx} is not an object")
            continue
        obl_id = raw.get("obligation_id")
        if not obl_id or not re.match(r"^J03-OBL-[0-9]{3}$", str(obl_id)):
            errors.append(f"Entry {idx} has invalid obligation_id: {obl_id}")
            continue
        anchor = raw.get("source_anchor", "")
        predicate = raw.get("predicate")
        
        if predicate is not None:
            pred_str = str(predicate).strip().lower()
            for vac_pat in VACOUS_PATTERNS:
                if re.match(vac_pat, pred_str):
                    errors.append(f"Obligation {obl_id} contains vacuous/tautological predicate: {predicate}")
            for con_pat in CONTRADICTORY_PATTERNS:
                if re.search(con_pat, pred_str, re.IGNORECASE):
                    errors.append(f"Obligation {obl_id} contains contradictory predicate: {predicate}")
        
        entries.append(WitnessEntry(
            obligation_id=obl_id,
            source_anchor=anchor,
            predicate=predicate,
            target_capability=raw.get("target_capability"),
        ))
        
    return WitnessValidationResult(
        valid=len(errors) == 0 and len(entries) > 0,
        entries=entries,
        errors=errors,
    )
