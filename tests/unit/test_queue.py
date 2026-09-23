from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.steps import STEP_CONTRACTS, validate_step_contracts
from tests.fixtures.change_builder import MockChangeBuilder


def _write_proposed_dec(tmp_path: Path, change_id: str, dec_id: str = "DEC-0001", title: str = "Pick a store") -> Path:
    dec_dir = tmp_path / "docs" / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    path = dec_dir / f"{dec_id}-test.md"
    path.write_text(
        "---\n"
        f"id: {dec_id}\n"
        f"title: {title}\n"
        "kind: architecture\n"
        "status: proposed\n"
        "owner: ghost\n"
        f"change: {change_id}\n"
        "affects: {capabilities: [], spec_refs: []}\n"
        "---\n# Decision\n",
        encoding="utf-8",
    )
    return path


def test_step_contracts_match_phase_contracts():
    assert validate_step_contracts() == []
    assert STEP_CONTRACTS["declare"]["gate"] == "declaring"
    assert STEP_CONTRACTS["implement"]["gate"] == "implemented"


def test_next_picks_lowest_change_id(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-031", title="Later").step_intake().step_analyze()
    MockChangeBuilder(tmp_path, change_id="CHG-030", title="Earlier").step_intake()
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "analyze"
    assert selected.change_id == "CHG-030"
    assert selected.gate == "analyzed"


def test_next_declare_binds_first_pending_task(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-032", title="Tasks")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "declare"
    assert selected.task == "TASK-001"
    assert selected.path == builder.change_dir.relative_to(tmp_path).as_posix()
    assert selected.task_path and selected.task_path.endswith("TASK-001.md")


def test_next_empty_product_is_intake(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "intake"
    assert selected.change_id is None
    assert selected.intake_pending is False


def test_next_json_empty_product_has_done_halt(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    import json

    ret = main(["next", str(tmp_path), "--json"])
    out, _ = capsys.readouterr()
    assert ret == 0
    data = json.loads(out)
    assert data["selected"]["skill"] == "intake"
    assert data["selected"]["intake_pending"] is False
    assert data["halt"]["kind"] == "done"
    assert data.get("envelope") is None


def test_next_blocked_on_decision_exits_without_ready(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-033", title="Blocked").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    _write_proposed_dec(tmp_path, "CHG-033")
    queue = build_work_queue(tmp_path)
    assert select_next(queue) is None
    assert queue.blocked and queue.blocked[0].change_id == "CHG-033"
    ret = main(["next", str(tmp_path)])
    assert ret == 1


def test_next_json_and_no_writes(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-034", title="Json").step_intake()
    import json

    before = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    ret = main(["next", str(tmp_path), "--json"])
    out, _ = capsys.readouterr()
    assert ret == 0
    data = json.loads(out)
    assert data["selected"]["skill"] == "analyze"
    assert data["selected"]["change_id"] == "CHG-034"
    assert data["halt"] is None
    assert data["envelope"]["step"] == "analyze"
    assert (builder.change_dir / "change.yaml").read_text(encoding="utf-8") == before


def test_next_step_filter_and_change_scope(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-035", title="A").step_intake()
    later = (
        MockChangeBuilder(tmp_path, change_id="CHG-036", title="B")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    ret = main(["next", str(tmp_path), "--step", "declare"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "CHG-036" in out
    assert "/declare" in out
    ret = main(["next", str(later.change_dir)])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "CHG-036" in out
    assert "TASK-001" in out
    ret = main(["next", str(tmp_path), "--step", "implement"])
    _, err = capsys.readouterr()
    assert ret == 1
    assert "No ready work" in err


def test_next_implement_after_target_confirmed(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-037", title="Impl")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_declare()
    )
    # Implement opens only after the Core closed the declaring gate.
    builder._core_advance("declaring")
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["status"] = "declared"
    task_file.write_text(
        f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}",
        encoding="utf-8",
    )
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "implement"
    assert selected.task == "TASK-001"


def test_next_human_declare_checklist(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-038", title="Human declare")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
    before = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    ret = main(["next", str(tmp_path), "--human", "--step", "declare"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "not a second process" in out
    assert "Worker (human)" in out
    assert "docs/changes/*/evidence/red/**" in out
    assert f"check-gate {builder.change_dir.relative_to(tmp_path).as_posix()} --gate declaring" in out
    assert "deltafuse evidence" in out and "--phase red" in out
    assert "Do not auto-accept Decisions" in out
    assert (builder.change_dir / "change.yaml").read_text(encoding="utf-8") == before


def test_next_human_blocked_is_human_gate(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-039", title="Human blocked").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    _write_proposed_dec(tmp_path, "CHG-039")
    ret = main(["next", str(tmp_path), "--human"])
    _, err = capsys.readouterr()
    assert ret == 1
    assert "Human gate" in err
    assert "Do not auto-accept Decisions" in err
    assert "Do not run an LLM skill" in err
    assert "CHG-039" in err


def test_next_analyze_json_names_routing_pass(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-055", title="Pass json").step_intake()
    import json

    before = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    ret = main(["next", str(tmp_path), "--json"])
    out, _ = capsys.readouterr()
    assert ret == 0
    data = json.loads(out)
    selected = data["selected"]
    assert selected["skill"] == "analyze"
    assert selected["analyze_pass"] == "routing"
    assert selected["capability"] is None
    assert "docs/spec/_capabilities.yaml" in selected["allowed_read"]
    assert (builder.change_dir / "change.yaml").read_text(encoding="utf-8") == before


def test_next_analyze_wide_still_one_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    lock = yaml.safe_load((tmp_path / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8"))
    assert lock["workflow"]["call_width"] == "wide"
    builder = MockChangeBuilder(
        tmp_path, change_id="CHG-056", title="Wide serial"
    ).step_intake(claims=["CR-001", "CR-002"])
    routing = {
        "change": builder.change_id,
        "claims": {
            "CR-001": {"primary_capability": "billing.invoices", "confidence": "high"},
            "CR-002": {"primary_capability": "system.core", "confidence": "high"},
        },
    }
    (builder.change_dir / "routing.yaml").write_text(yaml.safe_dump(routing), encoding="utf-8")
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.analyze_pass == "slice"
    assert selected.capability == "billing.invoices"
    assert selected.slice_id == "SLICE-01"


def test_next_human_analyze_routing_skips_analyzed_gate(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-057", title="Human routing").step_intake()
    ret = main(["next", str(tmp_path), "--human", "--step", "analyze"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "analyze_pass: routing" in out
    assert "Do not run `check-gate --gate analyzed` yet" in out
    assert "docs/spec/**" not in out
    assert "docs/spec/_capabilities.yaml" in out


def test_next_human_analyze_coverage_uses_kernel(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-063", title="Human coverage").step_intake()
    routing = {
        "change": builder.change_id,
        "claims": {"CR-001": {"primary_capability": "system.core", "confidence": "high"}},
    }
    (builder.change_dir / "routing.yaml").write_text(yaml.safe_dump(routing), encoding="utf-8")
    slices = builder.change_dir / "slices"
    slices.mkdir()
    (slices / "SLICE-01.md").write_text(
        "---\n"
        "id: SLICE-01\n"
        f"change: {builder.change_id}\n"
        "title: Core\n"
        "status: draft\n"
        "primary_capability: system.core\n"
        "spec_refs: [docs/spec/core.md#REQ-01]\n"
        "claims: [CR-001]\n"
        "---\n",
        encoding="utf-8",
    )
    ret = main(["next", str(tmp_path), "--human", "--step", "analyze"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "analyze_pass: coverage" in out
    assert "deltafuse coverage" in out
    assert f"check-gate {builder.change_dir.relative_to(tmp_path).as_posix()} --gate analyzed" in out


def test_next_json_blocked_decision_has_halt_choices(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-070", title="Halt").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    _write_proposed_dec(tmp_path, "CHG-070", title="Use Redis")
    import json

    ret = main(["next", str(tmp_path), "--json"])
    out, _ = capsys.readouterr()
    assert ret == 1
    data = json.loads(out)
    assert data["selected"] is None
    assert data["halt"]["kind"] == "decision"
    labels = [row["label"] for row in data["halt"]["choices"]]
    assert any("Accept DEC-0001" in label and "Use Redis" in label for label in labels)
    assert any("Reject DEC-0001" in label for label in labels)
    assert any(row["id"] == "inspect" and row["command"] is None for row in data["halt"]["choices"])
    assert any("deltafuse decide" in (row["command"] or "") for row in data["halt"]["choices"])


def _set_task_status(builder: MockChangeBuilder, status: str, task_id: str = "TASK-001") -> None:
    task_file = builder.change_dir / "tasks" / f"{task_id}.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["status"] = status
    task_file.write_text(
        f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}",
        encoding="utf-8",
    )


def _decomposed(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Phases")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def test_next_declared_tasks_close_the_declaring_gate_first(tmp_path: Path, repo_root: Path):
    """q0 run 20260921T081038Z: every task declared, the Change still at
    'decomposed' - reading task statuses alone sent the Worker to implement
    with the declaring gate closed."""
    builder = _decomposed(tmp_path, repo_root, "CHG-041")
    _set_task_status(builder, "declared")
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "declare"
    assert "close the declaring gate" in selected.reason


def test_next_task_ahead_of_its_change_is_blocked_not_verified(tmp_path: Path, repo_root: Path):
    """The same run: tasks 'implemented' with the Change at 'decomposed' were
    routed to verify."""
    builder = _decomposed(tmp_path, repo_root, "CHG-042")
    _set_task_status(builder, "implemented")
    queue = build_work_queue(tmp_path)
    assert select_next(queue) is None
    assert any(
        item.task == "TASK-001" and "ran ahead of the declaring gate" in item.reason
        for item in queue.blocked
    )


def test_next_implemented_tasks_close_the_implemented_gate_before_verify(
    tmp_path: Path, repo_root: Path
):
    builder = _decomposed(tmp_path, repo_root, "CHG-043").step_declare()
    builder._core_advance("declaring")
    _set_task_status(builder, "implemented")
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "implement"
    assert "close the implemented gate" in selected.reason


@pytest.mark.parametrize("status", ["pending", "declared", "implemented"])
def test_next_keeps_decompose_until_the_decomposed_gate_passes(
    tmp_path: Path, repo_root: Path, status: str
):
    """q0 run 20260921T121031Z: decompose wrote task files that failed the
    decomposed gate (no `change`, no `slice`, `kind: code`), and `next` sent
    the Worker to declare, where it could not fix them - twenty minutes of
    loop. Before that gate the Change's status picks the step."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-044", title="Early tasks")
        .step_intake()
        .step_analyze()
        .step_specify()
    )
    tasks = builder.change_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / "TASK-001.md").write_text(
        f"---\nid: TASK-001\nkind: code\nstatus: {status}\n---\n# TASK-001\n",
        encoding="utf-8",
    )
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "decompose"
    assert "check-gate decomposed" in selected.reason


def test_an_intake_note_taken_in_by_an_archived_change_is_not_pending(tmp_path: Path, repo_root: Path, capsys):
    """q0 run M03 20260921T215701Z: after CHG-001 converged and was archived,
    `next` offered its intake note again and the Worker opened CHG-002 from the
    same request."""
    import json

    from deltafuse.core.queue import intake_sources_pending

    install(target_dir=tmp_path, framework_root=repo_root)
    note = tmp_path / "docs" / "intake" / "M03-adversarial.md"
    note.write_text("# Request\n- CR-001: something\n", encoding="utf-8")
    assert intake_sources_pending(tmp_path)

    archived = tmp_path / "docs" / "archive" / "changes" / "2026-09-22-CHG-001-x"
    archived.mkdir(parents=True)
    (archived / "change.yaml").write_text(
        yaml.safe_dump({"id": "CHG-001-x", "status": "archived",
                        "source": {"request": "request.md", "intake_refs": ["docs/intake/M03-adversarial.md"]}}),
        encoding="utf-8",
    )
    assert not intake_sources_pending(tmp_path)
    assert main(["next", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr()[0])
    assert data["halt"]["kind"] == "done"

    (tmp_path / "docs" / "intake" / "another.md").write_text("# New request\n", encoding="utf-8")
    assert intake_sources_pending(tmp_path)


def test_next_names_the_skill_file_so_the_worker_does_not_guess(tmp_path: Path, repo_root: Path):
    """gemma-4-26b-a4b on M01 (2026-09-22) read `docs/skills`: it had the
    skill's name and no path, and the guess counted against T6."""
    from deltafuse.core.installer import install
    from deltafuse.core.queue import build_work_queue, select_next, skill_file
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-820", title="Skill path").step_intake()
    item = select_next(build_work_queue(tmp_path))
    assert item is not None and item.skill
    assert item.skill_path == f".agents/skills/{item.skill}/SKILL.md"
    assert (tmp_path / item.skill_path).is_file()
    assert skill_file(tmp_path, "nosuchskill") is None
