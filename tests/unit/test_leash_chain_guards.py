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


def test_a_deletion_is_the_humans_only_for_its_own_archived_copy(tmp_path: Path, repo_root: Path):
    """df-leash #8: after `decide --gap`, a deleted file was the human's when its bytes matched ANY file in
    the receipted archive, so a copy of src/victim.py dropped there made its deletion "the human's"."""
    from deltafuse.core.decide import apply_decision
    from deltafuse.core.leash_run import leash_at_advance
    from tests.unit.test_decide_without_commit import _enforce, _git_commit_all
    from tests.unit.test_gap_reopen import _gap_found

    root = tmp_path / "p"
    root.mkdir()
    builder = _gap_found(root, repo_root)
    victim = root / "src" / "victim.py"
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text("def keep():\n    return 42\n", encoding="utf-8")
    _enforce(root)
    _git_commit_all(root)
    apply_decision(builder.change_dir, status="reopened", gap="spec-gap", note="row missing")
    _git_commit_all(root)

    data = victim.read_bytes()
    victim.unlink()
    assert run_leash(root)["violations"], "control: a src/ deletion in Analyze is refused"
    smuggle = builder.change_dir / "reopened" / "verify.1" / "evidence" / "green" / "TASK-999.yaml"
    smuggle.parent.mkdir(parents=True, exist_ok=True)
    smuggle.write_bytes(data)
    payload = run_leash(root)
    assert any("src/victim.py" in v for v in payload["violations"]), payload
    assert leash_at_advance(builder.change_dir, root)["violations"]


def test_a_declared_task_keeps_its_allowed_paths(tmp_path: Path, repo_root: Path):
    """df-leash #9: in Implement the Worker widened its own task's allowed_paths through the Writer
    (task.descriptor.yaml: updatable) and the envelope, read from the working file, followed."""
    import pytest

    from deltafuse.core.artifact_write import write_artifact
    from deltafuse.core.artifacts import ArtifactServiceError
    from deltafuse.core.transitions import set_artifact_status

    root, builder = _declared(tmp_path, repo_root)
    set_artifact_status(builder.change_dir, status="implementing", task_id="TASK-001")
    for field, value in (("allowed_paths", ["src/core.py", "src/billing.py"]), ("forbidden_paths", [])):
        with pytest.raises(ArtifactServiceError, match=field):
            write_artifact(builder.change_dir, "task", identity="TASK-001", fields={field: value})


def test_the_implement_envelope_is_the_declared_tasks(tmp_path: Path, repo_root: Path):
    """The envelope reads allowed_paths as the task had them when declared (at the base), not as the
    working file has them now."""
    root, builder = _declared(tmp_path, repo_root)
    task = builder.change_dir / "tasks" / "TASK-001.md"
    text = task.read_text(encoding="utf-8")
    assert "- src/core.py\n" in text, text
    task.write_text(text.replace("- src/core.py\n", "- src/core.py\n- src/billing.py\n"), encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "billing.py").write_text("PRICE = 0\n", encoding="utf-8")
    payload = run_leash(root)
    assert any("src/billing.py" in v for v in payload["violations"]), payload


def test_a_pending_task_still_takes_new_allowed_paths(tmp_path: Path, repo_root: Path):
    from deltafuse.core.artifact_write import write_artifact
    from deltafuse.core.frontmatter import parse_frontmatter

    from tests.unit.test_artifact_writer_guards import TASK, _specified

    # Audit 2026-11-17 (FW-3): in Decompose, where tasks are written. This test wrote TASK-003 into
    # a Change past the `declaring` gate; a task or its paths added there opened a write envelope
    # the decomposed gate never checked, and the Writer refuses both now.
    builder = _specified(tmp_path, repo_root)
    write_artifact(builder.change_dir, "task", identity="TASK-003", fields=dict(TASK), body="P\n")
    write_artifact(builder.change_dir, "task", identity="TASK-003", fields={"allowed_paths": ["src/other.py", "src/more.py"]})
    meta, _ = parse_frontmatter((builder.change_dir / "tasks" / "TASK-003.md").read_text(encoding="utf-8"))
    assert meta["allowed_paths"] == ["src/other.py", "src/more.py"]
