import pytest
from pathlib import Path
import yaml
from deltafuse.core.fsm import (
    validate_change_package,
    check_gate,
    can_transition,
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


def _set_slice_capability(change_dir: Path, capability: str, spec_refs: list[str] | None = None) -> None:
    slice_file = change_dir / "slices" / "SLICE-01.md"
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
