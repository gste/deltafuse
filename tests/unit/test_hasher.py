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
    # pip rewrites this on every editable install and wheel build (it raced the parallel suite)
    egg_info = tmp_path / "src" / "deltafuse.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "SOURCES.txt").write_text("src/deltafuse/__init__.py", encoding="utf-8")

    h_dirty = compute_framework_content_hash(tmp_path)
    assert h_clean == h_dirty, "Transient caches must not affect the framework content hash"


def test_installer_scripts_declare_cache_skip(repo_root: Path):
    """Regression guard: shell installers must skip the same transient caches as hasher.py,
    otherwise a shell-installed product fails lock-hash validation."""
    ps1 = (repo_root / "scripts" / "init.ps1").read_text(encoding="utf-8")
    sh = (repo_root / "scripts" / "init.sh").read_text(encoding="utf-8")
    assert "__pycache__" in ps1 and ".pytest_cache" in ps1 and ".egg-info" in ps1, (
        "init.ps1 must skip __pycache__/.pytest_cache in sync with hasher.py"
    )
    assert "__pycache__" in sh and ".pytest_cache" in sh and ".egg-info" in sh, (
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


def _framework_tree(root: Path) -> Path:
    (root / "process" / "Sub").mkdir(parents=True)
    (root / "process" / "Sub" / "A.md").write_text("a\n", encoding="utf-8")
    (root / "src" / "deltafuse.egg-info").mkdir(parents=True)
    (root / "src" / "core.py").write_text("x = 1\n", encoding="utf-8")
    (root / "src" / "deltafuse.egg-info" / "SOURCES.txt").write_text("src/core.py\n", encoding="utf-8")
    (root / "tests" / "__pycache__").mkdir(parents=True)
    (root / "tests" / "__pycache__" / "t.pyc").write_bytes(b"\0")
    (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return root


def test_shell_installers_compute_the_same_framework_hash(tmp_path: Path, repo_root: Path):
    """A product installed by init.sh or init.ps1 pins this hash and the Core checks it against
    hasher.py's: init.sh wrote its pyproject record as `pyproject.toml:` and never matched."""
    import os
    import re
    import shutil
    import subprocess

    import pytest

    root = _framework_tree(tmp_path)
    expected = compute_framework_content_hash(root)
    checked = 0

    bash = shutil.which("bash")
    if bash and not (os.name == "nt" and "system32" in bash.lower()):  # WSL's bash sees other paths
        sh = (repo_root / "scripts" / "init.sh").read_text(encoding="utf-8")
        functions = "\n".join(
            re.search(rf"^{name}\(\) {{.*?^}}", sh, re.S | re.M).group(0)
            for name in ("sha256_file", "framework_hash")
        )
        out = subprocess.run(
            [bash, "-c", functions + "\nframework_hash"],
            env={**os.environ, "SCRIPT_DIR": root.as_posix()}, capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip() == expected, "init.sh"
        checked += 1

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh:
        script = (
            "$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:DF_INIT, [ref]$null, [ref]$null);"
            "$fn = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]"
            " -and $n.Name -eq 'Get-FrameworkContentHash' }, $true) | Select-Object -First 1;"
            "$FrameworkRoot = $env:DF_ROOT; . ([scriptblock]::Create($fn.Extent.Text)); Get-FrameworkContentHash"
        )
        out = subprocess.run(
            [pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "DF_INIT": str(repo_root / "scripts" / "init.ps1"), "DF_ROOT": str(root)},
            capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip() == expected, "init.ps1"
        checked += 1

    if not checked:
        pytest.skip("neither bash nor PowerShell is available")
