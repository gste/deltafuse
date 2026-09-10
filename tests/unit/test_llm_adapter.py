"""Thinker (LLM) skills bind a model; the Process selects the step."""

from pathlib import Path

from deltafuse.core.steps import STEP_CONTRACTS, THINKER_LLM_MARKERS


def test_canonical_skills_bind_thinker_to_llm(repo_root: Path):
    for step, spec in STEP_CONTRACTS.items():
        skill_path = repo_root / "process" / "skills" / spec["skill"] / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        for marker in THINKER_LLM_MARKERS:
            assert marker in text, f"{step}: missing {marker!r}"
        assert f"--gate {spec['gate']}" in text, f"{step}: missing --gate {spec['gate']}"
        assert "Recommend /" not in text, f"{step}: still recommends a slash command"


def test_declare_and_implement_call_evidence_runner(repo_root: Path):
    declare = (repo_root / "process" / "skills" / "declare" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    implement = (repo_root / "process" / "skills" / "implement" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "deltafuse evidence" in declare
    assert "deltafuse evidence" in implement


def test_verify_archives_via_kernel(repo_root: Path):
    skill = (repo_root / "process" / "skills" / "verify" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "deltafuse archive" in skill


def test_product_agents_template_defers_to_process(repo_root: Path):
    text = (repo_root / "process" / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    assert "The Process" in text
    assert "The Thinker" in text
    assert "Do not auto-accept Decisions" in text


def test_process_and_thinker_glossary(repo_root: Path):
    en = (repo_root / "docs" / "process-and-thinker.md").read_text(encoding="utf-8")
    ru = (repo_root / "docs" / "process-and-thinker.ru.md").read_text(encoding="utf-8")
    assert "**Process**" in en and "**Thinker**" in en
    assert "Human Gate is not a Thinker" in en
    assert "**Процесс**" in ru and "**Мыслитель**" in ru
    assert "Human Gate — не мыслитель" in ru
