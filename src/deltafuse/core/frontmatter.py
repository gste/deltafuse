"""Parser for Markdown files with YAML frontmatter."""

from __future__ import annotations
import re
from typing import Any
import yaml


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
        raise FrontmatterParseError(f"YAML parsing error in frontmatter: {e}") from e
