"""Unit tests for strict bounded artifact reader (AW-02)."""

import pytest
from deltafuse.core.artifact_reader import (
    strict_read_artifact,
    strict_parse_yaml,
    strict_parse_json,
    ArtifactReaderError,
    ArtifactParseResult,
)


def test_duplicate_yaml_key_rejected():
    yaml_text = """
id: TASK-001
title: First
id: TASK-002
"""
    with pytest.raises(ArtifactReaderError, match="duplicate key"):
        strict_parse_yaml(yaml_text)


def test_body_trailing_blank_lines_preserved():
    content = "---\nid: TASK-001\n---\nLine 1\nLine 2\n\n\n"
    res = strict_read_artifact(content)
    assert isinstance(res, ArtifactParseResult)
    assert res.metadata == {"id": "TASK-001"}
    assert res.raw_body == "Line 1\nLine 2\n\n\n"


def test_crlf_and_bom_preserved():
    content = "\ufeff---\r\nid: TASK-001\r\n---\r\nLine 1\r\nLine 2\r\n"
    res = strict_read_artifact(content)
    assert res.metadata == {"id": "TASK-001"}
    assert res.raw_body == "Line 1\r\nLine 2\r\n"
    assert res.encoding == "utf-8-sig"
    assert res.line_ending == "\r\n"


def test_non_finite_float_rejected():
    content = "---\nval: .nan\n---"
    with pytest.raises(ArtifactReaderError, match="non-finite"):
        strict_read_artifact(content)

    content_inf = "---\nval: .inf\n---"
    with pytest.raises(ArtifactReaderError, match="non-finite"):
        strict_read_artifact(content_inf)


def test_custom_yaml_tag_rejected():
    content = "---\nval: !custom_tag foo\n---"
    with pytest.raises(ArtifactReaderError, match="custom tag"):
        strict_read_artifact(content)


def test_excessive_size_rejected():
    large_content = "---\nid: TASK-001\n---\n" + ("x" * (1024 * 1024 + 100))
    with pytest.raises(ArtifactReaderError, match="exceeds max bytes"):
        strict_read_artifact(large_content, max_bytes=1024 * 1024)


def test_no_frontmatter_standalone_yaml():
    yaml_content = "id: TASK-001\nkind: feature\n"
    res = strict_read_artifact(yaml_content, has_frontmatter_delimiters=False)
    assert res.metadata == {"id": "TASK-001", "kind": "feature"}
    assert res.raw_body == ""


def test_non_ascii_unicode_preserved():
    content = "---\ntitle: Заголовок\n---\nПривет, мир!\n\n✨ Test emoji"
    res = strict_read_artifact(content)
    assert res.metadata["title"] == "Заголовок"
    assert res.raw_body == "Привет, мир!\n\n✨ Test emoji"


def test_scalar_types_and_dates_parsing():
    content = """---
string_val: "123"
bool_true: true
bool_false: false
null_val: null
date_val: 2026-09-18
---
"""
    res = strict_read_artifact(content)
    assert res.metadata["string_val"] == "123"
    assert res.metadata["bool_true"] is True
    assert res.metadata["bool_false"] is False
    assert res.metadata["null_val"] is None


def test_missing_frontmatter_delimiters_raises():
    bad_content = "id: TASK-001\nno delimiters here"
    with pytest.raises(ArtifactReaderError, match="delimiter"):
        strict_read_artifact(bad_content)


def test_strict_parse_json_success():
    json_text = '{"a": 1, "b": "hello", "c": [1, 2, 3]}'
    res = strict_parse_json(json_text)
    assert res == {"a": 1, "b": "hello", "c": [1, 2, 3]}


def test_strict_parse_json_duplicate_key_rejected():
    bad_json = '{"key": 1, "key": 2}'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(bad_json)
    assert exc_info.value.code == "duplicate_key"


def test_strict_parse_json_nested_duplicate_key_rejected():
    bad_json = '{"outer": {"nested": "a", "nested": "b"}}'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(bad_json)
    assert exc_info.value.code == "duplicate_key"


def test_strict_parse_json_non_finite_float_rejected():
    bad_json = '{"val": NaN}'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(bad_json)
    assert exc_info.value.code in ("non_finite_float", "json_syntax_error")


def test_strict_parse_json_excessive_depth_rejected():
    deep_json = '{"a": ' + ('{"a": ' * 110) + '1' + ('}' * 110) + '}'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(deep_json, max_depth=100)
    assert exc_info.value.code == "exceeds_max_depth"


def test_strict_parse_json_max_bytes_rejected():
    large_bytes = b'{"a": "' + (b'x' * 100) + b'"}'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(large_bytes, max_bytes=50)
    assert exc_info.value.code == "exceeds_max_bytes"


def test_strict_parse_json_non_object_rejected():
    arr_json = '[1, 2, 3]'
    with pytest.raises(ArtifactReaderError) as exc_info:
        strict_parse_json(arr_json)
    assert exc_info.value.code == "not_an_object"

