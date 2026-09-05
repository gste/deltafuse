"""Integration tests for DeltaFuse product repository layout validator."""

from pathlib import Path
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
