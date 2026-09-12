"""DF3-001 red acceptance tests for accepted AU-001 P0/P1 findings.

Each test pins one accepted audit hypothesis as a minimal reproducer.
Still-red tests are `xfail(strict=True)` per test: red now, and they flip the
suite the moment the owning DF3-00x card fixes the behavior (an unexpected
pass fails CI). F-01 and F-02 already flipped green when DF3-002 fixed the
archiver and the route-aware converged gate.

Threat class per test:
- accidental_misuse: an honest Worker following skills hits a deadlock or a
  dead route (F-03, F-04, B-01; F-02 fixed by DF3-002).
- adversarial_worker: a Worker with the capabilities a host grants it games
  gates, evidence, the journal or the bench (B-04, SEC-02, SEC-03, SEC-04,
  C-01; F-01 fixed by DF3-002).

SEC-01 (CI leash diffs empty HEAD on a clean PR checkout) has no test here:
its subject, ``process/templates/.github/workflows/deltafuse-leash.yml``, has
in-flight uncommitted edits from a parallel branch, so a file-content test
would be unstable. The reproducer is owned by DF3-003 (CI diff + manifest).

No implementation changes in this module (DF3-001 contract).
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from deltafuse.bench.journal import collect_attempts
from deltafuse.core.archiver import ArchivalError, archive_change
from deltafuse.core.decide import apply_decision
from deltafuse.core.fsm import check_gate, find_repo_root
from deltafuse.core.queue import build_work_queue, select_next
from tests.fixtures.change_builder import MockChangeBuilder

# ---------------------------------------------------------------- F-01 (P0)


def test_f01_archive_cannot_skip_gate_by_hand_set_converged(
    tmp_path: Path, repo_root: Path
):
    """adversarial_worker: hand-set ``status: converged`` must not bypass the
    converged gate on archive."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-901", title="Bypass")
    builder.step_intake()
    builder._update_change_yaml({"status": "converged"})

    with pytest.raises(ArchivalError):
        archive_change(builder.change_dir, repo_root=tmp_path)


# ---------------------------------------------------------------- F-02 (P0)


def test_f02_converged_gate_does_not_demand_regression_for_docs_route(
    tmp_path: Path, repo_root: Path
):
    """accidental_misuse: a fully verified ``route: docs`` Change must reach the
    converged gate without product-source regression evidence."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(
        tmp_path, change_id="CHG-902", title="Docs converge", route="docs"
    ).step_intake().step_analyze().step_specify().step_decompose()
    builder.step_declare().step_implement().step_verify()

    # Drop the regression leg the code route expects; a docs change has none.
    for cov in (builder.change_dir / "coverage.yaml",):
        if cov.is_file():
            data = yaml.safe_load(cov.read_text(encoding="utf-8")) or {}
            for claim in (data.get("claims") or {}).values():
                if isinstance(claim, dict) and "regression" in (claim.get("evidence") or {}):
                    del claim["evidence"]["regression"]
            cov.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    regression_dir = builder.change_dir / "evidence" / "regression"
    if regression_dir.is_dir():
        shutil.rmtree(regression_dir)

    errors = check_gate(builder.change_dir, "converged")
    assert errors == []


# ---------------------------------------------------------------- F-03 (P0)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_f03_spec_rejection_moves_change_out_of_specification_proposed(
    tmp_path: Path, repo_root: Path
):
    """accidental_misuse: after a human rejects the spec, change.yaml must leave
    ``specification-proposed`` so the lifecycle converges instead of spinning."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-903", title="Spec reject")
        .step_intake()
        .step_analyze()
    )
    # Write the Specify stage by hand: step_specify() auto-accepts via decide,
    # which is exactly the happy path the rejection deadlock hides behind.
    (builder.change_dir / "spec-delta.md").write_text(
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01]\n"
        "added: []\n"
        "modified: []\n"
        "removed: []\n"
        "---\n\n# Spec Delta\nDetails\n",
        encoding="utf-8",
    )
    builder._update_change_yaml({"status": "specification-proposed"})

    apply_decision(builder.change_dir, status="rejected", spec=True)

    data = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )
    assert data["status"] != "specification-proposed"


