import pytest
from pathlib import Path
import shutil
import yaml
from deltafuse.core.fsm import (
    validate_change_package,
    check_gate,
    can_transition,
    missing_analyze_artifacts,
    VALID_CHANGE_STATUSES,
)
from deltafuse.core.archiver import is_change_id_archived
from deltafuse.core.installer import install
from deltafuse.core.frontmatter import parse_frontmatter
from tests.fixtures.change_builder import MockChangeBuilder


def test_validate_empty_directory(tmp_path: Path):
    errors = validate_change_package(tmp_path)
    assert any("Missing required change.yaml" in e for e in errors)


def test_check_gate_lifecycle(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / "docs" / "changes" / "CHG-001-test"
    change_dir.mkdir(parents=True)

    # 1. Intake state
    assert len(check_gate(change_dir, "intake")) > 0

    (change_dir / "request.md").write_text("# Request\nCR-001: Implement feature", encoding="utf-8")
    change_yaml_content = (
        "schema_version: 2\n"
        "id: CHG-001\n"
        "title: Test change\n"
        "status: normalized\n"
        "framework:\n"
        "  version: 2.0.0\n"
        f"  content_hash: {yaml.safe_load((tmp_path / '.deltafuse' / 'lock.yaml').read_text(encoding='utf-8'))['framework']['content_hash']}\n"
        "intent: feature\n"
        "risk: low\n"
        "source:\n"
        "  request: request.md\n"
        "  intake_refs: []\n"
        "deltas: []\n"
        "slices: []\n"
        "decisions: []\n"
        "tasks: []\n"
        "verification: null\n"
    )
    (change_dir / "change.yaml").write_text(change_yaml_content, encoding="utf-8")

    assert check_gate(change_dir, "intake") == []
    assert len(check_gate(change_dir, "analyzed")) > 0


def test_fsm_canonical_statuses_and_transitions():
    assert len(VALID_CHANGE_STATUSES) == 18
    assert "specification-proposed" in VALID_CHANGE_STATUSES
    assert "blocked-on-decision" in VALID_CHANGE_STATUSES

    # Canonical transitions
    assert can_transition("normalized", "analyzing")
    assert can_transition("analyzing", "blocked-on-decision")
    assert can_transition("blocked-on-decision", "analyzing")
    assert can_transition("analyzing", "analyzed")
    assert can_transition("analyzed", "specification-proposed")
    assert can_transition("analyzed", "targeting")  # Bug path
    assert can_transition("specification-proposed", "specified")
    assert can_transition("specified", "decomposed")
    assert can_transition("decomposed", "targeting")
    assert can_transition("targeting", "target-confirmed")
    assert can_transition("target-confirmed", "implementing")
    assert can_transition("implementing", "implemented")
    assert can_transition("implemented", "verifying")
    assert can_transition("verifying", "converged")
    assert can_transition("converged", "archived")

    # Terminal transitions
    assert can_transition("normalized", "rejected")
    assert can_transition("normalized", "duplicate")
    assert can_transition("targeting", "not-reproduced")

    # Forbidden transitions
    assert not can_transition("normalized", "converged")
    assert not can_transition("decomposed", "converged")
    assert not can_transition("archived", "analyzing")
    assert not can_transition("rejected", "normalized")


def test_decision_blocking_gate(tmp_path: Path, repo_root: Path):
    """Verifies that an unresolved proposed decision blocks the analyzed/specified gate."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / "docs" / "changes" / "CHG-001-test"
    change_dir.mkdir(parents=True)
    (change_dir / "request.md").write_text("# Request\nCR-001: Implement feature", encoding="utf-8")
    (change_dir / "routing.yaml").write_text(yaml.safe_dump({"change": "CHG-001", "claims": {"CR-001": {"summary": "S", "primary_capability": "system.core", "confidence": "high"}}}), encoding="utf-8")
    (change_dir / "coverage.yaml").write_text(yaml.safe_dump({"change": "CHG-001", "claims": {"CR-001": {"slice": "SLICE-01", "status": "pending"}}}), encoding="utf-8")
    slices_dir = change_dir / "slices"
    slices_dir.mkdir(parents=True)
    (slices_dir / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-001\ntitle: S\nstatus: draft\nprimary_capability: c\nclaims: [CR-001]\n---\n# S\n",
        encoding="utf-8"
    )
    change_yaml = {
        "schema_version": 2,
        "id": "CHG-001",
        "title": "Test change",
        "status": "analyzed",
        "framework": {"version": "2.0.0", "content_hash": yaml.safe_load((tmp_path / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8"))["framework"]["content_hash"]},
        "source": {"request": "request.md"},
        "analysis": {"routing": "routing.yaml", "summary": "analysis.md"},
        "deltas": [], "slices": [{"id": "SLICE-01", "status": "draft", "file": "slices/SLICE-01.md"}],
        "decisions": [], "tasks": []
    }
    (change_dir / "change.yaml").write_text(yaml.safe_dump(change_yaml), encoding="utf-8")

    # Create a proposed decision in docs/decisions
    dec_file = tmp_path / "docs" / "decisions" / "DEC-0001-db-choice.md"
    dec_file.write_text(
        "---\n"
        "id: DEC-0001\n"
        "title: DB Choice\n"
        "kind: architecture\n"
        "status: proposed\n"
        "owner: ghost\n"
        "change: CHG-001\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision details\n",
        encoding="utf-8"
    )

    errs = check_gate(change_dir, "analyzed")
    assert any("blocked-on-decision" in e and "DEC-0001" in e for e in errs)

    # Transition decision to accepted -> gate unblocked
    dec_file.write_text(
        "---\n"
        "id: DEC-0001\n"
        "title: DB Choice\n"
        "kind: architecture\n"
        "status: accepted\n"
        "owner: human\n"
        "change: CHG-001\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision details\n",
        encoding="utf-8"
    )
    assert not any("blocked-on-decision" in e for e in check_gate(change_dir, "analyzed"))


def test_is_change_id_archived(tmp_path: Path):
    arch_dir = tmp_path / "docs" / "archive" / "changes" / "2026-09-05-CHG-999"
    arch_dir.mkdir(parents=True)
    assert is_change_id_archived("CHG-999", tmp_path)
    assert not is_change_id_archived("CHG-888", tmp_path)


def test_task_design_ref_validation(tmp_path: Path):
    from tests.fixtures.change_builder import MockChangeBuilder
    from deltafuse.core.frontmatter import parse_frontmatter

    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-005", title="Design Ref Test")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["design_ref"] = "docs/decisions/DEC-0005-missing.md"
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")

    # 1. Nonexistent DEC file
    errs = validate_change_package(builder.change_dir)
    assert any("Referenced decision record does not exist" in e for e in errs)

    # 2. DEC file in proposed status
    dec_file = tmp_path / "docs" / "decisions" / "DEC-0005-missing.md"
    dec_file.parent.mkdir(parents=True, exist_ok=True)
    dec_file.write_text(
        "---\nid: DEC-0005\ntitle: D\nkind: architecture\nstatus: proposed\nowner: ghost\nchange: CHG-005\naffects: {capabilities: [c], spec_refs: []}\n---\n# D\n",
        encoding="utf-8"
    )
    errs = validate_change_package(builder.change_dir)
    assert any("must be 'accepted'" in e for e in errs)

    # 3. DEC file in accepted status
    dec_file.write_text(
        "---\nid: DEC-0005\ntitle: D\nkind: architecture\nstatus: accepted\nowner: ghost\nchange: CHG-005\naffects: {capabilities: [c], spec_refs: []}\n---\n# D\n",
        encoding="utf-8"
    )
    errs = validate_change_package(builder.change_dir)
    assert not any("Referenced decision" in e for e in errs)


def _write_security_ratelimit_catalog(root: Path) -> None:
    catalog = {
        "schema_version": 2,
        "domains": {
            "security": {
                "summary": "Security controls",
                "capabilities": {
                    "ratelimit": {
                        "summary": "Token bucket limiter",
                        "spec": ["docs/spec/security/ratelimit.md"],
                    }
                },
            }
        },
    }
    (root / "docs" / "spec" / "_capabilities.yaml").write_text(
        yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8"
    )


def _write_ratelimit_spec(root: Path) -> None:
    spec = root / "docs" / "spec" / "security" / "ratelimit.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Rate limit\n## REQ-RL-01\nLimiter MUST initialize a token bucket.\n", encoding="utf-8")


def _set_slice_capability(
    change_dir: Path,
    capability: str,
    spec_refs: list[str] | None = None,
    slice_id: str = "SLICE-01",
) -> None:
    slice_file = change_dir / "slices" / f"{slice_id}.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["primary_capability"] = capability
    if spec_refs is not None:
        meta["spec_refs"] = spec_refs
    slice_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")


def test_specified_rejects_missing_live_spec_and_invalid_catalog(tmp_path: Path, repo_root: Path):
    """F-010 / S01: spec-delta alone is not enough without ratelimit.md and a valid catalog."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-010", title="S01 vacuous specify")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    _set_slice_capability(builder.change_dir, "security.ratelimit", spec_refs=[])
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(
        "schema_version: 2\n"
        "domains:\n"
        "  rate-limiter:\n"
        "    capabilities:\n"
        "      token-bucket:\n"
        "        requirements: [CR-001]\n",
        encoding="utf-8",
    )
    errs = check_gate(builder.change_dir, "specified")
    assert any("docs/spec/_capabilities.yaml" in e for e in errs)
    assert not (tmp_path / "docs" / "spec" / "security" / "ratelimit.md").is_file()
    assert any("Capability 'security.ratelimit'" in e or "must be a mapping" in e
               or "required" in e.lower() or "summary" in e or "spec" in e for e in errs)


