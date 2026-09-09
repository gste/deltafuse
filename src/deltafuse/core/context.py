"""Context contract and budget validation engine for DeltaFuse Change packages."""

from __future__ import annotations
import math
from pathlib import Path
from typing import Any
from deltafuse.core.integrity import path_is_inside_repo


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
    """Sum estimated tokens over unique existing files (duplicates counted once)."""
    total = 0
    seen: set[Path] = set()
    for f in files:
        try:
            resolved = f.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            content = resolved.read_text(encoding="utf-8", errors="ignore")
            total += estimate_tokens(content)
        except OSError:
            continue
    return total


def validate_context_budget(
    context_budget: dict[str, Any],
    files: list[Path],
    repo_root: Path | None = None,
) -> list[str]:
    """Validates that loaded files do not exceed max_tokens and max_files constraints.

    Missing paths and paths outside *repo_root* are errors, not silent skips.
    Duplicate paths are counted once for budget limits.
    """
    errors: list[str] = []
    max_files = context_budget.get("max_files")
    max_tokens = context_budget.get("max_tokens")
    root = repo_root.resolve() if repo_root is not None else None
    unique_files: list[Path] = []
    seen: set[Path] = set()

    for f in files:
        try:
            resolved = f.resolve()
        except OSError as ex:
            errors.append(f"Invalid path '{f}': {ex}")
            continue
        if root is not None and not path_is_inside_repo(resolved, root):
            errors.append(
                f"Path traversal forbidden: '{f}' is outside repository root"
            )
            continue
        if not resolved.is_file():
            errors.append(f"Referenced file does not exist: '{f}'")
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_files.append(resolved)

    if max_files is not None and len(unique_files) > max_files:
        errors.append(
            f"Context budget exceeded: {len(unique_files)} files loaded, "
            f"maximum allowed is {max_files}"
        )

    if max_tokens is not None:
        estimated = estimate_files_tokens(unique_files)
        if estimated > max_tokens:
            errors.append(
                f"Context budget exceeded: estimated {estimated} tokens loaded, "
                f"maximum allowed is {max_tokens}"
            )

    return errors
