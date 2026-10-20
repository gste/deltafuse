"""`workflow.code_roots` sets where a `code`-route Change may read and write.

Fuse-Back, J03 after Fuse-Back (2026-10-08): in a multi-module Maven repository the code and
tests live in `<module>/src/main/java` and `<module>/src/test/java`. Every phase contract named
only the root `src/**` and `tests/**`, so no Change there passed `decomposed`, and
`workflow.code_roots` - accepted by validate-config - was read by nothing. Without the key the
contracts are what they were.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.context import code_write_globs, phase_allowed_paths, phase_write_globs
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.leash import is_product_path, task_envelope_errors, unreachable_green_errors
from tests.fixtures.change_builder import MockChangeBuilder

MODULE_TASK = {
    "id": "TASK-001",
    "slice": "SLICE-01",
    "depends_on": [],
    "allowed_paths": ["svc/src/main/java/A.java", "svc/src/test/java/ATest.java"],
}
REFUSALS = ("outside the phase contract", "outside what this Change may write", "may change no product file")


def _set_code_roots(product: Path, roots: list[str] | None) -> None:
    config = product / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    workflow = data.setdefault("workflow", {})
    if roots is None:
        workflow.pop("code_roots", None)
    else:
        workflow["code_roots"] = roots
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _module_product(tmp_path: Path, repo_root: Path, roots: list[str] | None) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    _set_code_roots(tmp_path, roots)
    for rel in ("svc/src/main/java/A.java", "svc/src/test/java/ATest.java"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("class A {}\n", encoding="utf-8")
    return (
        MockChangeBuilder(tmp_path, change_id="CHG-190", title="Module code")
        .step_intake()
        .step_analyze()
        .step_specify()
    )


def _write_task(builder: MockChangeBuilder) -> None:
    tasks = builder.change_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / "TASK-001.md").write_text(
        "---\nid: TASK-001\nchange: CHG-190\nslice: SLICE-01\nkind: feature\nstatus: pending\n"
        "depends_on: []\nrequirement_delta: modified\nspec_refs: [docs/spec/core.md#REQ-01]\n"
        f"design_ref: null\nallowed_paths: {MODULE_TASK['allowed_paths']}\nforbidden_paths: []\n"
        "context_budget: {max_tokens: 16000, max_files: 24}\n---\n\n# TASK-001\n",
        encoding="utf-8",
    )


def test_task_envelope_takes_the_configured_roots(tmp_path: Path, repo_root: Path):
    builder = _module_product(tmp_path, repo_root, ["svc/src/**"])
    _write_task(builder)
    assert task_envelope_errors(builder.change_dir) == []

    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("svc/src/main/java/A.java", "other/B.java"), encoding="utf-8")
    errors = task_envelope_errors(builder.change_dir)
    assert len(errors) == 1 and "'other/B.java'" in errors[0] and "svc/src/**" in errors[0]


def test_phase_globs_follow_the_configured_roots(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    default_write = phase_write_globs("implement", "code", tmp_path)
    assert "src/**" in default_write and "tests/**" in default_write
    assert code_write_globs(tmp_path) == ("src/**", "tests/**")

    _set_code_roots(tmp_path, ["svc/src/**"])
    write = phase_write_globs("implement", "code", tmp_path)
    assert "svc/src/**" in write and "src/**" not in write and "tests/**" not in write
    read = phase_allowed_paths("implement", "read", tmp_path)
    assert "svc/src/**" in read and "src/**" not in read
    assert "svc/src/**" in phase_allowed_paths("declare", "read", tmp_path)
    assert "svc/src/**" in phase_allowed_paths("verify", "read", tmp_path)
    # docs/ops routes keep their own globs
    assert phase_write_globs("implement", "ops", tmp_path) == phase_write_globs("implement", "ops")


def test_a_module_file_is_a_product_file(tmp_path: Path, repo_root: Path):
    builder = _module_product(tmp_path, repo_root, ["svc/src/**"])
    _write_task(builder)
    assert unreachable_green_errors(builder.change_dir) == []
    assert is_product_path("svc/src/main/java/A.java", product_root=tmp_path)
    assert not is_product_path("svc/src/main/java/A.java")  # without the product: as before
    assert is_product_path("src/x.py") and not is_product_path("src/x.py", product_root=tmp_path)


def test_next_json_implement_envelope_names_the_module(tmp_path: Path, repo_root: Path, capsys):
    builder = _module_product(tmp_path, repo_root, ["svc/src/**"])
    builder.step_decompose(tasks=[MODULE_TASK]).step_declare()
    builder._core_advance("declaring")
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: declared", "status: implementing"), encoding="utf-8")
    assert main(["next", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr()[0])
    envelope = data["envelope"]
    assert envelope["step"] == "implement"
    assert "svc/src/**" in envelope["read"] and "src/**" not in envelope["read"]
    assert "svc/src/main/java/A.java" in envelope["write"]


def test_the_module_change_passes_decomposed(tmp_path: Path, repo_root: Path):
    """The reproduction from CHANGE-WRITE-PATHS.md: the three refusals are gone with the key."""
    builder = _module_product(tmp_path, repo_root, None)
    _write_task(builder)
    without = check_gate(builder.change_dir, "decomposed")
    assert all(any(r in e for e in without) for r in REFUSALS), without

    _set_code_roots(tmp_path, ["svc/src/**"])
    with_roots = check_gate(builder.change_dir, "decomposed")
    assert not any(r in e for e in with_roots for r in REFUSALS), with_roots
