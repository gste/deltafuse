"""LS-001/LS-002: write envelope on next --json and deltafuse leash."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from jsonschema.validators import validator_for

from deltafuse.cli import main
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _envelope_schema(repo_root: Path) -> dict:
    path = repo_root / "docs" / "contracts" / "leash.schema.yaml"
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    return schema


def _assert_valid_envelope(envelope: dict, repo_root: Path) -> None:
    schema = _envelope_schema(repo_root)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    errors = [err.message for err in validator_cls(schema).iter_errors(envelope)]
    assert errors == [], errors
    assert envelope["write"]


def _next_json(product: Path, capsys) -> tuple[int, dict]:
    ret = main(["next", str(product), "--json"])
    out, _ = capsys.readouterr()
    return ret, json.loads(out)


def _leash_json(product: Path, capsys, files: list[str] | None = None) -> tuple[int, dict]:
    argv = ["leash", str(product), "--json"]
    for rel in files or []:
        argv.extend(["--file", rel])
    ret = main(argv)
    out, err = capsys.readouterr()
    body = out if out.strip() else err
    return ret, json.loads(body)


def _git_init_commit(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=leash@test",
            "-c",
            "user.name=leash",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "init",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _set_baseline(product: Path, status: str = "accepted") -> None:
    config = product / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data.setdefault("project", {})["baseline"] = status
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_envelope_schema_is_draft_2020(repo_root: Path):
    schema = _envelope_schema(repo_root)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "leash/v1" in schema["$id"]


def test_next_json_intake_envelope_excludes_src(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / "docs" / "intake" / "note.md").write_text("# want a change\n", encoding="utf-8")
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    assert data["halt"] is None
    envelope = data["envelope"]
    assert envelope["step"] == "intake"
    _assert_valid_envelope(envelope, repo_root)
    blob = " ".join(envelope["write"])
    assert "src/" not in blob
    assert "src/**" not in envelope["write"]


def test_next_json_analyze_has_envelope_halt_null(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-090", title="Envelope").step_intake()
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    assert data["halt"] is None
    envelope = data["envelope"]
    assert envelope["step"] == "analyze"
    assert envelope["change"] == "CHG-090"
    _assert_valid_envelope(envelope, repo_root)
    assert any("routing.yaml" in row for row in envelope["write"])
    assert "src/**" not in envelope["write"]


def test_next_json_declare_envelope_keeps_tests_and_task_paths(
    tmp_path: Path, repo_root: Path, capsys
):
    install(target_dir=tmp_path, framework_root=repo_root)
    (
        MockChangeBuilder(tmp_path, change_id="CHG-091", title="Declare env")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    envelope = data["envelope"]
    assert envelope["step"] == "declare"
    assert envelope["task"] == "TASK-001"
    _assert_valid_envelope(envelope, repo_root)
    assert any(row.startswith("tests") for row in envelope["write"])
    assert "src/core.py" not in envelope["write"]
    assert "src/**" not in envelope["write"]


def test_next_json_implement_envelope_uses_task_allowed_paths(
    tmp_path: Path, repo_root: Path, capsys
):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-093", title="Implement env")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(
        task.read_text(encoding="utf-8").replace("status: pending", "status: implementing"),
        encoding="utf-8",
    )
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    envelope = data["envelope"]
    assert envelope["step"] == "implement"
    assert envelope["task"] == "TASK-001"
    _assert_valid_envelope(envelope, repo_root)
    assert any(row.startswith("tests") for row in envelope["write"])
    assert "src/core.py" in envelope["write"]
    assert "src/secret.py" not in envelope["write"]
    assert "src/**" not in envelope["write"]


def test_next_json_done_halt_has_null_envelope(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    assert data["halt"]["kind"] == "done"
    assert data["envelope"] is None


def test_leash_intake_rejects_src_file(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / "docs" / "intake" / "note.md").write_text("# want a change\n", encoding="utf-8")
    ret, data = _leash_json(tmp_path, capsys, files=["src/foo.py"])
    assert ret == 1
    assert data["ok"] is False
    assert data["skipped"] is False
    assert data["envelope"]["step"] == "intake"
    assert data["violations"]


def test_leash_intake_allows_change_request(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / "docs" / "intake" / "note.md").write_text("# want\n", encoding="utf-8")
    ret, data = _leash_json(
        tmp_path,
        capsys,
        files=["docs/changes/CHG-001-example/request.md"],
    )
    assert ret == 0
    assert data["ok"] is True
    assert data["envelope"]["step"] == "intake"


def test_leash_advisory_same_violations_exit_zero(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / "docs" / "intake" / "note.md").write_text("# want a change\n", encoding="utf-8")
    config = tmp_path / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["workflow"]["leash"] = "advisory"
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    ret, payload = _leash_json(tmp_path, capsys, files=["src/foo.py"])
    assert ret == 0
    assert payload["mode"] == "advisory"
    assert payload["violations"]
    assert payload["ok"] is False


def test_leash_exempt_path_when_no_ready_step(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret, data = _leash_json(tmp_path, capsys, files=["AGENTS.md"])
    assert ret == 0
    assert data["skipped"] is True
    assert data["envelope"] is None
    assert data["violations"] == []


def test_leash_orphan_src_without_change(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_baseline(tmp_path)
    ret, data = _leash_json(tmp_path, capsys, files=["src/x.py"])
    assert ret == 1
    assert data["skipped"] is False
    assert data["envelope"] is None
    assert any("not covered by any Change" in row for row in data["violations"])


def test_leash_implement_covers_allowed_src(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_baseline(tmp_path)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-094", title="Covered src")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(
        task.read_text(encoding="utf-8").replace("status: pending", "status: implementing"),
        encoding="utf-8",
    )
    ret, data = _leash_json(tmp_path, capsys, files=["src/core.py"])
    assert ret == 0
    assert data["ok"] is True
    assert data["envelope"]["step"] == "implement"


def test_leash_docs_route_allows_spec_rejects_src(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_baseline(tmp_path)
    (
        MockChangeBuilder(tmp_path, change_id="CHG-095", title="Docs route", route="docs")
        .step_intake()
        .step_analyze()
    )
    ret_ok, data_ok = _leash_json(tmp_path, capsys, files=["docs/spec/core.md"])
    assert ret_ok == 0
    assert data_ok["ok"] is True
    assert data_ok["envelope"]["step"] == "specify"
    ret_bad, data_bad = _leash_json(tmp_path, capsys, files=["src/x.py"])
    assert ret_bad == 1
    assert data_bad["ok"] is False
    assert data_bad["violations"]


def test_leash_git_diff_rejects_src_on_intake(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / "docs" / "intake" / "note.md").write_text("# want a change\n", encoding="utf-8")
    _git_init_commit(tmp_path)
    src = tmp_path / "src" / "foo.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("print(1)\n", encoding="utf-8")
    ret = main(["leash", str(tmp_path), "--json"])
    out, err = capsys.readouterr()
    payload = json.loads(out if out.strip() else err)
    assert ret == 1
    assert payload["violations"]
    assert any("src/foo.py" in row for row in payload["violations"])
