"""Unit tests for DeltaFuse framework hasher and sensitivity invariant."""

from pathlib import Path
from deltafuse.core.hasher import compute_framework_content_hash, compute_product_baseline_revision


def test_hasher_skips_transient_caches(tmp_path: Path):
    """Hash must be identical whether __pycache__/.pytest_cache exist or not,
    matching the skip rules in scripts/init.ps1 and scripts/init.sh."""
    process_dir = tmp_path / "process"
    process_dir.mkdir(parents=True)
    (process_dir / "a.txt").write_text("content a", encoding="utf-8")

    h_clean = compute_framework_content_hash(tmp_path)

    cache_dir = tmp_path / "tests" / "__pycache__"
    cache_dir.mkdir(parents=True)
    (cache_dir / "stub.pyc").write_text("stale bytecode", encoding="utf-8")
    pytest_cache = tmp_path / "tests" / ".pytest_cache"
    pytest_cache.mkdir(parents=True)
    (pytest_cache / "v").write_text("cache", encoding="utf-8")

    h_dirty = compute_framework_content_hash(tmp_path)
    assert h_clean == h_dirty, "Transient caches must not affect the framework content hash"


def test_installer_scripts_declare_cache_skip(repo_root: Path):
    """Regression guard: shell installers must skip the same transient caches as hasher.py,
    otherwise a shell-installed product fails lock-hash validation."""
    ps1 = (repo_root / "scripts" / "init.ps1").read_text(encoding="utf-8")
    sh = (repo_root / "scripts" / "init.sh").read_text(encoding="utf-8")
    assert "__pycache__" in ps1 and ".pytest_cache" in ps1, (
        "init.ps1 must skip __pycache__/.pytest_cache in sync with hasher.py"
    )
    assert "__pycache__" in sh and ".pytest_cache" in sh, (
        "init.sh must skip __pycache__/.pytest_cache in sync with hasher.py"
    )


def test_hasher_deterministic(tmp_path: Path):
    process_dir = tmp_path / "process"
    process_dir.mkdir(parents=True)
    (process_dir / "a.txt").write_text("content a", encoding="utf-8")
    (process_dir / "b.txt").write_text("content b", encoding="utf-8")

    h1 = compute_framework_content_hash(tmp_path)
    h2 = compute_framework_content_hash(tmp_path)
    assert h1 == h2
    assert len(h1) == 64


def test_hasher_sensitivity_on_single_char_change(tmp_path: Path):
    process_dir = tmp_path / "process"
    process_dir.mkdir(parents=True)
    f = process_dir / "a.txt"
    f.write_text("canonical content", encoding="utf-8")

    h1 = compute_framework_content_hash(tmp_path)

    # Mutate 1 character
    f.write_text("canonical content.", encoding="utf-8")
    h2 = compute_framework_content_hash(tmp_path)

    assert h1 != h2, "Framework hash must be sensitive to any single character change"


def test_gitattributes_pins_lf_for_shell_scripts(repo_root: Path):
    attrs = (repo_root / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attrs
    assert "text=auto" in attrs


def test_product_baseline_revision_ignores_timestamp_and_tracks_spec_src(tmp_path: Path):
    spec = tmp_path / "docs" / "spec"
    src = tmp_path / "src"
    spec.mkdir(parents=True)
    src.mkdir()
    (spec / "core.md").write_text("# Spec\n## REQ-01\n", encoding="utf-8")
    (src / "core.py").write_text("x = 1\n", encoding="utf-8")
    h1 = compute_product_baseline_revision(tmp_path)
    assert h1.startswith("sha256:")
    assert h1 == compute_product_baseline_revision(tmp_path)

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    assert compute_product_baseline_revision(tmp_path) == h1

    (spec / "core.md").write_text("# Spec\n## REQ-01\nChanged.\n", encoding="utf-8")
    h2 = compute_product_baseline_revision(tmp_path)
    assert h2 != h1