def test_specified_accepts_live_spec_and_catalog_without_code(tmp_path: Path, repo_root: Path):
    """Specified must not require product code; live spec + catalog is enough."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-011", title="Live specify")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    _write_ratelimit_spec(tmp_path)
    _write_security_ratelimit_catalog(tmp_path)
    _set_slice_capability(
        builder.change_dir,
        "security.ratelimit",
        spec_refs=["docs/spec/security/ratelimit.md#REQ-RL-01"],
    )
    spec_delta = (
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01]\n"
        "added: [docs/spec/security/ratelimit.md#REQ-RL-01]\n"
        "modified: []\n"
        "removed: []\n"
        "---\n\n# Spec Delta\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    assert check_gate(builder.change_dir, "specified") == []
    assert not (tmp_path / "src" / "ratelimit" / "limiter.py").exists()


def test_specified_none_requires_existing_anchors(tmp_path: Path, repo_root: Path):
    """S03: requirement_delta none is only valid with exact live spec_refs."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-012", title="Unchanged spec")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    assert check_gate(builder.change_dir, "specified") == []

    _set_slice_capability(builder.change_dir, "system.core", spec_refs=["docs/spec/core.md"])
    errs = check_gate(builder.change_dir, "specified")
    assert any("must include an existing anchor" in e for e in errs)


