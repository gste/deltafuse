"""RM-031: EARS is spec style; PBT is optional Declare and skippable without a runner."""

from pathlib import Path

import pytest


def test_specify_skill_ears_does_not_replace_live_spec(repo_root: Path):
    skill = (repo_root / "process" / "skills" / "specify" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "RFC 2119" in skill
    assert "WHEN [condition] THE SYSTEM SHALL" in skill
    assert "not a substitute for live `docs/spec/**`" in skill
    assert ".kiro" not in skill


def test_declare_skill_pbt_is_optional_not_hidden_replacement(repo_root: Path):
    skill = (repo_root / "process" / "skills" / "declare" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Skip if no local runner" in skill
    assert "does not replace the GWT example Red test" in skill
    assert "independent hidden suite" in skill
    assert "Do not add `.kiro` or Cucumber as Declare" in skill


def test_optional_pbt_skips_without_local_runner():
    """RM-031 / KI-07: absence of Hypothesis is skip, not a gate fail."""
    pytest.importorskip("hypothesis", reason="no local PBT runner")
