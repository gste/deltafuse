"""Unit tests for ArtifactRegistry schema resolution and structured validation (AW-03)."""

from deltafuse import __version__ as FW_VERSION
from pathlib import Path
import pytest

from deltafuse.core.artifact_registry import (
    ArtifactRegistry,
    ArtifactRegistryError,
)


def test_registry_initialization_and_descriptors():
    registry = ArtifactRegistry()
    desc = registry.get_descriptor("task")
    assert desc["kind"] == "task"
    assert "create" in desc["allowed_operations"]
    assert "status" in desc["core_owned_fields"]


def test_unsupported_kind_rejected():
    registry = ArtifactRegistry()
    with pytest.raises(ArtifactRegistryError, match="Unsupported kind"):
        registry.get_descriptor("nonexistent_kind")


def test_structured_diagnostics_format():
    registry = ArtifactRegistry()
    invalid_task = {
        "id": "INVALID-ID",
        "change": "CHG-001",
        "slice": "SLICE-01",
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": ["docs/spec/auth.md#REQ-01"],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": ["src/billing.py"],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    res = registry.validate_storage_schema("task", invalid_task)
    assert not res.valid
    assert len(res.diagnostics) > 0
    diag = res.diagnostics[0]
    assert hasattr(diag, "code")
    assert hasattr(diag, "path")
    assert hasattr(diag, "message")


def test_reference_validation_scope(tmp_path: Path):
    registry = ArtifactRegistry()
    task_payload = {
        "id": "TASK-001",
        "change": "CHG-001",
        "slice": "SLICE-99",  # missing
        "kind": "feature",
        "status": "pending",
        "depends_on": [],
        "requirement_delta": "added",
        "spec_refs": [],
        "allowed_paths": ["src/auth.py"],
        "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    res = registry.validate_references("task", task_payload, change_dir=tmp_path)
    assert not res.valid
    assert any(d.code == "missing_reference" for d in res.diagnostics)
    assert any(s["scope"] == "whole_gate" and s["status"] == "not_evaluated" for s in res.scopes)


def test_valid_legacy_extension_fields_supported():
    registry = ArtifactRegistry()
    valid_routing_ext = {
        "change": "CHG-001",
        "claims": {},
        "custom_extension": "supported",
    }
    res = registry.validate_storage_schema("routing", valid_routing_ext)
    assert res.valid


def test_aw31_verify_product_lock_rejects_version_and_content_hash_mismatch(tmp_path):
    from deltafuse.core.artifact_registry import ArtifactRegistry, ArtifactRegistryError
    from deltafuse.core.assets import get_installed_lock_hash

    reg = ArtifactRegistry()
    lock_dir = tmp_path / ".deltafuse"
    lock_dir.mkdir(parents=True)
    lock_file = lock_dir / "lock.yaml"

    # Valid lock
    lock_file.write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        f"  content_hash: {get_installed_lock_hash()}\n",
        encoding="utf-8",
    )
    reg.verify_product_lock(tmp_path)

    # Test 1: Mismatched version 99.99.99
    lock_file.write_text(
        "schema_version: 3\n"
        "framework:\n"
        "  version: 99.99.99\n"
        "  source: deltafuse\n"
        f"  content_hash: {get_installed_lock_hash()}\n",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactRegistryError) as exc1:
        reg.verify_product_lock(tmp_path)
    assert "framework version '99.99.99'" in str(exc1.value)

    # Test 2: Mismatched zero content hash
    lock_file.write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        "  content_hash: sha256:0000000000000000000000000000000000000000000000000000000000000000\n",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactRegistryError) as exc2:
        reg.verify_product_lock(tmp_path)
    assert "framework content_hash" in str(exc2.value)