def test_specified_rejects_normalized_status(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-013", title="Status still normalized")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["status"] = "normalized"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")
    errs = check_gate(builder.change_dir, "specified")
    assert any("status must be 'specified' or 'specification-proposed'" in e for e in errs)


def test_specified_rejects_missing_usage_stats_file(tmp_path: Path, repo_root: Path):
    """F-010 / S05: catalog pointing at usage_stats.md fails specified if the file is absent."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-014", title="S05 missing stats spec")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    catalog = {
        "schema_version": 2,
        "domains": {
            "monitoring": {
                "summary": "Usage monitoring",
                "capabilities": {
                    "usage_stats": {
                        "summary": "Per-key usage statistics",
                        "spec": ["docs/spec/monitoring/usage_stats.md"],
                    }
                },
            }
        },
    }
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(
        yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8"
    )
    _set_slice_capability(
        builder.change_dir,
        "monitoring.usage_stats",
        spec_refs=["docs/spec/monitoring/usage_stats.md#REQ-US-01"],
    )
    spec_delta = (
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01]\n"
        "added: [docs/spec/monitoring/usage_stats.md#REQ-US-01]\n"
        "modified: []\n"
        "removed: []\n"
        "---\n\n# Spec Delta\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    errs = check_gate(builder.change_dir, "specified")
    assert any("usage_stats.md" in e and "does not exist" in e for e in errs)


def test_targeting_from_analyzed_skips_specify(tmp_path: Path, repo_root: Path):
    """AB-06 S04: targeting does not require spec-delta or the specified gate."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-015", title="Bugfix no specify")
        .step_intake()
        .step_analyze()
        .step_decompose()
        .step_target()
    )
    assert not (builder.change_dir / "spec-delta.md").is_file()
    assert check_gate(builder.change_dir, "targeting") == []


