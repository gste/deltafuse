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


def _frontmatter_example(skill: Path) -> dict:
    text = skill.read_text(encoding="utf-8")
    block = re.search(r"```yaml\n(.*?)```", text, re.S)
    assert block, f"{skill} shows no frontmatter example"
    body = "\n".join(
        line.strip() for line in block.group(1).splitlines() if line.strip() != "---"
    )
    return yaml.safe_load(body)


@pytest.mark.parametrize("skill, schema", [("specify", "spec-delta"), ("decompose", "task")])
def test_skill_frontmatter_example_passes_its_schema(repo_root: Path, skill: str, schema: str):
    example = _frontmatter_example(repo_root / "process" / "skills" / skill / "SKILL.md")
    assert default_registry.validate(schema, example) == []


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
