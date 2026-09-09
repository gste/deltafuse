"""Mutational test suite verifying that DeltaFuse FSM & gatekeeper catch semantic defects T1-T8."""

from pathlib import Path
import pytest
import yaml
from deltafuse.core.fsm import check_gate, validate_change_package
from deltafuse.core.archiver import archive_change, ArchivalError
from deltafuse.core.installer import install
from deltafuse.core.hasher import compute_product_baseline_revision
from tests.fixtures.change_builder import MockChangeBuilder


def test_mutation_t1_green_evidence_in_red_folder_rejected(tmp_path: Path):
    """T1: Green evidence file placed in evidence/red/ directory must be rejected."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-201", title="T1 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    green_fake = {
        "schema_version": 2,
        "change": "CHG-201",
        "task": "TASK-001",
        "phase": "green",  # Deliberate mismatch with red/ directory
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest tests/",
        "exit_code": 0,
        "result": "passed",
        "summary": "Faked green evidence in red folder",
        "changed_paths": ["src/core.py"],
        "spec_status": "unchanged",
        "base_revision": compute_product_baseline_revision(tmp_path),
    }
    (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(green_fake), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("phase mismatch" in e for e in errs)
    gate_errs = check_gate(builder.change_dir, "targeting")
    assert any("phase mismatch" in e for e in gate_errs)


def test_mutation_t2_red_evidence_with_passed_result_rejected(tmp_path: Path):
    """T2: Red evidence with result=passed and exit_code=0 must be rejected."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-202", title="T2 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    passed_red = {
        "schema_version": 2,
        "change": "CHG-202",
        "task": "TASK-001",
        "phase": "red",
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest tests/test_task.py",
        "exit_code": 0,
        "result": "passed",  # Deliberate violation of red invariant
        "failure_category": "behavioral-mismatch",
        "summary": "Test passed in red phase",
        "changed_paths": ["tests/test_task.py"],
        "spec_status": "unchanged",
    }
    (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(passed_red), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("red evidence must have result 'expected-failure'" in e for e in errs)
    assert any("red evidence must have non-zero exit_code" in e for e in errs)


def test_mutation_t3_converged_gate_fails_with_pending_tasks(tmp_path: Path):
    """T3: Gate converged must fail if any task is still in 'pending' status."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-203", title="T3 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
    )
    # Revert task frontmatter back to pending
    from deltafuse.core.frontmatter import parse_frontmatter
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["status"] = "pending"
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

    # Add verification artifacts
    (builder.change_dir / "verification.md").write_text("# Verification", encoding="utf-8")
    ver_dir = builder.change_dir / "evidence" / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    (ver_dir / "run.yaml").write_text(yaml.safe_dump({
        "schema_version": 2, "change": "CHG-203", "phase": "verification",
        "timestamp": "2026-09-05T12:00:00Z", "command": "pytest", "exit_code": 0,
        "result": "passed", "summary": "Passed", "changed_paths": [], "spec_status": "unchanged",
        "base_revision": compute_product_baseline_revision(tmp_path),
    }), encoding="utf-8")

    gate_errs = check_gate(builder.change_dir, "converged")
    assert any("has non-terminal status 'pending'" in e for e in gate_errs)


def test_mutation_t4_evidence_for_nonexistent_task_rejected(tmp_path: Path):
    """T4: Evidence referencing nonexistent TASK-999 must be rejected."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-204", title="T4 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    phantom_evidence = {
        "schema_version": 2,
        "change": "CHG-204",
        "task": "TASK-999",  # Nonexistent task
        "phase": "red",
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest tests/phantom.py",
        "exit_code": 1,
        "result": "expected-failure",
        "failure_category": "behavioral-mismatch",
        "summary": "Phantom task test",
        "changed_paths": ["tests/phantom.py"],
        "spec_status": "unchanged",
    }
    (red_dir / "TASK-999.yaml").write_text(yaml.safe_dump(phantom_evidence), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("references nonexistent task 'TASK-999'" in e for e in errs)


def test_mutation_t5_status_mismatch_rejected(tmp_path: Path):
    """T5: change.yaml claiming status 'normalized' with decomposed tasks/evidence must be rejected."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-205", title="T5 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    # Force change.yaml status back to normalized
    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["status"] = "normalized"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("Status mismatch" in e and "normalized" in e for e in errs)


def test_mutation_t7_broken_spec_anchor_rejected(tmp_path: Path):
    """T7: spec_refs pointing to nonexistent anchor in docs/spec must be rejected."""
    # Ensure docs/spec exists with core.md containing only REQ-01
    spec_dir = tmp_path / "docs" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "core.md").write_text("# Spec\n## REQ-01\nValid requirement\n", encoding="utf-8")

    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-207", title="T7 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    # Point task to a broken anchor #REQ-GHOST-999
    from deltafuse.core.frontmatter import parse_frontmatter
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["spec_refs"] = ["docs/spec/core.md#REQ-GHOST-999"]
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("Anchor '#REQ-GHOST-999' not found in specification file" in e for e in errs)


def test_mutation_f004_path_traversal_rejected(tmp_path: Path):
    """F-004 / RM-004: spec_refs that resolve outside repo_root must fail the package gate."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside_spec.md"
    outside.write_text("# leaked\n## REQ-LEAK\n", encoding="utf-8")
    spec_dir = repo / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "core.md").write_text("# Spec\n## REQ-01\nValid requirement\n", encoding="utf-8")

    builder = (
        MockChangeBuilder(repo, change_id="CHG-204", title="F-004 Traversal")
        .step_intake()
        .step_analyze()
    )
    from deltafuse.core.frontmatter import parse_frontmatter
    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["spec_refs"] = ["../outside_spec.md"]
    slice_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("Path traversal forbidden" in e for e in errs)


