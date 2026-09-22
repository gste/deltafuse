"""Roadmap item 1: the Worker writes structure only through `deltafuse artifact write`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deltafuse.cli import main
from deltafuse.core.artifact_write import split_envelope, write_artifact
from deltafuse.core.artifacts import ArtifactServiceError
from deltafuse.core.installer import install
from deltafuse.core.leash import structural_kind, vouched_digests, hand_written_errors
from tests.fixtures.change_builder import MockChangeBuilder
from tests.unit.test_leash import _commit_all, _git_init_commit, _leash_diff

TASK = {
    "slice": "SLICE-01",
    "title": "Penalty parameter",
    "kind": "feature",
    "depends_on": [],
    "requirement_delta": "none",
    "spec_refs": ["docs/spec/core.md#REQ-01"],
    "allowed_paths": ["src/app.py"],
    "forbidden_paths": [],
}


@pytest.mark.parametrize(
    "rel, kind",
    [
        ("docs/changes/CHG-001-x/routing.yaml", "routing"),
        ("docs/changes/CHG-001-x/spec-delta.md", "spec-delta"),
        ("docs/changes/CHG-001-x/slices/SLICE-01.md", "slice"),
        ("docs/changes/CHG-001-x/tasks/TASK-001.md", "task"),
        ("docs/changes/CHG-001-x/request.md", None),
        ("docs/changes/CHG-001-x/change.yaml", None),
        ("docs/changes/CHG-001-x/evidence/red/TASK-001.yaml", None),
        ("docs/spec/security/ratelimit.md", None),
    ],
)
def test_structural_kinds(rel: str, kind: str | None):
    assert structural_kind(rel) == kind


def test_the_envelope_takes_fields_nested_or_flat():
    assert split_envelope({"identity": "TASK-001", "fields": {"a": 1}, "body": "p"}) == ("TASK-001", None, {"a": 1}, "p")
    assert split_envelope({"target": "tasks/TASK-001.md", "a": 1}) == (None, "tasks/TASK-001.md", {"a": 1}, None)
    with pytest.raises(ArtifactServiceError, match="prose"):
        split_envelope({"identity": "X", "body": {"not": "prose"}})


def _specified(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=change_id, title="Writer")
    builder.step_intake().step_analyze().step_specify()
    _git_init_commit(tmp_path)
    return builder


def test_write_creates_then_updates_and_defaults_the_budget(tmp_path: Path, repo_root: Path):
    builder = _specified(tmp_path, repo_root, "CHG-601")
    created = write_artifact(builder.change_dir, "task", identity="TASK-009", fields=dict(TASK), body="Prose.\n")
    task = builder.change_dir / "tasks" / "TASK-009.md"
    assert created["operation"] == "create" and task.is_file()
    text = task.read_text(encoding="utf-8")
    assert "max_tokens: 64000" in text and "Prose." in text

    updated = write_artifact(
        builder.change_dir, "task", identity="TASK-009",
        fields={"slice": "SLICE-01", "allowed_paths": ["src/app.py", "tests/test_app.py"]},
    )
    assert updated["operation"] == "update"
    text = task.read_text(encoding="utf-8")
    assert "tests/test_app.py" in text and "Prose." in text  # body kept


def test_the_leash_accepts_writer_output_and_refuses_a_hand_edit(tmp_path: Path, repo_root: Path, capsys):
    builder = _specified(tmp_path, repo_root, "CHG-602")
    write_artifact(builder.change_dir, "task", identity="TASK-009", fields=dict(TASK), body="Prose.\n")
    rel = (builder.change_dir / "tasks" / "TASK-009.md").relative_to(tmp_path).as_posix()
    assert hand_written_errors(tmp_path, rel, head=None, vouched=vouched_digests(tmp_path)) == []

    task = tmp_path / rel
    task.write_text(task.read_text(encoding="utf-8").replace("feature", "bugfix"), encoding="utf-8")
    errors = hand_written_errors(tmp_path, rel, head=None, vouched=vouched_digests(tmp_path))
    assert errors and "deltafuse artifact write --kind task" in errors[0]


def test_a_core_status_write_is_vouched_by_its_receipt(tmp_path: Path, repo_root: Path):
    from deltafuse.core.transitions import append_receipt

    install(target_dir=tmp_path, framework_root=repo_root)
    task = tmp_path / "docs" / "changes" / "CHG-603-x" / "tasks" / "TASK-001.md"
    task.parent.mkdir(parents=True)
    task.write_bytes(b"---\nid: TASK-001\nstatus: declaring\n---\n")
    import hashlib

    append_receipt(tmp_path, {
        "kind": "artifact-status", "change": "CHG-603-x", "artifact": "task",
        "artifact_id": "TASK-001", "from": "pending", "to": "declaring",
        "recorded": "2026-09-22T00:00:00Z",
        "path": "docs/changes/CHG-603-x/tasks/TASK-001.md",
        "sha256": hashlib.sha256(task.read_bytes()).hexdigest(),
    })
    rel = "docs/changes/CHG-603-x/tasks/TASK-001.md"
    assert hand_written_errors(tmp_path, rel, head=None, vouched=vouched_digests(tmp_path)) == []


def test_cli_write_reports_create_and_a_precise_refusal(tmp_path: Path, repo_root: Path, capsys):
    builder = _specified(tmp_path, repo_root, "CHG-604")
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"identity": "TASK-009", "fields": TASK, "body": "Prose.\n"}), encoding="utf-8")
    assert main(["artifact", "write", "--kind", "task", "--change", str(builder.change_dir), "--input", str(good)]) == 0
    assert "create" in capsys.readouterr().out

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"identity": "TASK-010", "fields": {**TASK, "kind": "code"}}), encoding="utf-8")
    assert main(["artifact", "write", "--kind", "task", "--change", str(builder.change_dir), "--input", str(bad)]) == 2
    err = capsys.readouterr().err
    assert "'code' is not one of" in err
    assert not (builder.change_dir / "tasks" / "TASK-010.md").exists()


def test_leash_diff_flags_a_hand_written_task_in_the_envelope(tmp_path: Path, repo_root: Path, capsys):
    builder = _specified(tmp_path, repo_root, "CHG-605")
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    write_artifact(builder.change_dir, "task", identity="TASK-009", fields=dict(TASK), body="Prose.\n")
    ret, data = _leash_diff(tmp_path, capsys)
    assert data["violations"] == [], data["violations"]
    _commit_all(tmp_path, "writer task")

    hand = builder.change_dir / "tasks" / "TASK-010.md"
    hand.write_text((builder.change_dir / "tasks" / "TASK-009.md").read_text(encoding="utf-8").replace("TASK-009", "TASK-010"), encoding="utf-8")
    ret, data = _leash_diff(tmp_path, capsys)
    assert ret == 1
    assert any("TASK-010.md' was written by hand" in row for row in data["violations"])


DECISION = {
    "title": "Store penalties in memory or in Redis",
    "kind": "architecture",
    "affects": {"capabilities": ["system.core"], "spec_refs": ["docs/spec/core.md"]},
}


def test_a_decision_gets_the_next_id_and_its_change(tmp_path: Path, repo_root: Path):
    import yaml as _yaml

    from deltafuse.core.frontmatter import parse_frontmatter

    builder = _specified(tmp_path, repo_root, "CHG-610")
    receipt = write_artifact(builder.change_dir, "decision", fields=dict(DECISION), body="## Question\n\nWhere?\n")
    assert receipt["operation"] == "create"
    folder = tmp_path / "docs" / "decisions"
    created = sorted(p.name for p in folder.glob("DEC-*.md") if p.name != "DEC-0000-template.md")
    assert created == ["DEC-0001.md"]
    meta, body = parse_frontmatter((folder / "DEC-0001.md").read_text(encoding="utf-8"))
    assert meta["id"] == "DEC-0001" and meta["change"] == "CHG-610" and meta["status"] == "proposed"
    assert meta["owner"] == "human" and "Where?" in body
    change = _yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert "DEC-0001" in change["decisions"]
    write_artifact(builder.change_dir, "decision", fields=dict(DECISION))
    assert (folder / "DEC-0002.md").is_file()


def test_a_decided_decision_is_the_humans(tmp_path: Path, repo_root: Path):
    from deltafuse.core.decide import apply_decision

    builder = _specified(tmp_path, repo_root, "CHG-611")
    write_artifact(builder.change_dir, "decision", fields=dict(DECISION))
    write_artifact(builder.change_dir, "decision", identity="DEC-0001", fields={"title": "Sharper question"})
    apply_decision(tmp_path, status="accepted", decision="DEC-0001")
    with pytest.raises(ArtifactServiceError, match="the human's"):
        write_artifact(builder.change_dir, "decision", identity="DEC-0001", fields={"title": "Rewrite history"})


def test_the_leash_vouches_writer_and_decide_and_refuses_a_hand_written_decision(tmp_path: Path, repo_root: Path):
    from deltafuse.core.decide import apply_decision

    builder = _specified(tmp_path, repo_root, "CHG-612")
    rel = "docs/decisions/DEC-0001.md"
    write_artifact(builder.change_dir, "decision", fields=dict(DECISION))
    assert structural_kind(rel) == "decision"
    assert hand_written_errors(tmp_path, rel, head=None, vouched=vouched_digests(tmp_path)) == []
    apply_decision(tmp_path, status="accepted", decision="DEC-0001")
    assert hand_written_errors(tmp_path, rel, head=None, vouched=vouched_digests(tmp_path)) == []

    hand = tmp_path / "docs" / "decisions" / "DEC-0002.md"
    hand.write_text((tmp_path / rel).read_text(encoding="utf-8").replace("DEC-0001", "DEC-0002"), encoding="utf-8")
    errors = hand_written_errors(tmp_path, "docs/decisions/DEC-0002.md", head=None, vouched=vouched_digests(tmp_path))
    assert errors and "--kind decision" in errors[0]
