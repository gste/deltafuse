"""HS-001: next --json halt is the host button contract."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema.validators import validator_for

from deltafuse.cli import main
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder
from tests.unit.test_queue import _write_proposed_dec


def _halt_schema(repo_root: Path) -> dict:
    path = repo_root / "docs" / "contracts" / "halt.schema.yaml"
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    return schema


def _assert_valid_halt(halt: dict, repo_root: Path) -> None:
    schema = _halt_schema(repo_root)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    errors = [err.message for err in validator_cls(schema).iter_errors(halt)]
    assert errors == [], errors
    assert any(row.get("id") == "inspect" and row.get("command") is None for row in halt["choices"])
    for row in halt["choices"]:
        cmd = row.get("command")
        if cmd is None:
            continue
        text = str(cmd)
        assert text.startswith("deltafuse decide ")
        assert "git push" not in text
        assert "git merge" not in text


def _next_json(product: Path, capsys) -> tuple[int, dict]:
    ret = main(["next", str(product), "--json"])
    out, _ = capsys.readouterr()
    return ret, json.loads(out)


def test_halt_schema_is_draft_2020(repo_root: Path):
    schema = _halt_schema(repo_root)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "halt/v1" in schema["$id"]


def test_next_json_done_halt_matches_contract(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    halt = data["halt"]
    assert halt["kind"] == "done"
    _assert_valid_halt(halt, repo_root)
    assert all(row["command"] is None for row in halt["choices"])


def test_next_json_decision_halt_matches_contract(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-080", title="Halt dec").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    _write_proposed_dec(tmp_path, "CHG-080", title="Pick a store")
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 1
    halt = data["halt"]
    assert halt["kind"] == "decision"
    _assert_valid_halt(halt, repo_root)
    assert any("deltafuse decide" in (row["command"] or "") and "--decision" in (row["command"] or "") for row in halt["choices"])


def test_next_json_spec_halt_matches_contract(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-081", title="Halt spec").step_intake().step_analyze()
    builder._update_change_yaml({"status": "specification-proposed"})
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 1
    halt = data["halt"]
    assert halt["kind"] == "spec"
    _assert_valid_halt(halt, repo_root)
    assert any("--spec" in (row["command"] or "") for row in halt["choices"])


def test_next_json_blocked_halt_matches_contract(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-083", title="Halt blocked")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: pending", "status: blocked"), encoding="utf-8")
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 1
    halt = data["halt"]
    assert halt["kind"] == "blocked"
    _assert_valid_halt(halt, repo_root)
    assert all(row["command"] is None for row in halt["choices"])


def test_halt_schema_rejects_push_and_inspect_command(repo_root: Path):
    schema = _halt_schema(repo_root)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    push = {
        "kind": "decision",
        "prompt": "Stop",
        "choices": [{"id": "push", "label": "Push", "command": "git push"}],
    }
    inspect_run = {
        "kind": "blocked",
        "prompt": "Stop",
        "choices": [{"id": "inspect", "label": "Inspect", "command": "deltafuse decide . --spec --status accepted"}],
    }
    assert list(validator_cls(schema).iter_errors(push))
    assert list(validator_cls(schema).iter_errors(inspect_run))


def test_ready_step_has_null_halt(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-082", title="Ready").step_intake()
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    assert data["halt"] is None
    assert data["selected"]["skill"] == "analyze"


def test_installer_adapters_do_not_vendor_oracle(tmp_path: Path, repo_root: Path):
    # Pack isolation for the Worker sandbox is `test_init_does_not_copy_oracle`.
    # This locks the generated adapter snapshot: no oracle.yaml / hidden_suite.
    install(target_dir=tmp_path, framework_root=repo_root)
    names = [p.as_posix() for p in tmp_path.rglob("*") if p.is_file()]
    joined = "\n".join(names).lower()
    assert "oracle.yaml" not in joined
    assert "hidden_suite" not in joined
    for root in (".agents/skills", ".cursor/skills", ".gemini/skills"):
        skill_root = tmp_path / root
        if not skill_root.is_dir():
            continue
        for path in skill_root.rglob("*.md"):
            text = path.read_text(encoding="utf-8").lower()
            assert "oracle.yaml" not in text
            assert "hidden_suite" not in text