def test_aw38_verify_product_lock_rejects_missing_and_malformed_fields(tmp_path, monkeypatch):
    from deltafuse.core.artifact_registry import ArtifactRegistry, ArtifactRegistryError
    from deltafuse.core.assets import get_installed_lock_hash

    reg = ArtifactRegistry()
    lock_dir = tmp_path / ".deltafuse"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "lock.yaml"

    # Missing framework.content_hash while retaining source
    lock_file.write_text(f"schema_version: 3\nframework:\n  version: {FW_VERSION}\n  source: deltafuse\n", encoding="utf-8")
    with pytest.raises(ArtifactRegistryError) as exc:
        reg.verify_product_lock(tmp_path)
    assert "framework.content_hash" in str(exc.value)

    # Missing framework.version
    lock_file.write_text(f"schema_version: 3\nframework:\n  source: deltafuse\n  content_hash: {get_installed_lock_hash()}\n", encoding="utf-8")
    with pytest.raises(ArtifactRegistryError) as exc:
        reg.verify_product_lock(tmp_path)
    assert "framework.version" in str(exc.value)

    # Missing framework.source
    lock_file.write_text(f"schema_version: 3\nframework:\n  version: {FW_VERSION}\n  content_hash: {get_installed_lock_hash()}\n", encoding="utf-8")
    with pytest.raises(ArtifactRegistryError) as exc:
        reg.verify_product_lock(tmp_path)
    assert "framework.source" in str(exc.value)

    # Malformed content_hash format
    lock_file.write_text(f"schema_version: 3\nframework:\n  version: {FW_VERSION}\n  source: deltafuse\n  content_hash: invalid_hash\n", encoding="utf-8")
    with pytest.raises(ArtifactRegistryError) as exc:
        reg.verify_product_lock(tmp_path)
    assert "invalid framework.content_hash format" in str(exc.value)

    # Unavailable executing asset identity
    lock_file.write_text(f"schema_version: 3\nframework:\n  version: {FW_VERSION}\n  source: deltafuse\n  content_hash: {get_installed_lock_hash()}\n", encoding="utf-8")
    monkeypatch.setattr("deltafuse.core.assets.get_executing_framework_identity", lambda: (FW_VERSION, set()))
    with pytest.raises(ArtifactRegistryError) as exc:
        reg.verify_product_lock(tmp_path)
    assert "unavailable" in str(exc.value)


def test_the_string_null_as_design_ref_is_refused_with_the_fix(tmp_path: Path):
    """Gemma 31B shakedown cls-g31p3-m02 (2026-10-04): design_ref "null" (a string) four
    decompose steps running. The value is still refused; the refusal now names the fix."""
    registry = ArtifactRegistry()
    payload = {
        "id": "TASK-001", "change": "CHG-001", "slice": "SLICE-01", "kind": "feature",
        "status": "pending", "depends_on": [], "requirement_delta": "added", "spec_refs": [],
        "design_ref": "null", "allowed_paths": ["src/auth.py"], "forbidden_paths": [],
        "context_budget": {"max_tokens": 16000, "max_files": 24},
    }
    res = registry.validate_references("task", payload, change_dir=tmp_path)
    design = [d for d in res.diagnostics if d.path == "/design_ref"]
    assert design and not res.valid
    assert 'not the string "null"' in design[0].message
    payload["design_ref"] = "docs/design/missing.md"
    other = [d for d in registry.validate_references("task", payload, change_dir=tmp_path).diagnostics
             if d.path == "/design_ref"]
    assert other and "not the string" not in other[0].message


def _pin_order(tmp_path: Path, kind: str, payload: dict, pointer: str, rels: list) -> list:
    """Write one file per candidate location, each with its own id; peel them off in turn."""
    repo = tmp_path / "repo"
    (repo / ".deltafuse").mkdir(parents=True)
    root = repo / "sub"
    cdir = repo / "cdir"
    bases = {"root": root, "repo": repo, "cdir": cdir}
    files = []
    for n, (base, rel) in enumerate(rels):
        path = bases[base].joinpath(*rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nid: WINNER-{n}\nchange: CHG-001\n---\nbody\n", encoding="utf-8")
        files.append(path)
    winners = []
    for path in files:
        res = ArtifactRegistry().validate_references(
            kind, payload, product_root=root, change_dir=cdir, change_id="CHG-001"
        )
        msgs = [d.message for d in res.diagnostics if d.path == pointer]
        winners.append(msgs[0].split("identity '")[1].split("'")[0])
        path.unlink()
    return winners


def test_reference_candidate_order_is_pinned(tmp_path: Path):
    """The first existing candidate wins; this pins the search order of slice and dependency files."""
    chg = ("docs", "changes", "CHG-001")
    slice_rels = [
        ("root", ("slices", "SLICE-01.md")),
        ("repo", chg + ("slices", "SLICE-01.md")),
        ("root", chg + ("slices", "SLICE-01.md")),
        ("cdir", ("slices", "SLICE-01.md")),
        ("cdir", ("SLICE-01.md",)),
        ("repo", ("slices", "SLICE-01.md")),
    ]
    assert _pin_order(tmp_path / "s", "task", {"slice": "SLICE-01"}, "/slice", slice_rels) == [
        f"WINNER-{n}" for n in range(len(slice_rels))
    ]
    dep_rels = [
        ("root", ("tasks", "TASK-001.md")),
        ("repo", chg + ("tasks", "TASK-001.md")),
        ("root", chg + ("tasks", "TASK-001.md")),
        ("cdir", ("tasks", "TASK-001.md")),
        ("repo", ("tasks", "TASK-001.md")),
    ]
    assert _pin_order(tmp_path / "d", "task", {"depends_on": ["TASK-001"]}, "/depends_on", dep_rels) == [
        f"WINNER-{n}" for n in range(len(dep_rels))
    ]
