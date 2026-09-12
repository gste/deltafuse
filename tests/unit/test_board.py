"""FM-001: read-only board snapshot for fuse-map."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema.validators import validator_for

from deltafuse.cli import main
from deltafuse.core.board import (
    BOARD_LAYOUT,
    BOARD_TERMINAL_STATUSES,
    BoardError,
    build_board_snapshot,
    validate_board_layout,
)
from deltafuse.core.fsm import VALID_CHANGE_STATUSES
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _board_schema(repo_root: Path) -> dict:
    path = repo_root / "docs" / "contracts" / "board-snapshot.schema.yaml"
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    return schema


def _assert_valid_snapshot(snapshot: dict, repo_root: Path) -> None:
    schema = _board_schema(repo_root)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    errors = [err.message for err in validator_cls(schema).iter_errors(snapshot)]
    assert errors == [], errors


def _tree_sig(root: Path) -> list[tuple[str, int, int]]:
    rows: list[tuple[str, int, int]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            rows.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    return rows


def test_board_layout_covers_happy_path_once():
    assert validate_board_layout() == []
    seen: set[str] = set()
    for column in BOARD_LAYOUT["columns"]:
        for status in column["statuses"]:
            assert status not in seen
            seen.add(status)
            assert status not in BOARD_TERMINAL_STATUSES
    assert seen == VALID_CHANGE_STATUSES - BOARD_TERMINAL_STATUSES


def test_board_empty_product_still_has_layout(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    snapshot = build_board_snapshot(tmp_path)
    _assert_valid_snapshot(snapshot, repo_root)
    assert snapshot["schema_version"] == 1
    assert snapshot["changes"] == []
    assert "archive" not in snapshot
    assert snapshot["layout"]["columns"]
    assert snapshot["layout"]["steps"]
    assert snapshot["product"]["baseline"] == "draft"
    assert snapshot["product"]["changes_path"] == "docs/changes"
    assert snapshot["product"]["archive_changes_path"] == "docs/archive/changes"
    assert snapshot["product"]["call_width"] == "wide"
    assert "framework_version" in snapshot["product"]


def test_board_two_changes_and_no_side_effects(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-031", title="Later").step_intake().step_analyze()
    first = MockChangeBuilder(tmp_path, change_id="CHG-030", title="Earlier").step_intake()
    (first.change_dir / "evidence" / "red").mkdir(parents=True)
    (first.change_dir / "evidence" / "red" / "TASK-001.yaml").write_text(
        "schema_version: 3\n", encoding="utf-8"
    )
    dec = tmp_path / "docs" / "decisions" / "DEC-0042-block.md"
    dec.write_text(
        "---\n"
        "id: DEC-0042\n"
        "title: Block\n"
        "kind: product\n"
        "status: proposed\n"
        "owner: human\n"
        "date: 2026-09-10\n"
        "change: CHG-030\n"
        "---\n\n# Block\n",
        encoding="utf-8",
    )

    before = _tree_sig(tmp_path)
    snapshot = build_board_snapshot(tmp_path)
    assert _tree_sig(tmp_path) == before
    _assert_valid_snapshot(snapshot, repo_root)
    assert [card["id"] for card in snapshot["changes"]] == ["CHG-030", "CHG-031"]
    by_id = {card["id"]: card for card in snapshot["changes"]}
    assert by_id["CHG-030"]["status"] == "normalized"
    assert by_id["CHG-030"]["title"] == "Earlier"
    assert by_id["CHG-030"]["route"] == "code"
    assert by_id["CHG-030"]["path"] == first.change_dir.relative_to(tmp_path).as_posix()
    assert by_id["CHG-030"]["blocked_decisions"] == ["DEC-0042"]
    assert by_id["CHG-030"]["has_red"] is True
    assert by_id["CHG-030"]["has_green"] is False
    assert by_id["CHG-030"]["slice_count"] == 0
    assert by_id["CHG-031"]["status"] == "analyzed"
    assert by_id["CHG-031"]["slice_count"] == 1
    assert "request.md" not in json.dumps(snapshot)
    assert "CR-001" not in json.dumps(snapshot)
    # placement: unique column per status
    index = {
        status: column["id"]
        for column in snapshot["layout"]["columns"]
        for status in column["statuses"]
    }
    assert index[by_id["CHG-030"]["status"]] == "normalized"
    assert index[by_id["CHG-031"]["status"]] == "analyzed"


def test_board_archive_flag_only(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-040", title="Live").step_intake()
    archived = tmp_path / "docs" / "archive" / "changes" / "2026-09-10-CHG-041"
    archived.mkdir(parents=True)
    (archived / "change.yaml").write_text(
        "schema_version: 3\n"
        "id: CHG-041\n"
        "title: Done\n"
        "status: archived\n"
        "intent: feature\n"
        "risk: low\n",
        encoding="utf-8",
    )
    without = build_board_snapshot(tmp_path)
    assert "archive" not in without
    assert [card["id"] for card in without["changes"]] == ["CHG-040"]
    with_archive = build_board_snapshot(tmp_path, include_archive=True)
    _assert_valid_snapshot(with_archive, repo_root)
    assert [card["id"] for card in with_archive["archive"]] == ["CHG-041"]
    assert with_archive["archive"][0]["status"] == "archived"
    assert with_archive["archive"][0]["path"].endswith("CHG-041")


def test_board_uses_config_paths(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["paths"]["changes"] = "work/changes"
    cfg["paths"]["archive"] = "work/archive"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    change_dir = tmp_path / "work" / "changes" / "CHG-050-alt"
    change_dir.mkdir(parents=True)
    (change_dir / "change.yaml").write_text(
        "schema_version: 3\n"
        "id: CHG-050\n"
        "title: Alt path\n"
        "status: normalized\n"
        "intent: feature\n"
        "risk: low\n",
        encoding="utf-8",
    )
    snapshot = build_board_snapshot(tmp_path)
    assert snapshot["product"]["changes_path"] == "work/changes"
    assert snapshot["product"]["archive_changes_path"] == "work/archive/changes"
    assert snapshot["changes"][0]["path"] == "work/changes/CHG-050-alt"


def test_board_skips_unreadable_package(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    broken = tmp_path / "docs" / "changes" / "not-a-change"
    broken.mkdir(parents=True)
    (broken / "change.yaml").write_text("{not yaml", encoding="utf-8")
    snapshot = build_board_snapshot(tmp_path)
    assert snapshot["changes"] == []
    assert snapshot["warnings"]
    _assert_valid_snapshot(snapshot, repo_root)


def test_board_missing_lock_is_hard_error(tmp_path: Path):
    with pytest.raises(BoardError, match="Not a DeltaFuse product"):
        build_board_snapshot(tmp_path)


def test_cli_board_json(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-060", title="CLI").step_intake()
    capsys.readouterr()
    ret = main(["board", str(tmp_path), "--json"])
    out, err = capsys.readouterr()
    assert ret == 0, err
    assert err == ""
    payload = json.loads(out)
    _assert_valid_snapshot(payload, repo_root)
    assert payload["changes"][0]["id"] == "CHG-060"


def test_cli_board_missing_lock(tmp_path: Path, capsys):
    ret = main(["board", str(tmp_path), "--json"])
    out, err = capsys.readouterr()
    assert ret == 2
    assert out == ""
    assert "Board failed:" in err
    assert "Not a DeltaFuse product" in err


def test_board_schema_rejects_missing_layout(repo_root: Path):
    schema = _board_schema(repo_root)
    validator = validator_for(schema)(schema)
    body = {
        "schema_version": 1,
        "product": {"baseline": "draft", "changes_path": "docs/changes"},
        "changes": [],
    }
    messages = [err.message for err in validator.iter_errors(body)]
    assert any("layout" in msg for msg in messages)


def test_board_module_does_not_run_gates(repo_root: Path):
    text = (repo_root / "src" / "deltafuse" / "core" / "board.py").read_text(encoding="utf-8")
    assert "check_gate" not in text
    assert "validate_change_package" not in text