# ---------------------------------------------------------------- F-04 (P1)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_f04_passing_analyzed_gate_advances_status_out_of_draft(
    tmp_path: Path, repo_root: Path
):
    """accidental_misuse: once gate ``analyzed`` passes, change.yaml must carry
    ``status: analyzed`` (Core-owned) so through-mode does not re-run Analyze."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(
        tmp_path, change_id="CHG-904", title="Analyzed loop"
    ).step_intake().step_analyze()
    builder._update_change_yaml({"status": "draft"})

    assert check_gate(builder.change_dir, "analyzed") == []
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None and selected.skill == "specify"
    data = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )
    assert data["status"] == "analyzed"


# ---------------------------------------------------------------- B-01 (P0)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_b01_wheel_package_data_covers_schemas_and_templates(repo_root: Path):
    """accidental_misuse: an installed wheel must ship process/schemas and
    process/templates so the CLI works after ``pip install deltafuse``."""
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    tool = pyproject.get("tool", {}).get("setuptools", {})
    packages = tool.get("packages") or []
    package_data = tool.get("package-data") or {}
    as_text = repr(packages) + repr(package_data)
    assert "process" in as_text, (
        "wheel package data must include process/schemas and process/templates"
    )


# ---------------------------------------------------------------- B-04 (P1)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_b04_synthetic_green_command_is_not_authentic_evidence(
    tmp_path: Path, repo_root: Path
):
    """adversarial_worker: a green stamp produced by an arbitrary ``python -c``
    command that never runs the product test runner must be rejected."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-905", title="Synthetic green")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_declare()
    )
    from deltafuse.core.evidence import run_evidence

    outcome = run_evidence(
        builder.change_dir,
        phase="green",
        task="TASK-001",
        argv=[sys.executable, "-c", "print('green')"],
        changed_paths=["src/feature.py"],
    )
    assert outcome.errors, "synthetic command must not produce authentic green"
    assert not outcome.authentic


# ---------------------------------------------------------------- SEC-02 (P0)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_sec02_framework_hash_covers_core_source(tmp_path: Path):
    """adversarial_worker: tampering with src/deltafuse/** must change the
    framework content hash (lock verification must see Core code)."""
    from deltafuse.core.hasher import compute_framework_content_hash

    root = tmp_path / "framework"
    (root / "docs").mkdir(parents=True)
    (root / "process").mkdir()
    (root / "src" / "deltafuse" / "core").mkdir(parents=True)
    (root / "docs" / "workflow.md").write_text("canon\n", encoding="utf-8")
    core_file = root / "src" / "deltafuse" / "core" / "fsm.py"
    core_file.write_text("state = 'safe'\n", encoding="utf-8")

    before = compute_framework_content_hash(root)
    core_file.write_text("state = 'tampered'\n", encoding="utf-8")
    after = compute_framework_content_hash(root)

    assert before != after
    assert hashlib.sha256(b"nonempty").hexdigest()  # hashlib wired


# ---------------------------------------------------------------- SEC-03 (P0)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_sec03_gate_journal_is_inside_the_worker_write_boundary():
    """adversarial_worker: a Worker write to ``.deltafuse/gate-journal.jsonl``
    must be a leash violation; today the path is neither exempt nor covered by
    any envelope, so ``check_paths`` lets it pass silently."""
    from deltafuse.core.leash import check_paths

    violations = check_paths([".deltafuse/gate-journal.jsonl"])
    assert violations, "gate journal writes must not slip past check_paths"


# ---------------------------------------------------------------- SEC-04 (P1)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_sec04_task_envelope_cannot_escape_slice(tmp_path: Path, repo_root: Path):
    """adversarial_worker: task ``allowed_paths`` outside the slice
    ``target_paths`` must be rejected, not merged into the write envelope."""
    install = pytest.importorskip("deltafuse.core.installer").install
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-906", title="Envelope escape")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task_file = next((builder.change_dir / "tasks").glob("*.md"))
    meta_text = task_file.read_text(encoding="utf-8")
    assert "docs/changes/" in meta_text  # fixture sanity

    expanded = meta_text.replace(
        "allowed_paths:", "allowed_paths:\n    - src/**\n    - ."
    )
    task_file.write_text(expanded, encoding="utf-8")

    from deltafuse.core.queue import build_work_queue

    item = select_next(build_work_queue(tmp_path))
    assert item is None, "a task that expands its envelope must not be ready"

    errors = check_gate(builder.change_dir, "decomposed")
    assert errors, "decomposed gate must flag task paths outside the slice"


# ---------------------------------------------------------------- C-01 (P0)


@pytest.mark.xfail(strict=True, reason="DF3-001 red acceptance: fix lands in the owning DF3-00x card")
def test_c01_gate_spam_does_not_inflate_process_score():
    """adversarial_worker: repeatedly querying an already-passed gate must not
    count as forward progress; bench process score rewards unique transitions."""
    spam = [
        {"cmd": "check-gate", "gate": "converged", "ok": True, "seq": i}
        for i in range(20)
    ]
    journal = collect_attempts(spam)
    # v3 contract: only unique forward transitions count as attempts; spam must
    # not read as 20 clean cycles driving process = (attempts-retries)/attempts.
    assert journal["events"] <= 1 or journal["retries"]["check_gate"] >= 19, (
        "repeated already-passed gate queries inflate the process score"
    )