def test_targeting_accepts_already_green(tmp_path: Path, repo_root: Path):
    """F-009: public oracle already passing is already-green, not manufactured Red."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-016", title="Already green lift")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "def test_penalty_lifts_after_window():\n    assert True\n",
        encoding="utf-8",
    )
    red = yaml.safe_load((builder.change_dir / "evidence" / "red" / "TASK-001.yaml").read_text(encoding="utf-8"))
    red["exit_code"] = 0
    red["result"] = "already-green"
    red["summary"] = "Public oracle already passes; lift is present from TASK-001"
    red["changed_paths"] = ["tests/test_task-001.py"]
    (builder.change_dir / "evidence" / "red" / "TASK-001.yaml").write_text(
        yaml.safe_dump(red, sort_keys=False), encoding="utf-8"
    )
    assert check_gate(builder.change_dir, "targeting") == []


def test_targeting_rejects_private_red_test(tmp_path: Path, repo_root: Path):
    """F-009: Red tests must not poke _-prefixed product internals."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-017", title="Private red")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "def test_penalty_lifts_after_window(limiter):\n"
        "    limiter._blocked_until['u'] = 0.0\n"
        "    assert limiter.consume('u', 1) is True\n",
        encoding="utf-8",
    )
    red_file = builder.change_dir / "evidence" / "red" / "TASK-001.yaml"
    red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    red["changed_paths"] = ["tests/test_task-001.py"]
    red_file.write_text(yaml.safe_dump(red, sort_keys=False), encoding="utf-8")
    errs = check_gate(builder.change_dir, "targeting")
    assert any("private symbols" in e for e in errs)


def test_implemented_rejects_stale_green_after_spec_change(tmp_path: Path, repo_root: Path):
    """F-006 / RM-006: old green yaml must not pass after docs/spec changes."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-018", title="Stale green")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
    )
    assert check_gate(builder.change_dir, "implemented") == []

    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## REQ-STALE\n", encoding="utf-8")
    errs = check_gate(builder.change_dir, "implemented")
    assert any("stale evidence" in e for e in errs)

    from deltafuse.core.hasher import compute_product_baseline_revision
    fresh = compute_product_baseline_revision(tmp_path)
    for rel in ("green/TASK-001.yaml", "regression/TASK-001.yaml"):
        ev_file = builder.change_dir / "evidence" / rel
        data = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
        data["base_revision"] = fresh
        ev_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert check_gate(builder.change_dir, "implemented") == []


def _restamp_evidence(change_dir: Path, repo_root: Path) -> None:
    from deltafuse.core.hasher import compute_product_baseline_revision

    fresh = compute_product_baseline_revision(repo_root)
    evidence_dir = change_dir / "evidence"
    if not evidence_dir.is_dir():
        return
    for ev_file in evidence_dir.rglob("*.yaml"):
        data = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("phase") in {"green", "regression", "verification"}:
            data["base_revision"] = fresh
            ev_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_ops_spec_delta(
    change_dir: Path,
    change_id: str,
    *,
    added: list[str] | None = None,
    modified: list[str] | None = None,
    removed: list[str] | None = None,
) -> None:
    spec_delta = (
        "---\n"
        f"change: {change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01]\n"
        f"added: {added or []}\n"
        f"modified: {modified or []}\n"
        f"removed: {removed or []}\n"
        "---\n\n# Spec Delta\n"
    )
    (change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")


def test_converged_rejects_wiped_added_spec_after_specify(tmp_path: Path, repo_root: Path):
    """Q-008 / RM-008: deleting live spec after Specify must fail converged, not archive-merge."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-019", title="Wiped spec")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
        .step_verify()
    )
    _write_ratelimit_spec(tmp_path)
    _write_ops_spec_delta(
        builder.change_dir,
        builder.change_id,
        added=["docs/spec/security/ratelimit.md#REQ-RL-01"],
    )
    _restamp_evidence(builder.change_dir, tmp_path)
    assert check_gate(builder.change_dir, "converged") == []

    (tmp_path / "docs" / "spec" / "security" / "ratelimit.md").unlink()
    _restamp_evidence(builder.change_dir, tmp_path)
    errs = check_gate(builder.change_dir, "converged")
    assert any(
        "Gate converged" in e and "added" in e and "ratelimit.md" in e for e in errs
    )


