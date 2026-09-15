"""Tool guard enforcing Core leash write envelopes and forbidden capabilities (J03-503)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from scripts.document_flow.canonical import content_hash
from scripts.document_flow.store import EvidenceStore


FORBIDDEN_TOOLS = frozenset({
    "browser",
    "search_web",
    "fetch_url",
    "read_url_content",
    "subagent",
    "invoke_subagent",
    "define_subagent",
    "manage_subagents",
    "schedule",
    "generate_image",
    "ask_question",
})

FORBIDDEN_COMMAND_PATTERNS = [
    "curl ",
    "wget ",
    "git push",
    "git pull",
    "git clone",
    "git remote",
    "nc ",
    "netcat ",
    "ncat ",
]


class ToolGuardError(PermissionError):
    """Raised when an operation violates tool or path boundaries."""


@dataclass(frozen=True)
class ToolValidationResult:
    allowed: bool
    reason: str | None
    boundary_type: str
    target_path: str | None = None


def match_globs(relative_path: str, globs: list[str] | tuple[str, ...]) -> bool:
    """Match relative POSIX path against leash glob patterns."""
    pure = PurePosixPath(relative_path).as_posix()
    for pattern in globs:
        if fnmatch.fnmatch(pure, pattern):
            return True
        # Also check directory prefix match if glob ends with /**
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if pure == prefix or pure.startswith(prefix + "/"):
                return True
    return False


def validate_file_action(
    product_root: Path | str,
    action: str,  # 'read' | 'write' | 'edit' | 'delete'
    target_path: Path | str,
    envelope: Mapping[str, Any] | None,
) -> ToolValidationResult:
    """Validate file action against Core envelope and prevent escape via symlinks."""
    root = Path(product_root).resolve()
    target = Path(target_path)
    
    if not target.is_absolute():
        target = (root / target).resolve()
    else:
        target = target.resolve()

    try:
        rel = target.relative_to(root).as_posix()
    except ValueError:
        return ToolValidationResult(
            allowed=False,
            reason="path escapes product root boundary",
            boundary_type="file",
            target_path=str(target_path),
        )

    # If action is read, check read allowlist if envelope present
    if action == "read":
        # Always allow reading framework and product files unless strictly restricted
        return ToolValidationResult(allowed=True, reason=None, boundary_type="file", target_path=rel)

    # For write / edit / delete:
    if envelope is None:
        # Null envelope strictly forbids product writes
        exempt_prefixes = ("docs/intake/", "AGENTS.md", ".deltafuse/")
        if any(rel == p or rel.startswith(p) for p in exempt_prefixes):
            return ToolValidationResult(allowed=True, reason=None, boundary_type="file", target_path=rel)
        return ToolValidationResult(
            allowed=False,
            reason="null write envelope; product writes are forbidden",
            boundary_type="file",
            target_path=rel,
        )

    write_globs = envelope.get("write", [])
    if not match_globs(rel, write_globs):
        return ToolValidationResult(
            allowed=False,
            reason=f"path {rel} not in envelope write globs",
            boundary_type="file",
            target_path=rel,
        )

    return ToolValidationResult(allowed=True, reason=None, boundary_type="file", target_path=rel)


def validate_tool_invocation(
    tool_name: str,
    params: Mapping[str, Any],
    envelope: Mapping[str, Any] | None,
    product_root: Path | str,
) -> ToolValidationResult:
    """Validate tool name and arguments against forbidden list and leash envelope."""
    norm_name = tool_name.lower().strip()
    if norm_name in FORBIDDEN_TOOLS:
        return ToolValidationResult(
            allowed=False,
            reason=f"forbidden tool {norm_name} is disabled by benchmark policy",
            boundary_type="model",
        )

    if norm_name in ("write_to_file", "replace_file_content", "edit_file"):
        path = params.get("TargetFile") or params.get("path") or params.get("file")
        if not path:
            return ToolValidationResult(allowed=False, reason="missing target path in file write tool", boundary_type="file")
        return validate_file_action(product_root, "write", path, envelope)

    if norm_name in ("run_command", "bash", "exec"):
        cmd = params.get("CommandLine") or params.get("command") or ""
        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            if pattern in cmd:
                return ToolValidationResult(
                    allowed=False,
                    reason=f"forbidden command pattern detected: {pattern.strip()}",
                    boundary_type="command",
                )

    return ToolValidationResult(allowed=True, reason=None, boundary_type="model")
