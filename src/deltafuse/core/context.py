"""Context contract and budget validation engine for DeltaFuse Change packages."""

from __future__ import annotations
import fnmatch
import json
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence
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


# A03-01 / F-003: words-per-token upper bounds vs ornith/Qwen BPE (not chat completions).
WORD_FACTOR_EN = 1.3
WORD_FACTOR_CYRILLIC = 2.2
WORD_FACTOR_CODE = 2.7
WORD_FACTOR_YAML = 4.5  # 98/22 from A03-01; roadmap yaml×4 still undercounted
WORD_FACTOR_LOG = 4.8
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_CODE_SUFFIXES = {
    ".py",
    ".pyi",
    ".ps1",
    ".sh",
    ".bash",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".cs",
}
_YAML_SUFFIXES = {".yaml", ".yml", ".json"}
_LOG_SUFFIXES = {".log"}


def token_factor(text: str, path: Path | None = None) -> float:
    """Conservative tokens-per-word factor. Take the max of suffix and script factors."""
    factor = WORD_FACTOR_EN
    if path is not None:
        suffix = path.suffix.lower()
        if suffix in _YAML_SUFFIXES:
            factor = max(factor, WORD_FACTOR_YAML)
        elif suffix in _LOG_SUFFIXES:
            factor = max(factor, WORD_FACTOR_LOG)
        elif suffix in _CODE_SUFFIXES:
            factor = max(factor, WORD_FACTOR_CODE)
    if _CYRILLIC_RE.search(text):
        factor = max(factor, WORD_FACTOR_CYRILLIC)
    return factor


def try_endpoint_token_count(text: str) -> int | None:
    """Optional llama-server POST /tokenize. Never uses chat completions (Q-004)."""
    url = os.environ.get("DELTAFUSE_TOKENIZE_URL", "").strip()
    if not url:
        return None
    payload = json.dumps({"content": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    tokens = body.get("tokens") if isinstance(body, dict) else None
    if isinstance(tokens, list):
        return len(tokens)
    count = body.get("count") if isinstance(body, dict) else None
    if isinstance(count, int) and count >= 0:
        return count
    return None


def estimate_tokens(text: str, path: Path | None = None) -> int:
    """Upper-bound token estimate: optional /tokenize, else A03-01 coefficients."""
    counted = try_endpoint_token_count(text)
    if counted is not None:
        return counted
    words = len(text.split())
    if words == 0:
        return 0
    return math.ceil(words * token_factor(text, path))


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
            total += estimate_tokens(content, resolved)
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


DEFAULT_TASK_BUDGET = {"max_tokens": 16000, "max_files": 24}


def posix_relpath(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def matches_contract_globs(rel_path: str, globs: Sequence[str]) -> bool:
    """True if *rel_path* matches any PHASE_CONTRACTS glob (fnmatch, POSIX slashes)."""
    rel = posix_relpath(rel_path)
    for raw in globs:
        pattern = raw.replace("\\", "/")
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def phase_allowed_paths(phase: str, kind: str) -> list[str]:
    contract = PHASE_CONTRACTS.get(phase)
    if not contract:
        return []
    key = "allowed_read" if kind == "read" else "allowed_write"
    return list(contract.get(key) or [])


def task_write_globs() -> list[str]:
    """Declared task allowed_paths may be Target tests or Implement sources."""
    return phase_allowed_paths("target", "write") + phase_allowed_paths("implement", "write")


def validate_paths_against_globs(
    rel_paths: Iterable[str],
    globs: Sequence[str],
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    for raw in rel_paths:
        if not isinstance(raw, str) or not raw:
            continue
        if not matches_contract_globs(raw, globs):
            errors.append(f"{label}: '{raw}' is outside the phase contract")
    return errors


def path_is_listed(rel_path: str, listed: Sequence[str]) -> bool:
    rel = posix_relpath(rel_path)
    for item in listed:
        if not isinstance(item, str):
            continue
        listed_posix = posix_relpath(item)
        if rel == listed_posix or fnmatch.fnmatch(rel, listed_posix):
            return True
    return False


def validate_task_context_budget(
    context_budget: dict[str, Any],
    spec_refs: Sequence[Any],
    allowed_paths: Sequence[Any],
    repo_root: Path,
) -> list[str]:
    """Budget for a TASK: spec_refs must exist; allowed_paths may be future writes."""
    errors: list[str] = []
    max_files = context_budget.get("max_files")
    max_tokens = context_budget.get("max_tokens")
    root = repo_root.resolve()
    unique_declared: list[Path] = []
    unique_existing: list[Path] = []
    seen: set[Path] = set()

    def consider(raw: Any, *, must_exist: bool) -> None:
        if not isinstance(raw, str) or not raw:
            return
        file_part = raw.split("#", 1)[0]
        try:
            resolved = (root / file_part).resolve()
        except OSError as ex:
            errors.append(f"Invalid path '{file_part}': {ex}")
            return
        if not path_is_inside_repo(resolved, root):
            errors.append(
                f"Path traversal forbidden: '{file_part}' is outside repository root"
            )
            return
        if resolved in seen:
            return
        seen.add(resolved)
        unique_declared.append(resolved)
        if resolved.is_file():
            unique_existing.append(resolved)
        elif must_exist:
            errors.append(f"Referenced file does not exist: '{file_part}'")

    for sref in spec_refs:
        consider(sref, must_exist=True)
    for apath in allowed_paths:
        consider(apath, must_exist=False)

    if max_files is not None and len(unique_declared) > max_files:
        errors.append(
            f"Context budget exceeded: {len(unique_declared)} files loaded, "
            f"maximum allowed is {max_files}"
        )
    if max_tokens is not None:
        estimated = estimate_files_tokens(unique_existing)
        if estimated > max_tokens:
            errors.append(
                f"Context budget exceeded: estimated {estimated} tokens loaded, "
                f"maximum allowed is {max_tokens}"
            )
    return errors
