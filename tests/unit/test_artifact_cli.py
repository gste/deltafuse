"""Unit tests for Artifact Writer CLI subcommands and tool argument schema export (AW-11).

Tests CLI parsing, JSON stdin/file inputs, exit codes (0, 2, 3, 4, 5),
core-owned field protection, Unicode preservation, and tool argument schemas.
"""

import json
from pathlib import Path
import pytest
from deltafuse.cli import main, export_tool_schemas


def test_export_tool_schemas():
    schemas = export_tool_schemas(kind="task", operation="create")
    assert "properties" in schemas
    assert "semantic_payload" in schemas["properties"]
    # Ensure Core-owned fields are excluded from creatable/updatable public tool fields
    allowed = schemas["properties"]["semantic_payload"].get("properties", {})
    assert "status" not in allowed
    assert "schema_version" not in allowed
    assert "framework" not in allowed


def test_cli_describe_subcommand(capsys):
    exit_code = main(["artifact", "describe", "--kind", "task", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["kind"] == "task"
    assert "title" in data["allowed_semantic_fields"]
    assert "status" in data["core_owned_fields"]


def test_cli_describe_export_schema(capsys):
    exit_code = main(["artifact", "describe", "--kind", "task", "--operation", "create", "--export-schema"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "properties" in data


def _setup_cli_test_dir(tmp_path):
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 3.1.0\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:17786cb040d1ed3cd5636dd4a6b97453c1b77627\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-001\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")


def test_cli_create_subcommand_success(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "input.json"
    payload = {
        "identity": "TASK-001",
        "semantic_payload": {
            "title": "Build CLI integration",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": ["src/deltafuse/cli.py"],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-001: Build CLI integration\n\nImplementation details.",
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main([
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(input_file),
        "--json",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt["outcome"] == "committed"
    assert (tmp_path / "tasks" / "TASK-001.md").is_file()


def test_cli_create_core_owned_field_denied(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "input.json"
    payload = {
        "identity": "TASK-002",
        "semantic_payload": {
            "title": "Spoof status",
            "status": "verified",
        },
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main([
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(input_file),
        "--json",
    ])
    assert exit_code == 3
    captured = capsys.readouterr()
    assert "Core-owned" in captured.err or "core_owned_field" in captured.err or "status" in captured.err


def test_cli_create_invalid_json_input(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "bad.json"
    input_file.write_text("{invalid json", encoding="utf-8")

    exit_code = main([
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(input_file),
        "--json",
    ])
    assert exit_code == 2
    assert not (tmp_path / "tasks" / "TASK-001.md").exists()


def test_cli_update_subcommand_success(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    # First create artifact
    input_file = tmp_path / "create.json"
    payload = {
        "identity": "TASK-010",
        "semantic_payload": {
            "title": "Initial Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    main(["artifact", "create", "--kind", "task", "--change", str(tmp_path), "--input", str(input_file), "--json"])
    capsys.readouterr()

    target_file = tmp_path / "tasks" / "TASK-010.md"
    assert target_file.is_file()
    import hashlib
    sha256 = hashlib.sha256(target_file.read_bytes()).hexdigest()

    update_file = tmp_path / "update.json"
    update_payload = {
        "target": "tasks/TASK-010.md",
        "expected_sha256": sha256,
        "patch": {
            "set": [{"path": "/allowed_paths", "value": ["src/updated.py"]}],
        },
    }
    update_file.write_text(json.dumps(update_payload), encoding="utf-8")

    exit_code = main([
        "artifact", "update",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(update_file),
        "--json",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt["outcome"] == "committed"
    assert "src/updated.py" in target_file.read_text(encoding="utf-8")


def test_cli_update_stale_expected_sha256(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    # Create artifact
    input_file = tmp_path / "create.json"
    payload = {
        "identity": "TASK-011",
        "semantic_payload": {
            "title": "Task Eleven",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    main(["artifact", "create", "--kind", "task", "--change", str(tmp_path), "--input", str(input_file), "--json"])
    capsys.readouterr()

    update_file = tmp_path / "update.json"
    update_payload = {
        "target": "tasks/TASK-011.md",
        "expected_sha256": "0" * 64,  # wrong hash
        "patch": {"set": [{"path": "/allowed_paths", "value": ["src/new.py"]}]},
    }
    update_file.write_text(json.dumps(update_payload), encoding="utf-8")

    exit_code = main([
        "artifact", "update",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(update_file),
        "--json",
    ])
    assert exit_code == 4


def test_cli_validate_subcommand(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    # Create valid task
    input_file = tmp_path / "create.json"
    payload = {
        "identity": "TASK-020",
        "semantic_payload": {
            "title": "Task Twenty",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    main(["artifact", "create", "--kind", "task", "--change", str(tmp_path), "--input", str(input_file), "--json"])
    capsys.readouterr()

    # Validate existing valid file -> exit code 0
    exit_code = main([
        "artifact", "validate",
        "--kind", "task",
        "--change", str(tmp_path),
        "--target", "tasks/TASK-020.md",
        "--json",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["valid"] is True

    # Validate non-existent file -> exit code 2
    exit_code_missing = main([
        "artifact", "validate",
        "--kind", "task",
        "--change", str(tmp_path),
        "--target", "tasks/NONEXISTENT.md",
        "--json",
    ])
    assert exit_code_missing == 2


def test_cli_unicode_and_multiline_payload(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "unicode.json"
    unicode_title = "Title with \u4e16\u754c Unicode & \"Quotes\" \n Next Line"
    unicode_body = "# TASK-030: \u4e16\u754c\n\nMultiline body with emoji \U0001F600\nSpecial chars: \\n \\t \" ' < > &"

    payload = {
        "identity": "TASK-030",
        "semantic_payload": {
            "title": unicode_title,
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": unicode_body,
    }
    input_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    exit_code = main([
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(input_file),
        "--json",
    ])
    assert exit_code == 0
    task_file = tmp_path / "tasks" / "TASK-030.md"
    content = task_file.read_text(encoding="utf-8")
    assert "\u4e16\u754c" in content
    assert "\U0001F600" in content


def test_reproduce_finding_3_cli_create_duplicate_key_and_unknown_envelope_field_rejected(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "finding3.json"
    raw_json_str = """{
        "request_id": "req-f3",
        "operation": "create",
        "kind": "task",
        "kind": "task",
        "unknown_envelope_field": "bogus",
        "identity": "TASK-099",
        "semantic_payload": {
            "title": "Finding 3 Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5}
        }
    }"""
    input_file.write_text(raw_json_str, encoding="utf-8")

    exit_code = main([
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(input_file),
        "--json",
    ])
    assert exit_code == 2
    assert not (tmp_path / "tasks" / "TASK-099.md").exists()


def test_cli_update_explicit_empty_body_replacement(tmp_path, capsys):
    _setup_cli_test_dir(tmp_path)
    input_file = tmp_path / "create.json"
    payload = {
        "identity": "TASK-040",
        "semantic_payload": {
            "title": "Task with Body",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-040: Task with Body\n\nInitial Body text.",
    }
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    main(["artifact", "create", "--kind", "task", "--change", str(tmp_path), "--input", str(input_file), "--json"])
    capsys.readouterr()

    target_file = tmp_path / "tasks" / "TASK-040.md"
    assert "Initial Body text." in target_file.read_text(encoding="utf-8")
    import hashlib
    sha256 = hashlib.sha256(target_file.read_bytes()).hexdigest()

    update_file = tmp_path / "update.json"
    update_payload = {
        "target": "tasks/TASK-040.md",
        "expected_sha256": sha256,
        "patch": {
            "set": [{"path": "/allowed_paths", "value": ["src/empty.py"]}],
        },
        "body_replacement": "",
    }
    update_file.write_text(json.dumps(update_payload), encoding="utf-8")

    exit_code = main([
        "artifact", "update",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", str(update_file),
        "--json",
    ])
    assert exit_code == 0
    updated_content = target_file.read_text(encoding="utf-8")
    assert "Initial Body text." not in updated_content


