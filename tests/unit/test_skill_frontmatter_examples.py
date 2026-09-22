"""Worker-facing frontmatter shapes: the skills' examples pass the schemas, and
schema errors name the whole expected shape.

q0 runs on 2026-09-21 spent most retries on frontmatter format: `spec-delta.md`
without `added` / `modified` / `removed` (the specify skill named them only as
upper-case body sections), tasks without `change` / `slice` or with
`kind: code`. An error names only the first failing rule, so the Worker fixed
one key per retry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from deltafuse.core.fsm import validate_change_package
from deltafuse.core.installer import install
from deltafuse.core.schemas import default_registry
from tests.fixtures.change_builder import MockChangeBuilder


def _json_examples(skill: Path) -> list[dict]:
    """Every ```json block of a skill: the Artifact Writer inputs it teaches."""
    text = skill.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\s*\n(.*?)```", text, re.S)
    assert blocks, f"{skill} shows no Writer input example"
    return [json.loads(block) for block in blocks]


PLACEHOLDERS = {
    "<domain>.<capability>": "system.core",
    "docs/spec/<domain>/<capability>.md": "docs/spec/core.md",
    "#REQ-ID": "#REQ-01",
    "src/<module>.py": "src/app.py",
    "tests/test_<module>.py": "tests/test_app.py",
}


def _concrete(example: dict) -> dict:
    text = json.dumps(example)
    for placeholder, value in PLACEHOLDERS.items():
        text = text.replace(placeholder, value)
    return json.loads(text)


def test_the_skills_writer_examples_are_accepted_by_the_writer(tmp_path: Path, repo_root: Path):
    """Roadmap item 1: the skills teach Writer inputs, not frontmatter. Each
    example, with its placeholders filled, must pass the Writer as taught - in
    lifecycle order, on one Change."""
    from deltafuse.core.artifact_write import split_envelope, write_artifact

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-800", title="Examples").step_intake()
    for skill, kinds in (("analyze", ["routing", "slice"]), ("specify", ["spec-delta"]), ("decompose", ["task"])):
        examples = _json_examples(repo_root / "process" / "skills" / skill / "SKILL.md")
        assert len(examples) == len(kinds), skill
        for example, kind in zip(examples, kinds):
            identity, target, fields, body = split_envelope(_concrete(example))
            receipt = write_artifact(builder.change_dir, kind, identity=identity, target=target, fields=fields, body=body)
            assert receipt["operation"] == "create", (skill, kind)


def test_task_schema_error_names_the_whole_shape(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-801", title="Shape")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(
        task.read_text(encoding="utf-8").replace("kind: feature", "kind: code"),
        encoding="utf-8",
    )
    errors = validate_change_package(builder.change_dir)
    hint = [e for e in errors if "expected frontmatter keys" in e]
    assert hint and hint[0].startswith("TASK-001.md: ")
    assert "kind (feature|bugfix|refactor|maintenance|documentation)" in hint[0]
    assert "change" in hint[0] and "slice" in hint[0]


def test_spec_delta_schema_error_names_the_whole_shape(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-802", title="Shape").step_intake().step_analyze()
    (builder.change_dir / "spec-delta.md").write_text(
        "---\nchange: CHG-802\nstatus: proposed\n---\n# Spec\n", encoding="utf-8"
    )
    errors = validate_change_package(builder.change_dir)
    assert any(
        "spec-delta.md: expected frontmatter keys: change, status" in e
        and "added (list, may be empty)" in e
        for e in errors
    ), errors


def test_routing_claim_error_names_the_claim_shape(tmp_path: Path, repo_root: Path):
    """q0 run M03 20260921T212331Z: `kind` in a routing claim, three times."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-803", title="Shape").step_intake().step_analyze()
    routing_file = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
    for claim in routing["claims"].values():
        claim["kind"] = "feature"
    routing_file.write_text(yaml.safe_dump(routing), encoding="utf-8")
    errors = validate_change_package(builder.change_dir)
    assert any(
        e.startswith("routing.yaml: expected keys for each claim: primary_capability")
        and "confidence (low|medium|high|unknown)" in e
        and "no other keys" in e
        for e in errors
    ), errors


def test_unquoted_colon_in_yaml_says_to_quote_the_value(tmp_path: Path, repo_root: Path):
    """q0 run M03 20260921T212331Z: twelve refusals in a row on
    `summary: Backward compatible: ...` before the Worker quoted it."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-804", title="Colon").step_intake().step_analyze()
    routing_file = builder.change_dir / "routing.yaml"
    routing_file.write_text(
        routing_file.read_text(encoding="utf-8").replace(
            "summary: Claim CR-001", "summary: Backward compatible: callers keep working"
        ),
        encoding="utf-8",
    )
    errors = validate_change_package(builder.change_dir)
    assert any(
        e.startswith("routing.yaml parsing error") and "must be quoted" in e for e in errors
    ), errors


@pytest.mark.parametrize("skill, gate", [("declare", "declaring"), ("implement", "implemented")])
def test_per_task_skills_close_the_change_gate_only_when_next_says_so(repo_root: Path, skill: str, gate: str):
    """q0 run M01 20260921T232218Z: the skills said to close the gate at the
    end of every step, one task each; the gate covers all tasks, so each task
    but the last cost a refused check-gate (T3)."""
    text = (repo_root / "process" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "do not check it after each task" in text
    assert f"deltafuse check-gate <change-dir> --gate {gate}" in text