def test_converged_rejects_removed_spec_still_on_disk(tmp_path: Path, repo_root: Path):
    """RM-008: spec-delta removed must actually be gone from docs/spec."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-020", title="Removed still live")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
        .step_verify()
    )
    legacy = tmp_path / "docs" / "spec" / "legacy.md"
    legacy.write_text("# Legacy\n## REQ-OLD\nRetired requirement.\n", encoding="utf-8")
    _write_ops_spec_delta(
        builder.change_dir,
        builder.change_id,
        removed=["docs/spec/legacy.md#REQ-OLD"],
    )
    _restamp_evidence(builder.change_dir, tmp_path)
    errs = check_gate(builder.change_dir, "converged")
    assert any("removed" in e and "still present" in e for e in errs)

    legacy.unlink()
    _restamp_evidence(builder.change_dir, tmp_path)
    assert check_gate(builder.change_dir, "converged") == []


def test_converged_without_spec_delta_skips_disk_check(tmp_path: Path, repo_root: Path):
    """S04: bugfix path may skip Specify; converged does not require spec-delta."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-021", title="Bugfix no specify")
        .step_intake()
        .step_analyze()
        .step_decompose()
        .step_target()
        .step_implement()
        .step_verify()
    )
    assert not (builder.change_dir / "spec-delta.md").is_file()
    assert check_gate(builder.change_dir, "converged") == []


def test_decomposed_rejects_task_without_budget(tmp_path: Path, repo_root: Path):
    """F-002 / RM-002: TASK without context_budget fails decomposed."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-022", title="No budget")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    assert check_gate(builder.change_dir, "decomposed") == []
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    del meta["context_budget"]
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    errs = check_gate(builder.change_dir, "decomposed")
    assert any("context_budget" in e for e in errs)


def test_decomposed_rejects_fifty_allowed_paths(tmp_path: Path, repo_root: Path):
    """F-002 / RM-002: 50 allowed_paths exceed max_files 24."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-023", title="Fifty files")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    allowed = []
    for i in range(50):
        (src / f"f{i:02d}.py").write_text("x = 1\n", encoding="utf-8")
        allowed.append(f"src/f{i:02d}.py")
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["allowed_paths"] = allowed
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    errs = check_gate(builder.change_dir, "decomposed")
    assert any("maximum allowed is 24" in e for e in errs)


def test_targeting_rejects_src_in_red_changed_paths(tmp_path: Path, repo_root: Path):
    """RM-002: Red evidence must not write src/** (PHASE_CONTRACTS target)."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-024", title="Red writes src")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
    )
    red_file = builder.change_dir / "evidence" / "red" / "TASK-001.yaml"
    red = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    red["changed_paths"] = ["src/core.py"]
    red_file.write_text(yaml.safe_dump(red, sort_keys=False), encoding="utf-8")
    errs = check_gate(builder.change_dir, "targeting")
    assert any("outside the phase contract" in e and "src/core.py" in e for e in errs)


def test_analyzed_still_requires_routing_slices_coverage(tmp_path: Path, repo_root: Path):
    """RM-002 regression: Analyze still requires routing+slices+coverage."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-025", title="Analyze artifacts")
    builder.step_intake()
    errs = check_gate(builder.change_dir, "analyzed")
    assert any("routing.yaml is missing" in e for e in errs)
    builder.step_analyze()
    assert missing_analyze_artifacts(builder.change_dir) == []
    assert check_gate(builder.change_dir, "analyzed") == []


