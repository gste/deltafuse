import pytest
from pathlib import Path
import yaml
from deltafuse.core.hasher import compute_framework_content_hash
from deltafuse.core.installer import install, InstallationError

def test_framework_content_hash_consistency(repo_root: Path):
    hash1 = compute_framework_content_hash(repo_root)
    hash2 = compute_framework_content_hash(repo_root)
    assert hash1 == hash2
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)

def test_fresh_installation(tmp_path: Path, repo_root: Path):
    result = install(target_dir=tmp_path, framework_root=repo_root)
    assert result.version == (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    assert len(result.content_hash) == 64

    # Check directories
    assert (tmp_path / ".deltafuse").is_dir()
    assert (tmp_path / "docs" / "intake").is_dir()
    assert (tmp_path / "docs" / "changes").is_dir()
    assert (tmp_path / "docs" / "spec").is_dir()
    assert (tmp_path / "docs" / "decisions").is_dir()
    assert (tmp_path / "docs" / "archive" / "changes").is_dir()

    # Check files
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".deltafuse" / "config.yaml").is_file()
    assert (tmp_path / ".deltafuse" / "lock.yaml").is_file()
    assert (tmp_path / "docs" / "spec" / "_capabilities.yaml").is_file()
    assert (tmp_path / "docs" / "decisions" / "DEC-0000-template.md").is_file()
    assert (tmp_path / "CHANGELOG.md").is_file()

    # Check generated skills
    agents_skills = tmp_path / ".agents" / "skills"
    assert (agents_skills / "intake" / "SKILL.md").is_file()
    assert (agents_skills / "analyze-change" / ".deltafuse-generated.yaml").is_file()

def test_idempotent_upgrade_preserves_custom_files(tmp_path: Path, repo_root: Path):
    # Step 1: initial install
    install(target_dir=tmp_path, framework_root=repo_root)

    # Step 2: mutate user files
    custom_agents = "# Custom User Agent Config\n"
    (tmp_path / "AGENTS.md").write_text(custom_agents, encoding="utf-8")

    custom_capabilities = """schema_version: 2
domains:
  custom_domain:
    summary: Custom user domain
    capabilities: {}
"""
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(custom_capabilities, encoding="utf-8")

    # Step 3: run install again without force
    install(target_dir=tmp_path, framework_root=repo_root)

    # Verify custom content preserved
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == custom_agents
    assert (tmp_path / "docs" / "spec" / "_capabilities.yaml").read_text(encoding="utf-8") == custom_capabilities

def test_force_upgrade_with_modified_lock(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)

    lock_file = tmp_path / ".deltafuse" / "lock.yaml"
    lock_file.write_text("schema_version: 2\nframework:\n  version: 1.0.0\n  content_hash: sha256:0000000000000000000000000000000000000000000000000000000000000000\n", encoding="utf-8")

    # Without force: must raise InstallationError
    with pytest.raises(InstallationError, match="A different DeltaFuse lock already exists"):
        install(target_dir=tmp_path, force=False, framework_root=repo_root)

    # With force: must succeed and update lock
    result = install(target_dir=tmp_path, force=True, framework_root=repo_root)
    assert f"content_hash: sha256:{result.content_hash}" in lock_file.read_text(encoding="utf-8")
