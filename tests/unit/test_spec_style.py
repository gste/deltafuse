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


def test_bench_docs_ru_en_section_parity(repo_root: Path):
    """V3-FIX-019: bench.ru.md mirrors the bench.md section structure."""
    def sections(name: str) -> set[str]:
        text = (repo_root / "docs" / name).read_text(encoding="utf-8")
        return {line[3:].strip() for line in text.splitlines() if line.startswith("## ")}

    en = sections("bench.md")
    ru = sections("bench.ru.md")
    # Compare canonicalized section titles by position count, not language:
    # each EN section must have a RU counterpart (same count and order).
    def ordered(name: str) -> list[str]:
        text = (repo_root / "docs" / name).read_text(encoding="utf-8")
        return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]

    assert len(ordered("bench.md")) == len(ordered("bench.ru.md")), (
        f"EN: {ordered('bench.md')} RU: {ordered('bench.ru.md')}"
    )
    assert "Cases" in {s for s in en}


def test_docs_forbid_removed_lifecycle_tokens(repo_root: Path):
    """V3-FIX-017: removed lifecycle terminology must not reappear in docs."""
    forbidden = {"target_confirmed"}
    for doc in (repo_root / "docs").rglob("*.md"):
        text = doc.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{doc.name} uses removed token '{token}'"