def test_narrow_analyze_gate_after_full_set(tmp_path: Path, repo_root: Path):
    """RM-020: narrow may write three times; analyzed still waits for the set."""
    install(target_dir=tmp_path, framework_root=repo_root)
    lock_path = tmp_path / ".deltafuse" / "lock.yaml"
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    lock.setdefault("workflow", {})["call_width"] = "narrow"
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("workflow", {})["call_width"] = "narrow"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    builder = MockChangeBuilder(tmp_path, change_id="CHG-028", title="Narrow analyze")
    builder.step_intake()
    builder.step_analyze()
    (builder.change_dir / "coverage.yaml").unlink()
    slices = builder.change_dir / "slices"
    for slice_file in slices.glob("*.md"):
        slice_file.unlink()
    slices.rmdir()
    assert "routing.yaml" not in missing_analyze_artifacts(builder.change_dir)
    assert missing_analyze_artifacts(builder.change_dir) == ["slices/", "coverage.yaml"]
    errs = check_gate(builder.change_dir, "analyzed")
    assert any("slice file" in e for e in errs)
    assert any("coverage.yaml is missing" in e for e in errs)

    builder.step_analyze()
    assert check_gate(builder.change_dir, "analyzed") == []


def test_wide_analyze_one_step_closes_analyzed(tmp_path: Path, repo_root: Path):
    """RM-020: wide default may write the full Analyze set in one step."""
    install(target_dir=tmp_path, framework_root=repo_root)
    lock = yaml.safe_load((tmp_path / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8"))
    assert lock["workflow"]["call_width"] == "wide"
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-029", title="Wide analyze")
        .step_intake()
        .step_analyze()
    )
    assert missing_analyze_artifacts(builder.change_dir) == []
    assert check_gate(builder.change_dir, "analyzed") == []


def test_feature_analyzed_does_not_skip_specify(tmp_path: Path, repo_root: Path):
    """RM-020 / BM-01: call_width does not skip Specify for a feature Change."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-030", title="Tiny feature")
        .step_intake()
        .step_analyze()
    )
    errs = check_gate(builder.change_dir, "specified")
    assert any("spec-delta.md is missing" in e for e in errs)


def test_auto_accept_decisions_does_not_bypass_human_gate(tmp_path: Path, repo_root: Path):
    """Q-007 flag in lock: auto_accept_decisions true still blocks proposed DEC."""
    install(target_dir=tmp_path, framework_root=repo_root)
    lock_path = tmp_path / ".deltafuse" / "lock.yaml"
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    lock["workflow"]["auto_accept_decisions"] = True
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-031", title="DEC still human")
        .step_intake()
        .step_analyze()
    )
    dec_file = tmp_path / "docs" / "decisions" / "DEC-0002-choice.md"
    dec_file.write_text(
        "---\n"
        "id: DEC-0002\n"
        "title: Choice\n"
        "kind: architecture\n"
        "status: proposed\n"
        "owner: ghost\n"
        "change: CHG-031\n"
        "affects: {capabilities: [system.core], spec_refs: []}\n"
        "---\n# Decision details\n",
        encoding="utf-8",
    )
    errs = check_gate(builder.change_dir, "analyzed")
    assert any("blocked-on-decision" in e and "DEC-0002" in e for e in errs)


def test_analyzed_accepts_o1_e1_claims(tmp_path: Path, repo_root: Path):
    """F-008 / RM-018: S02-style O1/E1 in request.md must not be orphans at analyzed."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-027", title="S02 labels")
        .step_intake(claims=["O1", "E1"])
        .step_analyze()
    )
    from deltafuse.core.integrity import extract_claims_from_request
    request = (builder.change_dir / "request.md").read_text(encoding="utf-8")
    assert extract_claims_from_request(request) == ["O1", "E1"]
    assert check_gate(builder.change_dir, "analyzed") == []


