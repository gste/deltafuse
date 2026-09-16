"""QF-011 finding: wheel installs must forward the bundle skills dir to the
adapter-skill installer, otherwise products get empty adapter roots and
`deltafuse validate-layout` fails with 24 missing-skill errors."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys = pytest.importorskip("sys")

from deltafuse.core import installer as inst  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_installer_passes_bundle_skills_dir(tmp_path, monkeypatch):
    """White-box: in bundle (wheel) mode the installer must pass skills_dir."""
    captured: dict = {}

    def fake_install_adapter_skills(**kwargs):
        captured.update(kwargs)
        return 0, kwargs["mode"]

    monkeypatch.setattr(inst, "install_adapter_skills", fake_install_adapter_skills)
    # Force the "pure wheel" branch: no nested checkout, assets = the real
    # generated bundle in the repo's src tree.
    monkeypatch.setattr(inst, "source_assets_root", lambda: None)
    monkeypatch.setattr(
        inst, "resolve_assets", lambda name: REPO_ROOT / "src" / "deltafuse" / "assets" / name
    )
    inst.install(target_dir=tmp_path, force=True)
    assert captured.get("skills_dir") is not None
    assert (captured["skills_dir"] / "run").is_dir()
