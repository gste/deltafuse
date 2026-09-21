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
        .step_declare()
    )
    builder._core_advance("declaring")
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


def test_leash_contract_requires_host_must(repo_root: Path):
    text = (repo_root / "docs" / "contracts" / "leash.md").read_text(encoding="utf-8")
    assert "## Host MUST" in text
    assert "MUST restrict write tools to `envelope.write`" in text
    assert "src/deltafuse/**" in text
    halt = (repo_root / "docs" / "contracts" / "halt.md").read_text(encoding="utf-8")
    assert "envelope` is JSON `null`" in halt


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


def test_leash_draft_src_is_orphan(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret, data = _leash_json(tmp_path, capsys, files=["src/x.py"])
    assert ret == 1
    assert any("not covered by any Change" in row for row in data["violations"])


def test_leash_draft_spec_is_not_orphan(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret, data = _leash_json(tmp_path, capsys, files=["docs/spec/core.md"])
    assert ret == 0
    assert data["violations"] == []


def test_leash_accepted_spec_is_orphan(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_baseline(tmp_path)
    ret, data = _leash_json(tmp_path, capsys, files=["docs/spec/core.md"])
    assert ret == 1
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
        .step_declare()
    )
    builder._core_advance("declaring")
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
    docs_change = (
        MockChangeBuilder(tmp_path, change_id="CHG-095", title="Docs route", route="docs")
        .step_intake()
        .step_analyze()
    )
    # The specify envelope opens only after the Core analyzed receipt.
    docs_change._core_advance("analyzed")
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


def test_posix_relpath_keeps_dot_directories():
    """lstrip("./") stripped a character set, turning '.deltafuse/x' into
    'deltafuse/x': no dot-directory ever matched a glob like '.deltafuse/**'."""
    from deltafuse.core.context import matches_contract_globs, posix_relpath

    assert posix_relpath(".deltafuse/bench.yaml") == ".deltafuse/bench.yaml"
    assert posix_relpath(".github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert posix_relpath("./src/app.py") == "src/app.py"
    assert posix_relpath("/src/app.py") == "src/app.py"
    assert matches_contract_globs(".deltafuse/config.yaml", [".deltafuse/**"])


def test_deltafuse_dir_is_exempt_but_core_journals_stay_guarded():
    """`.deltafuse/**` is exempt as a whole; the DF3-007 guard on Core-owned
    journals must still fire, so it runs before the exemptions."""
    from deltafuse.core.leash import check_paths, is_exempt_path

    assert is_exempt_path(".deltafuse/bench.yaml")
    assert check_paths([".deltafuse/bench.yaml"], [], baseline="draft") == []
    for journal in ("transitions.jsonl", "gate-journal.jsonl", "journal-head", "trusted-keys.yaml"):
        errors = check_paths([f".deltafuse/{journal}"], [], baseline="draft")
        assert errors and "Core-owned" in errors[0], journal


def _commit_all(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=leash@test", "-c", "user.name=leash",
         "-c", "commit.gpgsign=false", "commit", "-q", "-m", message],
        cwd=root, check=True, capture_output=True, text=True,
    )


def _leash_diff(product: Path, capsys) -> tuple[int, dict]:
    ret = main(["leash", str(product), "--json"])
    out, err = capsys.readouterr()
    return ret, json.loads(out if out.strip() else err)


def test_leash_judges_finished_intake_by_its_own_envelope(tmp_path: Path, repo_root: Path, capsys):
    """q0 run M01: once request.md exists the queue already names analyze, so
    the intake step's own writes read as outside the analyze envelope. The
    receipt chain keeps the step the Change is still in."""
    install(target_dir=tmp_path, framework_root=repo_root)
    _git_init_commit(tmp_path)
    MockChangeBuilder(tmp_path, change_id="CHG-501", title="Chain").step_intake()
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    assert ret == 0


def test_leash_accepts_a_commit_after_advance(tmp_path: Path, repo_root: Path, capsys):
    """Every `deltafuse advance` appends to transitions.jsonl, which leash
    refused outright: no commit after advance could pass the hook."""
    install(target_dir=tmp_path, framework_root=repo_root)
    _git_init_commit(tmp_path)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-502", title="Chain").step_intake()
    builder._core_advance("intake")
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    assert ret == 0
    # The chain does not open code paths: src/ stays outside every envelope.
    src = tmp_path / "src" / "app.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("print(1)\n", encoding="utf-8")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("src/app.py" in row for row in data["violations"])


def test_leash_rejects_forged_or_edited_transition_receipts(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    _git_init_commit(tmp_path)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-503", title="Forge").step_intake()
    builder._core_advance("intake")
    _commit_all(tmp_path, "intake")
    journal = tmp_path / ".deltafuse" / "transitions.jsonl"
    original = journal.read_text(encoding="utf-8")

    forged = {"kind": "transition", "change": "CHG-503", "gate": "analyzed",
              "from": "analyzing", "to": "analyzed", "recorded": "2026-09-21T00:00:00Z",
              "receipt": "0" * 64}
    journal.write_text(original + json.dumps(forged) + "\n", encoding="utf-8")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("receipt digest does not match" in row for row in data["violations"])

    journal.write_text(original.replace("normalized", "analyzed", 1), encoding="utf-8")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("append-only" in row for row in data["violations"])


def test_leash_accepts_decide_spec_and_rejects_a_legacy_click(tmp_path: Path, repo_root: Path, capsys):
    """decide --spec appends to the gate journal, journal-head and (now) the
    transition chain; all three must pass. A hand-appended legacy-format click
    must not, because has_click still counts legacy lines."""
    from tests.unit.test_decide import _spec_proposed

    builder = _spec_proposed(tmp_path, repo_root, "CHG-504", "proposed")
    _git_init_commit(tmp_path)
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0
    capsys.readouterr()
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    assert ret == 0

    _commit_all(tmp_path, "spec accepted")
    gate_journal = tmp_path / ".deltafuse" / "gate-journal.jsonl"
    legacy = {"kind": "decision", "status": "accepted", "id": "DEC-0009",
              "path": "docs/decisions/DEC-0009.md", "change": "CHG-504"}
    with gate_journal.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(legacy) + "\n")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("not a current-format gate receipt" in row for row in data["violations"])


def test_leash_without_product_root_still_refuses_core_journals():
    """The pure check (no repository to verify against) keeps DF3-007 strict."""
    from deltafuse.core.leash import check_paths

    errors = check_paths([".deltafuse/transitions.jsonl"], [], baseline="draft")
    assert errors and "Core-owned" in errors[0]


def test_leash_accepts_a_state_rewrite_and_rejects_a_hand_edit_riding_on_it(
    tmp_path: Path, repo_root: Path, capsys
):
    """q0 run M01, specify step: `deltafuse state --slice` rewrites the slice
    frontmatter, which lies outside the specify envelope on purpose. The guard
    vouches for it by its artifact-status receipt - and only while nothing but
    the status changed."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-505", title="State").step_intake().step_analyze()
    builder._core_advance("analyzed")
    _git_init_commit(tmp_path)

    assert main(["state", str(builder.change_dir), "--slice", "SLICE-01", "--status", "specified"]) == 0
    capsys.readouterr()
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    assert ret == 0

    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    slice_file.write_text(slice_file.read_text(encoding="utf-8") + "\nWidened scope.\n", encoding="utf-8")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("not a pure Core status write: body changed" in row for row in data["violations"])


def test_leash_rejects_a_hand_set_slice_status(tmp_path: Path, repo_root: Path, capsys):
    """Without the Core's receipt a status edit outside the envelope is just a
    hand edit."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-506", title="Hand").step_intake().step_analyze()
    builder._core_advance("analyzed")
    _git_init_commit(tmp_path)
    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    slice_file.write_text(
        slice_file.read_text(encoding="utf-8").replace("status: draft", "status: specified", 1),
        encoding="utf-8",
    )
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("SLICE-01.md" in row for row in data["violations"])


def test_leash_accepts_a_state_rewrite_of_a_slug_named_task(tmp_path: Path, repo_root: Path, capsys):
    """The Core rewrote TASK-001-<slug>.md through `state` and the leash looked
    for TASK-001.md, so the rewrite read as a hand edit. The receipt now names
    the file."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-507", title="Slug")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.rename(task.with_name("TASK-001-penalty-config.md"))
    _git_init_commit(tmp_path)

    assert main(["state", str(builder.change_dir), "--task", "TASK-001", "--status", "declared"]) == 0
    capsys.readouterr()
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    assert ret == 0


def test_leash_ignores_interpreter_caches(tmp_path: Path, repo_root: Path, capsys):
    """q0 run 20260921T111852Z: running the Red test wrote
    src/ratelimit/__pycache__/*.pyc, and the leash refused declare over it."""
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_baseline(tmp_path)
    (
        MockChangeBuilder(tmp_path, change_id="CHG-508", title="Caches")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    ret, data = _leash_json(
        tmp_path,
        capsys,
        files=[
            "src/ratelimit/__pycache__/limiter.cpython-314.pyc",
            "tests/__pycache__/test_penalty.cpython-314-pytest-9.0.pyc",
            ".pytest_cache/v/cache/lastfailed",
        ],
    )
    assert ret == 0, data
    assert data["ok"] is True


def test_task_forbidding_docs_keeps_the_changes_own_files(tmp_path: Path, repo_root: Path, capsys):
    """q0 run 20260921T130115Z: every task forbade `docs/**`, which removed
    evidence/, coverage.yaml and change.yaml from the declare and implement
    envelopes - the evidence `deltafuse evidence` writes read as a violation."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-509", title="Forbid docs")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(
        task.read_text(encoding="utf-8").replace(
            "forbidden_paths: [src/secret.py]", 'forbidden_paths: [src/secret.py, "docs/**"]'
        ),
        encoding="utf-8",
    )
    ret, data = _next_json(tmp_path, capsys)
    assert ret == 0
    write = data["envelope"]["write"]
    assert data["envelope"]["step"] == "declare"
    assert "docs/changes/*/evidence/red/**" in write
    assert "docs/changes/*/change.yaml" in write
    assert "src/secret.py" not in write
