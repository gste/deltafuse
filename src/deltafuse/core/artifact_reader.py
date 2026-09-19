"""Strict bounded artifact and YAML readers for DeltaFuse (AW-02).

Enforces strict YAML/JSON parser rules: duplicate key rejection, non-finite float
rejection, custom tag rejection, size/depth bounds, BOM/CRLF detection, and byte-exact
body preservation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any
import yaml


class ArtifactReaderError(Exception):
    """Raised when strict artifact or YAML reading fails."""

    def __init__(self, message: str, *, code: str = "parse_error", line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.line = line
        self.column = column


def strict_parse_json(
    content: str | bytes,
    *,
    max_bytes: int = 1024 * 1024,
    max_depth: int = 100,
) -> dict[str, Any]:
    """Strictly parse JSON string or bytes into a Python dictionary.

    Enforces strict rules:
    - Bytes bound checked before reading/decoding
    - UTF-8 validation (rejects invalid surrogates/encoding)
    - Rejects duplicate keys at EVERY depth level
    - Rejects non-finite numbers (NaN, Infinity, -Infinity)
    - Rejects nesting depths exceeding max_depth
    - Ensures top-level JSON value is a mapping/dict (JSON object)
    """
    if isinstance(content, bytes):
        if len(content) > max_bytes:
            raise ArtifactReaderError(
                f"JSON payload size ({len(content)} bytes) exceeds max bytes limit ({max_bytes})",
                code="exceeds_max_bytes",
            )
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as ex:
            raise ArtifactReaderError(
                f"Invalid UTF-8 encoding in JSON payload: {ex}",
                code="invalid_encoding",
            ) from ex
    else:
        try:
            raw_bytes = content.encode("utf-8", errors="strict")
        except UnicodeEncodeError as ex:
            raise ArtifactReaderError(
                f"Invalid Unicode in JSON payload: {ex}",
                code="invalid_encoding",
            ) from ex
        if len(raw_bytes) > max_bytes:
            raise ArtifactReaderError(
                f"JSON payload size ({len(raw_bytes)} bytes) exceeds max bytes limit ({max_bytes})",
                code="exceeds_max_bytes",
            )
        text = content

    def _reject_constant(val: str):
        raise ArtifactReaderError(
            f"non-finite number '{val}' is not permitted in JSON input",
            code="non_finite_float",
        )

    def _strict_pairs_hook(pairs):
        mapping: dict[str, Any] = {}
        for key, value in pairs:
            if not isinstance(key, str):
                raise ArtifactReaderError(
                    f"JSON object key must be a string, got {type(key).__name__}",
                    code="invalid_json_type",
                )
            if key in mapping:
                raise ArtifactReaderError(
                    f"duplicate key '{key}' in JSON input",
                    code="duplicate_key",
                )
            mapping[key] = value
        return mapping

    def _check_depth(obj: Any, depth: int):
        if depth > max_depth:
            raise ArtifactReaderError(
                f"JSON nesting depth exceeds limit ({max_depth})",
                code="exceeds_max_depth",
            )
        if isinstance(obj, dict):
            for v in obj.values():
                _check_depth(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _check_depth(item, depth + 1)

    try:
        data = json.loads(
            text,
            object_pairs_hook=_strict_pairs_hook,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as ex:
        raise ArtifactReaderError(
            f"JSON parse failure: {ex.msg}",
            code="json_syntax_error",
            line=ex.lineno,
            column=ex.colno,
        ) from ex
    except RecursionError:
        raise ArtifactReaderError(
            f"JSON nesting depth exceeds limit ({max_depth})",
            code="exceeds_max_depth",
        )

    if not isinstance(data, dict):
        raise ArtifactReaderError(
            "JSON input payload must be an object",
            code="not_an_object",
        )

    _check_depth(data, 1)
    return data



@dataclass(frozen=True)
class ArtifactParseResult:
    """Result of strict artifact parsing."""

    metadata: dict[str, Any]
    raw_metadata: str
    raw_body: str
    has_frontmatter: bool
    encoding: str
    line_ending: str


class StrictYamlLoader(yaml.SafeLoader):
    """PyYAML SafeLoader subclass enforcing strict duplicate-key and float rules."""
    pass


def _strict_construct_yaml_float(loader: StrictYamlLoader, node: yaml.ScalarNode) -> float:
    val = loader.construct_yaml_float(node)
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        line = node.start_mark.line + 1 if node.start_mark else None
        col = node.start_mark.column + 1 if node.start_mark else None
        raise ArtifactReaderError(
            f"non-finite float '{val}' is not permitted in artifact YAML",
            code="non_finite_float",
            line=line,
            column=col,
        )
    return val


def _strict_construct_mapping(loader: StrictYamlLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    if not isinstance(node, yaml.MappingNode):
        raise ArtifactReaderError(f"Expected mapping, got {node.id}")
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            line = key_node.start_mark.line + 1 if key_node.start_mark else None
            col = key_node.start_mark.column + 1 if key_node.start_mark else None
            raise ArtifactReaderError(
                f"duplicate key '{key}' in YAML input",
                code="duplicate_key",
                line=line,
                column=col,
            )
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


def _undefined_tag_constructor(loader: StrictYamlLoader, tag_suffix: str, node: yaml.Node) -> Any:
    line = node.start_mark.line + 1 if node.start_mark else None
    col = node.start_mark.column + 1 if node.start_mark else None
    raise ArtifactReaderError(
        f"custom tag '{node.tag}' is not permitted",
        code="custom_tag_disallowed",
        line=line,
        column=col,
    )


StrictYamlLoader.add_constructor("tag:yaml.org,2002:float", _strict_construct_yaml_float)
StrictYamlLoader.add_constructor("tag:yaml.org,2002:map", _strict_construct_mapping)
StrictYamlLoader.add_multi_constructor("!", _undefined_tag_constructor)


def strict_parse_yaml(yaml_text: str, *, max_bytes: int = 1024 * 1024) -> dict[str, Any]:
    """Parse YAML text strictly into a Python dictionary.

    Raises ArtifactReaderError on syntax errors, duplicate keys, custom tags,
    non-finite values, or exceeding max bytes.
    """
    raw_bytes = yaml_text.encode("utf-8")
    if len(raw_bytes) > max_bytes:
        raise ArtifactReaderError(
            f"YAML payload size ({len(raw_bytes)} bytes) exceeds max bytes ({max_bytes})",
            code="exceeds_max_bytes",
        )

    try:
        data = yaml.load(yaml_text, Loader=StrictYamlLoader)
    except yaml.YAMLError as ex:
        if isinstance(ex, ArtifactReaderError):
            raise ex
        mark = getattr(ex, "problem_mark", None)
        line = mark.line + 1 if mark else None
        col = mark.column + 1 if mark else None
        raise ArtifactReaderError(
            f"YAML parse failure: {ex}",
            code="yaml_syntax_error",
            line=line,
            column=col,
        ) from ex

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ArtifactReaderError("YAML content must be a mapping/dict", code="not_a_mapping")

    return data


def strict_read_artifact(
    content: str | bytes,
    *,
    max_bytes: int = 1024 * 1024,
    has_frontmatter_delimiters: bool = True,
) -> ArtifactParseResult:
    """Strictly read and split a Markdown/YAML artifact file into metadata and raw body.

    Preserves exact raw body bytes/newlines without trimming or stripping.
    """
    if isinstance(content, bytes):
        raw_bytes = content
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
            text = raw_bytes.decode("utf-8-sig")
        else:
            encoding = "utf-8"
            text = raw_bytes.decode("utf-8")
    else:
        encoding = "utf-8-sig" if content.startswith("\ufeff") else "utf-8"
        text = content[1:] if content.startswith("\ufeff") else content
        raw_bytes = text.encode("utf-8")

    if len(raw_bytes) > max_bytes:
        raise ArtifactReaderError(
            f"Artifact size ({len(raw_bytes)} bytes) exceeds max bytes limit ({max_bytes})",
            code="exceeds_max_bytes",
        )

    line_ending = "\r\n" if "\r\n" in text else "\n"

    if not has_frontmatter_delimiters:
        metadata = strict_parse_yaml(text, max_bytes=max_bytes)
        return ArtifactParseResult(
            metadata=metadata,
            raw_metadata=text,
            raw_body="",
            has_frontmatter=False,
            encoding=encoding,
            line_ending=line_ending,
        )

    # Frontmatter split matching '---\n' or '---\r\n'
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        # No valid frontmatter opening delimiter
        raise ArtifactReaderError(
            "Artifact does not start with frontmatter delimiter '---'",
            code="missing_frontmatter_delimiter",
        )

    # Find end delimiter
    open_len = 4 if text.startswith("---\r\n") else 4  # '---\r\n' is 5 chars, '---\n' is 4 chars
    if text.startswith("---\r\n"):
        open_len = 5

    rest = text[open_len:]
    # Find closing '---' line
    # Look for \n---\n, \r\n---\r\n, \n---\r\n, \r\n---\n, or \n--- / \r\n--- at EOF
    close_idx = -1
    close_len = 0

    lines = rest.splitlines(keepends=True)
    accum_len = 0
    for i, line in enumerate(lines):
        line_stripped = line.rstrip("\r\n")
        if line_stripped == "---":
            close_idx = accum_len
            close_len = len(line)
            break
        accum_len += len(line)

    if close_idx == -1:
        raise ArtifactReaderError(
            "Artifact frontmatter missing closing delimiter '---'",
            code="missing_closing_delimiter",
        )

    raw_metadata = rest[:close_idx]
    raw_body = rest[close_idx + close_len :]

    metadata = strict_parse_yaml(raw_metadata, max_bytes=max_bytes)

    return ArtifactParseResult(
        metadata=metadata,
        raw_metadata=raw_metadata,
        raw_body=raw_body,
        has_frontmatter=True,
        encoding=encoding,
        line_ending=line_ending,
    )