def test_converged_accepts_cancelled_and_superseded_tasks(tmp_path: Path, repo_root: Path):
    """F-005 / RM-005: cancelled/superseded siblings do not block converged."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-026", title="Cancelled sibling")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose(
            tasks=[
                {"id": "TASK-001", "slice": "SLICE-01", "depends_on": []},
                {"id": "TASK-002", "slice": "SLICE-01", "depends_on": ["TASK-001"]},
            ]
        )
        .step_target()
        .step_implement()
        .step_verify()
    )
    task_file = builder.change_dir / "tasks" / "TASK-002.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["status"] = "cancelled"
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    assert check_gate(builder.change_dir, "converged") == []

    meta["status"] = "superseded"
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    assert check_gate(builder.change_dir, "converged") == []


def test_docs_route_targets_spec_without_src(tmp_path: Path, repo_root: Path):
    """RM-021 / S08b: docs route has no limiter.py or product pytest."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-032", title="Docs only", route="docs")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    assert check_gate(builder.change_dir, "specified") == []
    builder.step_decompose().step_target()
    assert check_gate(builder.change_dir, "targeting") == []
    red = yaml.safe_load((builder.change_dir / "evidence" / "red" / "TASK-001.yaml").read_text(encoding="utf-8"))
    assert red["changed_paths"] == ["docs/spec/core.md"]
    assert not (tmp_path / "src" / "ratelimit" / "limiter.py").exists()


def test_docs_route_rejects_src_allowed_paths(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-033", title="Docs forbids src", route="docs")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["allowed_paths"] = ["src/core.py"]
    task_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    errs = validate_change_package(builder.change_dir)
    assert any("src/**" in e or "outside the phase contract" in e for e in errs)


def test_docs_route_implemented_without_product_regression(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-034", title="Docs green", route="docs")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
    )
    shutil.rmtree(builder.change_dir / "evidence" / "regression")
    assert check_gate(builder.change_dir, "implemented") == []


def test_code_route_still_requires_regression(tmp_path: Path, repo_root: Path):
    """RM-021: do not weaken Implement for code Changes."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-035", title="Code still pytest")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_target()
        .step_implement()
    )
    shutil.rmtree(builder.change_dir / "evidence" / "regression")
    errs = check_gate(builder.change_dir, "implemented")
    assert any("Regression evidence" in e for e in errs)


def test_ops_route_writes_ops_files_not_src(tmp_path: Path, repo_root: Path):
    """RM-021 / S08c: ops files, spec/src need not change."""
    install(target_dir=tmp_path, framework_root=repo_root)
    ops_dir = tmp_path / "docs" / "ops"
    ops_dir.mkdir(parents=True, exist_ok=True)
    (ops_dir / "runbook.md").write_text("# Runbook\nhostname: limiter-prod-02\n", encoding="utf-8")
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-036", title="Ops migrate", route="ops")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    assert check_gate(builder.change_dir, "specified") == []
    builder.step_decompose().step_target()
    assert check_gate(builder.change_dir, "targeting") == []
    builder.step_implement()
    assert check_gate(builder.change_dir, "implemented") == []
    green = yaml.safe_load((builder.change_dir / "evidence" / "green" / "TASK-001.yaml").read_text(encoding="utf-8"))
    assert green["changed_paths"] == ["docs/ops/runbook.md"]
    assert not any(p.startswith("src/") for p in green["changed_paths"])


def test_missing_route_defaults_to_code(tmp_path: Path, repo_root: Path):
    """S02/S03: omit route; still a code Change."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-037", title="Default code")
        .step_intake()
        .step_analyze()
    )
    change = yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))
    routing = yaml.safe_load((builder.change_dir / "routing.yaml").read_text(encoding="utf-8"))
    assert "route" not in change
    assert "route" not in routing
    from deltafuse.core.context import load_change_route
    route, errors = load_change_route(builder.change_dir)
    assert route == "code"
    assert errors == []
    assert check_gate(builder.change_dir, "analyzed") == []


