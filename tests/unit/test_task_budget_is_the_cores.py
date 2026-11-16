"""A task's context budget is the product's, and a glob counts what it covers.

Audit 2026-11-16 (df-evidence #11): the decomposed gate read the ceiling from the task's own
`context_budget`, which the Worker writes - raised to 10 million tokens, any task passed - and a
glob in allowed_paths counted as one file of zero tokens however much it covered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core.artifact_write import write_artifact
from deltafuse.core.artifacts import ArtifactServiceError
from deltafuse.core.context import validate_task_context_budget
from deltafuse.core.fsm import validate_change_package
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

BIG = ["src/big/m%02d.py" % i for i in range(30)]


def _big_tree(root: Path) -> None:
    (root / "src" / "big").mkdir(parents=True, exist_ok=True)
    for rel in BIG:
        (root / rel).write_text("x = 1\n", encoding="utf-8")


def test_a_glob_counts_the_files_it_covers(tmp_path: Path):
    _big_tree(tmp_path)
    budget = {"max_tokens": 64000, "max_files": 24}
    errors = validate_task_context_budget(budget, [], ["src/**"], tmp_path)
    assert any("30 files loaded" in e for e in errors), errors
    assert validate_task_context_budget(budget, [], ["src/big/m0*.py"], tmp_path) == []


def test_the_gate_uses_the_products_ceiling(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-250", title="Budget").step_intake().step_analyze()
    builder.step_specify().step_decompose([{"id": "TASK-001", "slice": "SLICE-01", "depends_on": [],
                                             "allowed_paths": BIG}])
    _big_tree(tmp_path)
    task = builder.change_dir / "tasks" / "TASK-001.md"
    text = task.read_text(encoding="utf-8")
    assert "max_files: 24" in text
    before = [e for e in validate_change_package(builder.change_dir) if "budget" in e]
    assert before
    task.write_text(text.replace("max_files: 24", "max_files: 1000"), encoding="utf-8")
    after = [e for e in validate_change_package(builder.change_dir) if "budget" in e]
    assert after == before


def test_the_writer_refuses_a_budget_from_the_worker(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-251", title="Budget").step_intake().step_analyze()
    builder.step_specify()
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    fields = {"title": "T", "kind": "feature", "slice": "SLICE-01", "depends_on": [], "requirement_delta": "added",
              "spec_refs": ["docs/spec/core.md#REQ-01"], "allowed_paths": ["src/core.py"], "forbidden_paths": []}
    with pytest.raises(ArtifactServiceError, match="context_budget is the Core's"):
        write_artifact(builder.change_dir, "task", identity="TASK-009",
                       fields={**fields, "context_budget": {"max_tokens": 10_000_000, "max_files": 1000}})
    write_artifact(builder.change_dir, "task", identity="TASK-009", fields=fields)
    created = (builder.change_dir / "tasks" / "TASK-009.md").read_text(encoding="utf-8")
    assert "max_tokens: 64000" in created
    with pytest.raises(ArtifactServiceError, match="context_budget is the Core's"):
        write_artifact(builder.change_dir, "task", identity="TASK-009",
                       fields={"context_budget": {"max_tokens": 10_000_000, "max_files": 24}})
    # Restating the value the task has is not a change.
    write_artifact(builder.change_dir, "task", identity="TASK-009",
                   fields={"forbidden_paths": ["src/secret.py"], "context_budget": {"max_tokens": 64000, "max_files": 24}})
    assert "src/secret.py" in (builder.change_dir / "tasks" / "TASK-009.md").read_text(encoding="utf-8")
