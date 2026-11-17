"""What the human's `decide` writes is the Core's, also before anyone commits it.

Fuse-Back, Maven J01 (2026-10-21, GAP-REOPEN-COMMIT): after `decide --gap spec-gap --status
reopened` the Worker ran `advance --gate analyzed` and the enforce leash refused it: the gap-reopen
receipt read as "not a Core transition receipt", and the Green/regression records `decide` moved
to the archive and the spec-delta.md it set back to `proposed` read as writes outside the analyze
envelope. Committing made the same advance pass. The bench commits after every human decision,
so it never saw this; a product's host need not commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from deltafuse.core.decide import apply_decision
from deltafuse.core.leash_run import leash_at_advance
from deltafuse.core.transitions import advance_change, set_artifact_status
from tests.fixtures.change_builder import record_green_attempt
from tests.unit.test_gap_reopen import _gap_found


def _git_commit_all(root: Path) -> None:
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    if not (root / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "-m", "step"], cwd=root, check=True, capture_output=True)


def _enforce(root: Path) -> None:
    config = root / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["workflow"]["leash"] = "enforce"
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_the_analyzed_gate_passes_after_a_gap_reopen_nobody_committed(tmp_path: Path, repo_root: Path):
    builder = _gap_found(tmp_path, repo_root)
    _enforce(tmp_path)
    _git_commit_all(tmp_path)

    apply_decision(builder.change_dir, status="reopened", gap="spec-gap", note="the catalogue row is missing")
    leash = leash_at_advance(builder.change_dir, tmp_path)
    assert leash is not None and leash["checked"], leash
    assert leash["violations"] == [], leash["violations"]
    advance_change(builder.change_dir, "analyzed")


def test_the_gap_pass_is_committed_after_the_analyzed_gate(tmp_path: Path, repo_root: Path):
    """2026-10-27, an owner's service: the reopen committed, the gap pass's routing and the coverage
    the `analyzed` gate wrote were refused at the commit, judged against Specify alone - the chain
    since base ran from Verify back to Specify, and a chain going backwards added no envelope."""
    from deltafuse.core.leash import check_paths, collect_chain_envelopes, git_dirty_paths

    builder = _gap_found(tmp_path, repo_root)
    _enforce(tmp_path)
    _git_commit_all(tmp_path)
    apply_decision(builder.change_dir, status="reopened", gap="spec-gap", note="the catalogue row is missing")
    _git_commit_all(tmp_path)

    advance_change(builder.change_dir, "analyzed")
    coverage = builder.change_dir / "coverage.yaml"
    coverage.write_text(coverage.read_text(encoding="utf-8") + "# refreshed\n", encoding="utf-8")
    steps = {env.get("step") for env in collect_chain_envelopes(tmp_path, dirty=git_dirty_paths(tmp_path))}
    assert {"analyze", "specify"} <= steps, steps
    assert not [e for e in check_paths(["docs/changes/CHG-220/coverage.yaml"],
                                       collect_chain_envelopes(tmp_path), product_root=tmp_path)
                if "outside" in e]


def test_a_reopened_task_is_judged_as_the_humans_write_before_a_commit(tmp_path: Path, repo_root: Path):
    builder = _gap_found(tmp_path, repo_root)  # a Change in Implement with TASK-001's code written
    (builder.change_dir / "verification.md").unlink()
    _enforce(tmp_path)
    _git_commit_all(tmp_path)

    # Implement shows the oracle wrong: Green attempted, the task blocked; that is committed.
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("status: implemented", "status: declared"), encoding="utf-8")
    _git_commit_all(tmp_path)
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")
    _git_commit_all(tmp_path)

    apply_decision(builder.change_dir, status="reopened", task="TASK-001", note="the oracle contradicts itself")
    leash = leash_at_advance(builder.change_dir, tmp_path)
    assert leash is not None and leash["checked"], leash
    assert leash["violations"] == [], leash["violations"]


def test_a_hand_edit_after_the_decision_or_a_deletion_without_an_archive_is_still_refused(
    tmp_path: Path, repo_root: Path
):
    # Audit 2026-11-17 (FW-2, R4): two sibling products. The second used to be installed inside
    # the first one's repository - a product in a subdirectory, which `init` now refuses.
    first = tmp_path / "first"
    builder = _gap_found(first, repo_root)
    _enforce(first)
    _git_commit_all(first)
    (builder.change_dir / "evidence" / "green" / "TASK-001.yaml").unlink()  # nobody decided this
    violations = leash_at_advance(builder.change_dir, first)["violations"]
    assert any("evidence/green/TASK-001.yaml" in v for v in violations), violations

    _git_commit_all(first)
    builder = _gap_found(tmp_path / "second", repo_root)
    root = tmp_path / "second"
    _enforce(root)
    _git_commit_all(root)
    apply_decision(builder.change_dir, status="reopened", gap="spec-gap")
    spec_delta = builder.change_dir / "spec-delta.md"
    spec_delta.write_text(spec_delta.read_text(encoding="utf-8") + "\nA line nobody vouches for.\n", encoding="utf-8")
    violations = leash_at_advance(builder.change_dir, root)["violations"]
    assert any("spec-delta.md" in v for v in violations), violations


def test_decide_says_to_commit_after_a_reopen(tmp_path: Path, repo_root: Path, capsys):
    from deltafuse.cli import main

    builder = _gap_found(tmp_path, repo_root)
    assert main(["decide", str(builder.change_dir), "--gap", "spec-gap", "--status", "reopened"]) == 0
    assert "next: commit these changes before the next step" in capsys.readouterr().out