def test_route_mismatch_is_error(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-038", title="Mismatch", route="docs")
        .step_intake()
        .step_analyze()
    )
    routing_file = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
    routing["route"] = "ops"
    routing_file.write_text(yaml.safe_dump(routing, sort_keys=False), encoding="utf-8")
    errs = validate_change_package(builder.change_dir)
    assert any("route mismatch" in e for e in errs)


def test_analyzed_ignores_routing_top_level_unknown_keys(tmp_path: Path, repo_root: Path):
    """RM-022 / AB-05: extra schema_version on routing.yaml does not fail analyzed."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-039", title="Routing extra keys")
        .step_intake()
        .step_analyze()
    )
    routing_file = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
    routing["schema_version"] = 2
    routing["unexpected_key"] = "ok"
    routing_file.write_text(yaml.safe_dump(routing, sort_keys=False), encoding="utf-8")
    assert check_gate(builder.change_dir, "analyzed") == []


def test_analyzed_accepts_two_slice_files(tmp_path: Path, repo_root: Path):
    """RM-022 / AB-02: a two-capability Change writes SLICE-01 and SLICE-02."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-040", title="Multi-cap slices")
        .step_intake()
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
    )
    assert (builder.change_dir / "slices" / "SLICE-01.md").is_file()
    assert (builder.change_dir / "slices" / "SLICE-02.md").is_file()
    assert check_gate(builder.change_dir, "analyzed") == []


def test_two_slices_do_not_satisfy_specified_without_live_spec(tmp_path: Path, repo_root: Path):
    """RM-022 regression: two slice files do not replace F-010 live spec."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-041", title="Two slices still need live spec")
        .step_intake()
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
        .step_specify()
    )
    catalog = {
        "schema_version": 2,
        "domains": {
            "monitoring": {
                "summary": "Usage monitoring",
                "capabilities": {
                    "usage_stats": {
                        "summary": "Per-key usage statistics",
                        "spec": ["docs/spec/monitoring/usage_stats.md"],
                    }
                },
            }
        },
    }
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(
        yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8"
    )
    for slice_id in ("SLICE-01", "SLICE-02"):
        _set_slice_capability(
            builder.change_dir,
            "monitoring.usage_stats",
            spec_refs=["docs/spec/monitoring/usage_stats.md#REQ-US-01"],
            slice_id=slice_id,
        )
    spec_delta = (
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01, SLICE-02]\n"
        "added: [docs/spec/monitoring/usage_stats.md#REQ-US-01]\n"
        "modified: []\n"
        "removed: []\n"
        "---\n\n# Spec Delta\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    errs = check_gate(builder.change_dir, "specified")
    assert any("usage_stats.md" in e and "does not exist" in e for e in errs)


def test_analyze_skill_does_not_freeze_single_slice(repo_root: Path):
    """RM-022 / AB-02: canonical skill must not freeze Analyze to one SLICE-01 file."""
    skill = (repo_root / "process" / "skills" / "analyze-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Do not collapse a multi-capability Change into a single" in skill
    assert "пиши только SLICE-01" not in skill
    assert "ONLY one file" not in skill


def test_analyzed_does_not_require_analysis_md(tmp_path: Path, repo_root: Path):
    """RM-030 / AB-04: analyzed is routing+slices+coverage; analysis.md is optional."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-042", title="No analysis summary")
        .step_intake()
        .step_analyze()
    )
    analysis = builder.change_dir / "analysis.md"
    analysis.unlink()
    assert not analysis.is_file()
    assert check_gate(builder.change_dir, "analyzed") == []


def test_analyze_skill_marks_analysis_md_optional(repo_root: Path):
    skill = (repo_root / "process" / "skills" / "analyze-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "`analysis.md` is optional" in skill
