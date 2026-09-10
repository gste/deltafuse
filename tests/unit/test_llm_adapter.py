"""Worker (LLM) skills bind a model; the Core selects the step."""

from pathlib import Path

from deltafuse.core.steps import STEP_CONTRACTS, WORKER_LLM_MARKERS


def test_canonical_skills_bind_worker_to_llm(repo_root: Path):
    for step, spec in STEP_CONTRACTS.items():
        skill_path = repo_root / "process" / "skills" / spec["skill"] / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        for marker in WORKER_LLM_MARKERS:
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


def test_product_agents_template_defers_to_core(repo_root: Path):
    text = (repo_root / "process" / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    assert "The Core" in text
    assert "The Worker" in text
    assert "Do not auto-accept Decisions" in text


def test_core_and_worker_glossary(repo_root: Path):
    en = (repo_root / "docs" / "core-and-worker.md").read_text(encoding="utf-8")
    ru = (repo_root / "docs" / "core-and-worker.ru.md").read_text(encoding="utf-8")
    assert "**Core**" in en and "**Worker**" in en
    assert "**Process** is the lifecycle we follow" in en
    assert "Human Gate is not a Worker" in en
    assert "**Ядро**" in ru and "**Воркер**" in ru
    assert "**Процесс** — lifecycle" in ru
    assert "Human Gate — не воркер" in ru
