from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.steps import STEP_CONTRACTS, validate_step_contracts
from tests.fixtures.change_builder import MockChangeBuilder


def test_step_contracts_match_phase_contracts():
    assert validate_step_contracts() == []
    assert STEP_CONTRACTS["declare"]["gate"] == "targeting"
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


def test_next_blocked_on_decision_exits_without_ready(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-033", title="Blocked").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
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
    )
    task_file = builder.change_dir / "tasks" / "TASK-001.md"
    meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    meta["status"] = "target-confirmed"
    task_file.write_text(
        f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}",
        encoding="utf-8",
    )
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "implement"
    assert selected.task == "TASK-001"
