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


def test_intake_skill_forbids_provenance_yaml(repo_root: Path):
    text = (repo_root / "process" / "skills" / "intake" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Do not add `provenance`" in text
    assert "CR-001" in text


def test_intake_skill_does_not_teach_src_writes(repo_root: Path):
    text = (repo_root / "process" / "skills" / "intake" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Do not write `src/**`" in text
    for line in text.splitlines():
        if "src/" in line or "src/**" in line:
            lowered = line.lower()
            assert "do not" in lowered or "must not" in lowered, line


def test_analyze_skill_follows_next_pass(repo_root: Path):
    text = (repo_root / "process" / "skills" / "analyze" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "analyze_pass" in text
    assert "do not call `check-gate --gate analyzed`" in text
    assert "deltafuse coverage" in text
    assert "primary_capability" in text
    assert "CR-001" in text


def test_specify_skill_follows_next_pass(repo_root: Path):
    text = (repo_root / "process" / "skills" / "specify" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "specify_pass" in text
    assert "do not call `check-gate --gate specified`" in text
    assert "spec_refs" in text
    assert "Do not set `specified` yourself" in text
    assert "status: accepted" not in text


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


def test_run_skill_is_through_mode(repo_root: Path):
    text = (repo_root / "process" / "skills" / "run" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "deltafuse next --json" in text
    assert "halt.choices" in text
    assert "deltafuse decide" in text
    assert "choice.command" in text
    assert "Do not auto-accept Decisions" in text
    assert "in this same session" in text
    assert "deltafuse leash" in text
    assert "envelope.write" in text


def test_worker_skills_do_not_instruct_writing_accepted_status(repo_root: Path):
    skills = repo_root / "process" / "skills"
    for path in sorted(skills.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        assert "status: accepted" not in text, path
        assert "status: rejected" not in text, path


def test_product_agents_template_defers_to_core(repo_root: Path):
    text = (repo_root / "process" / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    assert "The Core" in text
    assert "The Worker" in text
    assert "Do not auto-accept Decisions" in text
    assert "/run" in text
    assert "halt.choices" in text
    assert "choice.command" in text
    assert "envelope.write" in text
    assert "Intake MUST NOT write `src/**`" in text


def test_core_and_worker_glossary(repo_root: Path):
    en = (repo_root / "docs" / "core-and-worker.md").read_text(encoding="utf-8")
    ru = (repo_root / "docs" / "core-and-worker.ru.md").read_text(encoding="utf-8")
    assert "**Core**" in en and "**Worker**" in en
    assert "**Process** is the lifecycle we follow" in en
    assert "Human Gate is not a Worker" in en
    assert "## Through-mode" in en
    assert "**Ядро**" in ru and "**Воркер**" in ru
    assert "**Процесс** — lifecycle" in ru
    assert "Human Gate — не воркер" in ru
    assert "## Сквозной режим" in ru