def test_mutation_t8_rearchive_collision_fails(tmp_path: Path):
    """T8: Re-archiving a Change when target archive directory exists must fail with ArchivalError (no rmtree)."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-208", title="T8 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
        .step_verify()
    )
    # First archive succeeds
    archived_dir = archive_change(builder.change_dir, repo_root=tmp_path)
    assert archived_dir.is_dir()

    # Recreate the same change directory
    builder2 = (
        MockChangeBuilder(tmp_path, change_id="CHG-208", title="T8 Collision Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
        .step_verify()
    )
    with pytest.raises(ArchivalError) as exc_info:
        archive_change(builder2.change_dir, repo_root=tmp_path)

    assert "Overwriting historical archive records is strictly prohibited" in str(exc_info.value)
    # Ensure original archive wasn't wiped
    assert archived_dir.is_dir()


def test_mutation_n10_missing_spec_root_fails(tmp_path: Path):
    """N10: If docs/spec directory does not exist, spec_refs must not be silently skipped."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-210", title="N10 Mutation Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    # Delete docs/spec directory
    import shutil
    spec_dir = tmp_path / "docs" / "spec"
    if spec_dir.exists():
        shutil.rmtree(spec_dir)

    errs = validate_change_package(builder.change_dir)
    assert any("Specification root directory 'docs/spec' not found" in e for e in errs)


def test_mutation_t4_evidence_with_empty_tasks_directory_rejected(tmp_path: Path):
    """T4 edge-case: evidence referencing task when tasks/ has no tasks must fail."""
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-211", title="Empty Tasks T4 Test")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    # Note: decompose was not run, tasks/ does not exist or is empty
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    phantom_evidence = {
        "schema_version": 2,
        "change": "CHG-211",
        "task": "TASK-001",  # No tasks exist in package!
        "phase": "red",
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest",
        "exit_code": 1,
        "result": "expected-failure",
        "summary": "Phantom",
        "changed_paths": ["tests/test.py"],
        "spec_status": "unchanged",
    }
    (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(phantom_evidence), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("references nonexistent task 'TASK-001'" in e for e in errs)


def test_mutation_lock_hash_mismatch_rejected(tmp_path: Path, repo_root: Path):
    """P7.3: change.yaml framework hash mismatch with .deltafuse/lock.yaml must be rejected."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-212", title="Lock Hash Mismatch")
    builder.step_intake()

    # Tamper with framework content_hash in change.yaml
    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["framework"]["content_hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert any("Framework content hash mismatch" in e for e in errs)
