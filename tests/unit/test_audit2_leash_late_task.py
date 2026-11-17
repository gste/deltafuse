"""Audit 2026-11-17 (df-leash), FW-3: a task that did not exist when Decompose closed opens no
write envelope, whoever wrote it."""

from __future__ import annotations

import sys

import yaml

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, ORACLE, TASK_FIELDS, cli, commit, leash, product_at, put, walk, write,
)

WIDE = {**TASK_FIELDS, "title": "helper", "requirement_delta": "none", "allowed_paths": ["src/**"]}
TASK_002 = f"docs/changes/{CHANGE}/tasks/TASK-002.md"


def _outside(violations: list[str]) -> list[str]:
    return [v for v in violations if "src/existing.py" in v]


def test_control_implement_of_task_001_does_not_cover_another_product_file(product_at):
    root, _ = product_at("declared")
    put(root, "src/existing.py", "X = 'edited outside TASK-001'\n")
    code, data = leash(root)
    assert code == 1 and _outside(data["violations"]), data


def test_the_writer_refuses_a_new_task_after_decompose(product_at):
    """FW-3: in Implement the Worker added TASK-002 with `allowed_paths: [src/**]` through the Writer;
    its file being changed, the chain opened its envelope and every product file was writable."""
    root, change = product_at("declared")
    code, out = write(root, "task", {"identity": "TASK-002", "fields": WIDE, "body": "helper"}, check=False)
    assert code != 0, out
    assert "Decompose" in out, out
    assert not (change / "tasks" / "TASK-002.md").exists()


def test_the_writer_creates_tasks_until_the_decomposed_gate_closes(product_at):
    root, change = product_at("decomposed")
    code, out = write(root, "task", {"identity": "TASK-002", "fields": WIDE, "body": "helper"}, check=False)
    assert code != 0, out  # the gate is closed: the task set is the one it checked
    root, change = product_at("specified", "q")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS, "body": "b"})
    write(root, "task", {"identity": "TASK-002", "fields": {**TASK_FIELDS, "title": "second"}, "body": "b"})
    assert (change / "tasks" / "TASK-002.md").is_file()


def _late_task_through_the_writer(root, monkeypatch) -> None:
    """A Writer-vouched TASK-002 created after Decompose: the leash's own rule, without the Writer's."""
    from deltafuse.core import artifacts

    monkeypatch.setattr(artifacts, "late_task_error", lambda *a, **k: None)
    write(root, "task", {"identity": "TASK-002", "fields": WIDE, "body": "helper"})
    monkeypatch.undo()


def test_a_task_created_after_decompose_opens_no_envelope(product_at, monkeypatch):
    """The leash itself, whatever let the task file through."""
    root, change = product_at("declared")
    put(root, "src/existing.py", "X = 'edited outside TASK-001'\n")
    _late_task_through_the_writer(root, monkeypatch)
    assert (root / TASK_002).is_file()
    code, data = leash(root)
    assert code == 1 and _outside(data["violations"]), data
    # the hook, and `advance` at the end of the step
    assert commit(root, "widen", verify=True).returncode != 0
    from deltafuse.core.leash_run import leash_at_advance

    commit(root, "widen")  # --no-verify: `advance` judges the step's commits too
    verdict = leash_at_advance(change, root)
    assert verdict["checked"] and _outside(verdict["violations"]), verdict


def test_a_hand_written_late_task_opens_no_envelope(product_at):
    """The same trick with a file tool instead of the Writer."""
    root, change = product_at("declared")
    put(root, "src/existing.py", "X = 'edited outside TASK-001'\n")
    first = (change / "tasks" / "TASK-001.md").read_text(encoding="utf-8")
    head, body = first.split("---\n", 2)[1:]
    meta = yaml.safe_load(head)
    meta.update(id="TASK-002", status="pending", allowed_paths=["src/**"], requirement_delta="none")
    put(root, TASK_002, "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body)
    code, data = leash(root)
    assert code == 1 and _outside(data["violations"]), data
    assert any("TASK-002.md" in v and "by hand" in v for v in data["violations"]), data


def test_a_late_task_does_not_become_the_ready_envelope_either(product_at, monkeypatch):
    """With TASK-001 implemented the queue's next ready item is the new pending task's Declare."""
    root, change = product_at("declared")
    put(root, "src/app.py", "BANNER = 'hello'\n")
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", sys.executable, "tests/test_banner.py")
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    commit(root, "task 1 implemented")
    _late_task_through_the_writer(root, monkeypatch)
    commit(root, "late task")  # --no-verify: the task file is at HEAD now, and still not declared in time
    put(root, "src/existing.py", "X = 'edited outside TASK-001'\n")
    put(root, "tests/test_other.py", "assert True\n")
    code, data = leash(root)
    assert code == 1 and _outside(data["violations"]), data


def test_decompose_declare_and_implement_in_one_uncommitted_diff_stay_inside(product_at):
    """The legitimate walk without a commit between steps: the task is new since the base, and the
    base is before Decompose closed - its envelope opens."""
    root, change = product_at("specified")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS, "body": "Print the banner."})
    cli("advance", change, "--gate", "decomposed")
    put(root, "tests/test_banner.py", ORACLE)
    run = [sys.executable, "tests/test_banner.py"]
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    cli("advance", change, "--gate", "declaring")
    put(root, "src/app.py", "BANNER = 'hello'\n")
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    cli("advance", change, "--gate", "implemented")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data
    assert commit(root, "three steps", verify=True).returncode == 0


def test_a_pending_task_past_decompose_keeps_its_paths_in_the_writer(tmp_path, repo_root):
    """The nearest way round: not a new task, but new paths for one that is still pending while
    another task is in Implement (df-leash #9 froze the paths only once the task left `pending`)."""
    import pytest

    from deltafuse.core.artifact_write import write_artifact
    from deltafuse.core.artifacts import ArtifactServiceError
    from tests.unit.test_leash_chain_guards import _declared

    root, builder = _declared(tmp_path, repo_root)  # TASK-002 (src/other.py) is pending
    with pytest.raises(ArtifactServiceError, match="allowed_paths"):
        write_artifact(builder.change_dir, "task", identity="TASK-002", fields={"allowed_paths": ["src/**"]})


def test_a_pending_task_past_decompose_keeps_its_paths_in_the_leash(tmp_path, repo_root):
    from deltafuse.core.leash_run import run_leash
    from tests.unit.test_leash_chain_guards import _declared

    root, builder = _declared(tmp_path, repo_root)
    task = builder.change_dir / "tasks" / "TASK-002.md"
    text = task.read_text(encoding="utf-8")
    assert "[src/other.py]" in text, text
    task.write_text(text.replace("[src/other.py]", "[src/other.py, src/billing.py]"), encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "billing.py").write_text("PRICE = 0\n", encoding="utf-8")
    payload = run_leash(root)
    assert any("src/billing.py" in v for v in payload["violations"]), payload
