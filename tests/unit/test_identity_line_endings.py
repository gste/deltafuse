"""The framework identity a product lock pins does not depend on line endings.

2026-10-27: sync_assets.py had left the bundle manifest CRLF on a Windows
checkout (core.autocrlf=true; git status clean), products pinned that file's
digest, and a checkout to another branch and back rewrote it as LF: same
content, another digest, and the Artifact Writer refused every write.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from deltafuse import __version__
from deltafuse.core import assets
from deltafuse.core.artifact_registry import ArtifactRegistry, ArtifactRegistryError
from deltafuse.core.hasher import (
    compute_framework_content_hash,
    compute_framework_content_hashes,
    normalize_line_endings,
)

MANIFEST_LF = b'{\n  "files": {\n    "__init__.py": "ab"\n  },\n  "schema_version": 1\n}\n'


def _tree(root: Path, eol: bytes) -> Path:
    for rel, text in {
        "process/skills/a.md": b"# A\nline\n",
        "src/deltafuse/core.py": b"x = 1\ny = 2\n",
        "scripts/init.ps1": b"Write-Host hi\n",
        "VERSION": b"9.9.9\n",
        "pyproject.toml": b"[project]\nname = 'x'\n",
    }.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace(b"\n", eol))
    return root


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_normalize_line_endings_touches_only_crlf_in_text():
    assert normalize_line_endings(b"a\r\nb\r\n") == b"a\nb\n"
    assert normalize_line_endings(b"a\rb\n") == b"a\rb\n"  # a lone CR is content
    assert normalize_line_endings(b"a\r") == b"a\r"
    assert normalize_line_endings(b"\x00a\r\n") == b"\x00a\r\n"  # binary


def test_framework_content_hash_is_the_same_for_crlf_and_lf_checkouts(tmp_path: Path):
    lf = _tree(tmp_path / "lf", b"\n")
    crlf = _tree(tmp_path / "crlf", b"\r\n")

    assert compute_framework_content_hash(crlf) == compute_framework_content_hash(lf)
    current, legacy = compute_framework_content_hashes(crlf)
    assert current == compute_framework_content_hash(lf)
    assert legacy != current, "the legacy digest is the raw-byte one a CRLF checkout pinned"
    assert compute_framework_content_hashes(lf) == (current, current)


def test_framework_content_hash_keeps_binary_files_byte_exact(tmp_path: Path):
    one = _tree(tmp_path / "one", b"\n")
    two = _tree(tmp_path / "two", b"\n")
    (one / "src" / "blob.bin").write_bytes(b"\x00\x01\r\n")
    (two / "src" / "blob.bin").write_bytes(b"\x00\x01\n")
    assert compute_framework_content_hash(one) != compute_framework_content_hash(two)


def test_framework_content_hash_still_sees_content_changes(tmp_path: Path):
    root = _tree(tmp_path / "t", b"\r\n")
    before = compute_framework_content_hash(root)
    (root / "src" / "deltafuse" / "core.py").write_bytes(b"x = 1\r\ny = 3\r\n")
    assert compute_framework_content_hash(root) != before


def test_manifest_identity_is_the_same_for_crlf_and_lf(tmp_path: Path):
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(MANIFEST_LF)
    crlf.write_bytes(MANIFEST_LF.replace(b"\n", b"\r\n"))

    current_lf, legacy_lf = assets.manifest_identity_digests(lf)
    current_crlf, legacy_crlf = assets.manifest_identity_digests(crlf)
    assert current_lf == current_crlf == _sha(MANIFEST_LF)
    # either way round, the raw digest of the other form is still known
    assert _sha(crlf.read_bytes()) in legacy_lf
    assert _sha(crlf.read_bytes()) in legacy_crlf
    assert current_lf not in legacy_lf


def _bundle(root: Path, manifest: bytes, monkeypatch) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_bytes(manifest)
    monkeypatch.setattr(assets, "bundle_root", lambda: root)
    monkeypatch.setattr(assets, "source_assets_root", lambda: None)
    return root


def _lock(product: Path, content_hash: str) -> None:
    (product / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (product / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {__version__}\n"
        "  source: deltafuse\n"
        f"  content_hash: {content_hash}\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("disk_eol", [b"\n", b"\r\n"], ids=["disk-lf", "disk-crlf"])
def test_product_lock_survives_the_manifest_changing_line_endings(tmp_path: Path, monkeypatch, disk_eol):
    """The incident: a lock taken from CRLF bytes, the manifest now LF (and the reverse)."""
    bundle = _bundle(tmp_path / "bundle", MANIFEST_LF.replace(b"\n", disk_eol), monkeypatch)
    product = tmp_path / "product"
    registry = ArtifactRegistry()

    new_pin = assets.get_installed_lock_hash()
    assert new_pin == f"sha256:{_sha(MANIFEST_LF)}", "new locks pin the normalized digest"
    _lock(product, new_pin)
    registry.verify_product_lock(product)

    # transition until 4.0.0: a lock written up to 3.3.11 from either form verifies
    for eol in (b"\n", b"\r\n"):
        _lock(product, "sha256:" + _sha(MANIFEST_LF.replace(b"\n", eol)))
        registry.verify_product_lock(product)

    # it is still a content identity
    (bundle / "manifest.json").write_bytes(MANIFEST_LF.replace(b'"ab"', b'"cd"').replace(b"\n", disk_eol))
    with pytest.raises(ArtifactRegistryError, match="does not match running framework asset identity"):
        registry.verify_product_lock(product)


def test_init_keeps_a_legacy_pin_of_the_same_framework(tmp_path: Path, repo_root: Path, monkeypatch):
    """Re-running `deltafuse init` must not re-pin a lock written up to 3.3.11: every
    evidence stamp of an active Change carries the pin it was taken under."""
    from deltafuse.core import installer

    current = compute_framework_content_hash(repo_root)
    legacy = "e" * 64
    monkeypatch.setattr(installer, "compute_framework_content_hashes", lambda root: (current, legacy))

    installer.install(target_dir=tmp_path, framework_root=repo_root)
    lock_path = tmp_path / ".deltafuse" / "lock.yaml"
    lock_path.write_text(
        lock_path.read_text(encoding="utf-8").replace(f"sha256:{current}", f"sha256:{legacy}"),
        encoding="utf-8",
    )

    result = installer.install(target_dir=tmp_path, framework_root=repo_root)
    assert result.content_hash == legacy
    assert f"content_hash: sha256:{legacy}" in lock_path.read_text(encoding="utf-8")

    lock_path.write_text(
        lock_path.read_text(encoding="utf-8").replace(f"sha256:{legacy}", "sha256:" + "f" * 64),
        encoding="utf-8",
    )
    with pytest.raises(installer.InstallationError, match="different DeltaFuse lock"):
        installer.install(target_dir=tmp_path, framework_root=repo_root)
