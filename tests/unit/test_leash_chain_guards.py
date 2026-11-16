"""Audit 2026-11-16 (df-leash): which envelopes the receipt chain opens, and what a human decision vouches for."""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.installer import install
from deltafuse.core.leash_run import run_leash
from tests.fixtures.change_builder import MockChangeBuilder
from tests.fixtures.git import git


def _set_leash(root: Path, mode: str) -> None:
    cfg = root / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    data["workflow"]["leash"] = mode
    cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _declared(tmp_path: Path, repo_root: Path) -> tuple[Path, MockChangeBuilder]:
    """TASK-001 (src/core.py) declared, gate `declaring` passed: the ready step is implement TASK-001.
    TASK-002 (src/other.py) is still pending: never declared, no Red."""
    root = tmp_path / "prod"
    root.mkdir()
    install(target_dir=root, framework_root=repo_root)
    _set_leash(root, "enforce")
    builder = MockChangeBuilder(root, change_id="CHG-001", title="t")
    builder.step_intake().step_analyze().step_specify().step_decompose(tasks=[
        {"id": "TASK-001", "slice": "SLICE-01", "depends_on": [], "allowed_paths": ["src/core.py"]},
        {"id": "TASK-002", "slice": "SLICE-01", "depends_on": ["TASK-001"], "allowed_paths": ["src/other.py"]},
    ])
    builder.step_declare("TASK-001")
    builder._core_advance("declaring")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "base")
    return root, builder


def test_control_another_tasks_product_path_is_refused(tmp_path: Path, repo_root: Path):
    root, _ = _declared(tmp_path, repo_root)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")
    assert run_leash(root)["violations"]


def test_junk_evidence_opens_no_task_envelope(tmp_path: Path, repo_root: Path):
    """df-leash #7: any dirty file at evidence/green/TASK-002.yaml opened TASK-002's Implement envelope,
    so src/other.py of a task never declared passed."""
    root, builder = _declared(tmp_path, repo_root)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")
    green = builder.change_dir / "evidence" / "green" / "TASK-002.yaml"
    green.parent.mkdir(parents=True, exist_ok=True)
    green.write_text("anything: at all\n", encoding="utf-8")
    payload = run_leash(root)
    assert any("src/other.py" in v for v in payload["violations"]), payload


def test_junk_evidence_opens_nothing_while_the_human_decides(tmp_path: Path, repo_root: Path):
    root, builder = _declared(tmp_path, repo_root)
    dec = root / "docs" / "decisions" / "DEC-001.md"
    dec.parent.mkdir(parents=True, exist_ok=True)
    dec.write_text("---\nid: DEC-001\nchange: CHG-001\nstatus: proposed\n---\n# D\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "decision pending")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "core.py").write_text("x = 1\n", encoding="utf-8")
    green = builder.change_dir / "evidence" / "green" / "TASK-001.yaml"
    green.parent.mkdir(parents=True, exist_ok=True)
    green.write_text("junk: 1\n", encoding="utf-8")
    payload = run_leash(root)
    assert any("src/core.py" in v for v in payload["violations"]), payload


def test_a_core_written_record_of_another_task_does_not_open_this_ones(tmp_path: Path, repo_root: Path):
    """A stamped record is the task's only when it names that task and phase."""
    root, builder = _declared(tmp_path, repo_root)
    red = (builder.change_dir / "evidence" / "red" / "TASK-001.yaml").read_bytes()
    forged = builder.change_dir / "evidence" / "green" / "TASK-002.yaml"
    forged.parent.mkdir(parents=True, exist_ok=True)
    forged.write_bytes(red)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")
    payload = run_leash(root)
    assert any("src/other.py" in v for v in payload["violations"]), payload
