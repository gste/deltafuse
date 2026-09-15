"""Tests for tool envelope and capability guard (J03-503)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.document_flow.worker.tool_guard import (
    match_globs,
    validate_file_action,
    validate_tool_invocation,
)


def test_match_globs():
    globs = ["docs/changes/*/routing.yaml", "docs/changes/*/slices/**"]
    assert match_globs("docs/changes/CHG-001/routing.yaml", globs) is True
    assert match_globs("docs/changes/CHG-001/slices/slice-1.yaml", globs) is True
    assert match_globs("src/Main.java", globs) is False


def test_validate_file_action_with_envelope(tmp_path):
    envelope = {
        "step": "analyze",
        "write": ["docs/changes/*/analysis.md"],
    }
    res_ok = validate_file_action(tmp_path, "write", "docs/changes/CHG-1/analysis.md", envelope)
    assert res_ok.allowed is True

    res_fail = validate_file_action(tmp_path, "write", "src/App.java", envelope)
    assert res_fail.allowed is False
    assert "not in envelope" in res_fail.reason


def test_validate_file_action_null_envelope(tmp_path):
    res_exempt = validate_file_action(tmp_path, "write", "docs/intake/req.md", None)
    assert res_exempt.allowed is True

    res_product = validate_file_action(tmp_path, "write", "src/App.java", None)
    assert res_product.allowed is False
    assert "null write envelope" in res_product.reason


def test_validate_forbidden_tools(tmp_path):
    res_browser = validate_tool_invocation("search_web", {"query": "deltafuse"}, None, tmp_path)
    assert res_browser.allowed is False
    assert "forbidden tool" in res_browser.reason

    res_subagent = validate_tool_invocation("invoke_subagent", {}, None, tmp_path)
    assert res_subagent.allowed is False
    assert "forbidden tool" in res_subagent.reason


def test_validate_forbidden_commands(tmp_path):
    res_curl = validate_tool_invocation("run_command", {"CommandLine": "curl http://external.com"}, None, tmp_path)
    assert res_curl.allowed is False
    assert "forbidden command" in res_curl.reason

    res_push = validate_tool_invocation("run_command", {"CommandLine": "git push origin main"}, None, tmp_path)
    assert res_push.allowed is False
    assert "forbidden command" in res_push.reason
