"""Worker-facing frontmatter shapes: the skills' examples pass the schemas, and
schema errors name the whole expected shape.

q0 runs on 2026-09-21 spent most retries on frontmatter format: `spec-delta.md`
without `added` / `modified` / `removed` (the specify skill named them only as
upper-case body sections), tasks without `change` / `slice` or with
`kind: code`. An error names only the first failing rule, so the Worker fixed
one key per retry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from deltafuse.core.fsm import validate_change_package
from deltafuse.core.installer import install
from deltafuse.core.schemas import default_registry
from tests.fixtures.change_builder import MockChangeBuilder


def _yaml_examples(skill: Path) -> list[dict]:
    """Every ```yaml block of a skill, dedented, without its '---' frame."""
    text = skill.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.S)
    assert blocks, f"{skill} shows no yaml example"
    out = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip() and line.strip() != "---"]
        indent = min(len(line) - len(line.lstrip()) for line in lines)
        out.append(yaml.safe_load("\n".join(line[indent:] for line in lines)))
    return out


@pytest.mark.parametrize(
    "skill, schemas",
    [("specify", ["spec-delta"]), ("decompose", ["task"]), ("analyze", ["routing", "slice"])],
)
def test_skill_yaml_examples_pass_their_schemas(repo_root: Path, skill: str, schemas: list[str]):
    examples = _yaml_examples(repo_root / "process" / "skills" / skill / "SKILL.md")
    assert len(examples) == len(schemas)
    for example, schema in zip(examples, schemas):
        assert default_registry.validate(schema, example) == [], schema


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
