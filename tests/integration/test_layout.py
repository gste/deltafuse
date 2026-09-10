"""Integration tests for DeltaFuse product repository layout validator."""

from pathlib import Path
import shutil
import pytest
import yaml
from deltafuse.core.installer import install
from deltafuse.core.layout import validate_product_layout


def test_valid_installed_product_layout(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    errors = validate_product_layout(tmp_path)
    assert errors == []


def test_missing_lock_detected(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    lock_file = tmp_path / ".deltafuse" / "lock.yaml"
    lock_file.unlink()

    errors = validate_product_layout(tmp_path)
    assert any("Missing required path: .deltafuse/lock.yaml" in e for e in errors)


def test_legacy_forbidden_path_detected(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    legacy = tmp_path / "docs" / "process"
    legacy.mkdir(parents=True)

    errors = validate_product_layout(tmp_path)
    assert any("Legacy product path must be migrated: docs/process" in e for e in errors)


def test_missing_generated_skill_detected(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    skill_file = tmp_path / ".agents" / "skills" / "intake" / "SKILL.md"
    skill_file.unlink()

    errors = validate_product_layout(tmp_path)
    assert any("Missing generated skill: .agents/skills/intake/SKILL.md" in e for e in errors)


def test_linked_skill_not_a_symlink_detected(tmp_path: Path, repo_root: Path):
    product = tmp_path / "product"
    vendor = product / "vendor" / "delta-fuse"
    (vendor / "docs").mkdir(parents=True)
    (vendor / "scripts").mkdir()
    (vendor / "tests").mkdir()
    (vendor / "docs" / ".keep").write_text("", encoding="utf-8")
    (vendor / "scripts" / ".keep").write_text("", encoding="utf-8")
    (vendor / "tests" / ".keep").write_text("", encoding="utf-8")
    shutil.copytree(repo_root / "process", vendor / "process")
    shutil.copyfile(repo_root / "VERSION", vendor / "VERSION")
    result = install(target_dir=product, framework_root=vendor)
    if result.adapter_mode != "link":
        pytest.skip("OS refused skill symlinks")
    slot = product / ".agents" / "skills" / "intake"
    slot.unlink()
    slot.mkdir()
    (slot / "SKILL.md").write_text("---\nname: intake\n---\n", encoding="utf-8")
    errors = validate_product_layout(product)
    assert any("Generated skill is not a symlink: .agents/skills/intake" in e for e in errors)


def test_invalid_call_width_detected(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    lock_file = tmp_path / ".deltafuse" / "lock.yaml"
    lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
    lock["workflow"]["call_width"] = "ornith"
    lock_file.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    errors = validate_product_layout(tmp_path)
    assert any("call_width" in e for e in errors)


def test_call_width_mismatch_detected(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["workflow"]["call_width"] = "narrow"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    errors = validate_product_layout(tmp_path)
    assert any("does not match locked call_width" in e for e in errors)
