"""Context contract and budget validation engine for DeltaFuse Change packages."""

from __future__ import annotations
import math
from pathlib import Path
from typing import Any


class ContextLinterError(Exception):
    """Raised when context contract or budget invariants are violated."""
    pass


PHASE_CONTRACTS: dict[str, dict[str, list[str]]] = {
    "intake": {
        "allowed_read": ["docs/intake/**", "docs/changes/**"],
        "allowed_write": ["docs/changes/*/request.md", "docs/changes/*/change.yaml"],
    },
    "analyze": {
        "allowed_read": [
            "docs/changes/*/request.md",
            "docs/changes/*/change.yaml",
            "docs/spec/**",
            "docs/decisions/**",
            ".deltafuse/**",
        ],
        "allowed_write": [
            "docs/changes/*/routing.yaml",
            "docs/changes/*/analysis.md",
            "docs/changes/*/slices/**",
            "docs/changes/*/coverage.yaml",
            "docs/changes/*/change.yaml",
        ],
    },
    "specify": {
        "allowed_read": [
            "docs/changes/*/slices/**",
            "docs/changes/*/routing.yaml",
            "docs/spec/**",
            "docs/decisions/**",
        ],
        "allowed_write": [
            "docs/spec/**",
            "docs/changes/*/spec-delta.md",
            "docs/changes/*/change.yaml",
        ],
    },
    "decompose": {
        "allowed_read": [
            "docs/changes/*/slices/**",
            "docs/changes/*/spec-delta.md",
            "docs/spec/**",
        ],
        "allowed_write": [
            "docs/changes/*/tasks/**",
            "docs/changes/*/coverage.yaml",
            "docs/changes/*/change.yaml",
        ],
    },
    "target": {
        "allowed_read": [
            "docs/changes/*/tasks/*",
            "docs/spec/**",
            "tests/**",
        ],
        "allowed_write": [
            "tests/**",
            "docs/changes/*/evidence/red/**",
            "docs/changes/*/coverage.yaml",
            "docs/changes/*/change.yaml",
        ],
    },
    "implement": {
        "allowed_read": [
            "docs/changes/*/tasks/*",
            "tests/**",
            "src/**",
        ],
        "allowed_write": [
            "src/**",
            "tests/**",
            "docs/changes/*/evidence/green/**",
            "docs/changes/*/evidence/regression/**",
            "docs/changes/*/coverage.yaml",
            "docs/changes/*/change.yaml",
            "docs/changes/*/tasks/*",
        ],
    },
    "verify": {
        "allowed_read": [
            "docs/changes/**",
            "docs/spec/**",
            "tests/**",
        ],
        "allowed_write": [
            "docs/changes/*/verification.md",
            "docs/changes/*/evidence/verification/**",
            "docs/changes/*/coverage.yaml",
            "docs/changes/*/change.yaml",
            "docs/changes/*/tasks/*",
        ],
    },
}


def estimate_tokens(text: str) -> int:
    """Estimates token count using the standard word heuristic (1 word ≈ 1.3 tokens)."""
    words = text.split()
    return math.ceil(len(words) * 1.3)


def estimate_files_tokens(files: list[Path]) -> int:
    """Calculates total estimated tokens across a list of readable text files."""
    total = 0
    for f in files:
        if f.is_file():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                total += estimate_tokens(content)
            except Exception:
                pass
    return total


def validate_context_budget(
    context_budget: dict[str, Any],
    files: list[Path],
) -> list[str]:
    """Validates that loaded files do not exceed max_tokens and max_files constraints."""
    errors: list[str] = []
    max_files = context_budget.get("max_files")
    max_tokens = context_budget.get("max_tokens")

    if max_files is not None and len(files) > max_files:
        errors.append(
            f"Context budget exceeded: {len(files)} files loaded, maximum allowed is {max_files}"
        )

    if max_tokens is not None:
        estimated = estimate_files_tokens(files)
        if estimated > max_tokens:
            errors.append(
                f"Context budget exceeded: estimated {estimated} tokens loaded, maximum allowed is {max_tokens}"
            )

    return errors
