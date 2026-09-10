from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.specify import next_specify_pass
from tests.fixtures.change_builder import MockChangeBuilder


def _set_slice_status(change_dir: Path, slice_id: str, status: str) -> None:
    slice_file = change_dir / "slices" / f"{slice_id}.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["status"] = status
    slice_file.write_text(
        f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}",
        encoding="utf-8",
    )


def test_next_specify_pass_names_first_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-070", title="Specify first slice")
        .step_intake()
        .step_analyze()
    )
    cursor = next_specify_pass(builder.change_dir, tmp_path)
    assert cursor is not None
    assert cursor.pass_name == "slice"
    assert cursor.slice_id == "SLICE-01"
    assert cursor.capability == "system.core"
    assert cursor.spec_refs == ["docs/spec/core.md#REQ-01"]
    assert "docs/spec/core.md" in cursor.allowed_read
    assert "docs/spec/core.md" in cursor.allowed_write
    assert "docs/spec/**" not in cursor.allowed_read
    assert "docs/spec/**" not in cursor.allowed_write
    assert "docs/spec/_capabilities.yaml" in cursor.allowed_write


def test_next_specify_pass_second_slice_then_close(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-071", title="Specify two slices")
        .step_intake()
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
    )
    cursor = next_specify_pass(builder.change_dir, tmp_path)
    assert cursor.pass_name == "slice"
    assert cursor.slice_id == "SLICE-01"

    _set_slice_status(builder.change_dir, "SLICE-01", "specified")
    cursor = next_specify_pass(builder.change_dir, tmp_path)
    assert cursor.pass_name == "slice"
    assert cursor.slice_id == "SLICE-02"

    _set_slice_status(builder.change_dir, "SLICE-02", "specified")
    cursor = next_specify_pass(builder.change_dir, tmp_path)
    assert cursor.pass_name == "close"
    assert cursor.slice_id is None
    assert "docs/spec/**" not in cursor.allowed_read
    assert "docs/spec/**" not in cursor.allowed_write


def test_next_after_analyze_selects_specify_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-072", title="Queue specify")
        .step_intake()
        .step_analyze()
    )
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "specify"
    assert selected.specify_pass == "slice"
    assert selected.slice_id == "SLICE-01"
    assert selected.capability == "system.core"
    assert selected.spec_refs == ["docs/spec/core.md#REQ-01"]
    assert "docs/spec/core.md" in selected.allowed_read
    assert "docs/spec/**" not in selected.allowed_read
    assert selected.path == builder.change_dir.relative_to(tmp_path).as_posix()


def test_next_specify_json_omits_spec_tree(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-073", title="Specify json")
        .step_intake()
        .step_analyze()
    )
    import json

    before = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    ret = main(["next", str(tmp_path), "--step", "specify", "--json"])
    out, _ = capsys.readouterr()
    assert ret == 0
    data = json.loads(out)
    selected = data["selected"]
    assert selected["skill"] == "specify"
    assert selected["specify_pass"] == "slice"
    assert selected["slice_id"] == "SLICE-01"
    assert "docs/spec/**" not in selected["allowed_read"]
    assert "docs/spec/core.md" in selected["allowed_read"]
    assert (builder.change_dir / "change.yaml").read_text(encoding="utf-8") == before


def test_next_specify_close_when_slices_specified(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-074", title="Specify close")
        .step_intake()
        .step_analyze()
    )
    _set_slice_status(builder.change_dir, "SLICE-01", "specified")
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.specify_pass == "close"
    assert selected.skill == "specify"


def test_next_human_specify_slice_skips_specified_gate(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-075", title="Human specify").step_intake().step_analyze()
    ret = main(["next", str(tmp_path), "--human", "--step", "specify"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "specify_pass: slice" in out
    assert "slice_id: SLICE-01" in out
    assert "Do not run `check-gate --gate specified` yet" in out
    assert "docs/spec/**" not in out
    assert "docs/spec/core.md" in out
