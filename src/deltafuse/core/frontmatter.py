"""Parser for Markdown files with YAML frontmatter."""

from __future__ import annotations
import re
from typing import Any
import yaml


def yaml_error_hint(error: Exception) -> str:
    """A fix for the YAML mistake Workers make most, appended to a parse error.

    q0 run M03 20260921T212331Z: `summary: Backward compatible: ...` failed to
    parse twelve times in a row; PyYAML says "mapping values are not allowed
    here", which does not say to quote the value.
    """
    if "mapping values are not allowed" in str(error):
        return (
            " - a value that contains ': ' must be quoted, e.g. "
            'summary: "Backward compatible: callers keep working"'
        )
    return ""


class FrontmatterParseError(Exception):
    """Raised when Markdown frontmatter parsing fails."""
    pass


FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parses YAML frontmatter from Markdown text.
    
    Returns:
        (metadata_dict, markdown_body)
    
    Raises:
        FrontmatterParseError: if YAML is malformed or delimiters are missing.
    """
    match = FRONTMATTER_PATTERN.match(content.strip())
    if not match:
        raise FrontmatterParseError("File does not contain valid YAML frontmatter enclosed by '---' delimiters.")
    
    yaml_text, body = match.groups()
    try:
        data = yaml.safe_load(yaml_text) or {}
        if not isinstance(data, dict):
            raise FrontmatterParseError(f"Frontmatter YAML must be a mapping/dict, got {type(data).__name__}")
        return data, body
    except yaml.YAMLError as e:
        raise FrontmatterParseError(f"YAML parsing error in frontmatter: {e}{yaml_error_hint(e)}") from e


def replace_frontmatter(content: str, updates: dict[str, Any]) -> str:
    """Return Markdown with selected frontmatter keys replaced. Preserves body."""
    meta, body = parse_frontmatter(content)
    meta.update(updates)
    dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip()
    body_out = body if body.startswith("\n") or body == "" else "\n" + body
    if not body_out.endswith("\n"):
        body_out += "\n"
    return f"---\n{dumped}\n---{body_out}"
