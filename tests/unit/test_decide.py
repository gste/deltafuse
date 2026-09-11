"""Human Gate apply: decide records a click, next does not auto-accept."""

from __future__ import annotations

from pathlib import Path

from deltafuse.cli import main
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from tests.fixtures.change_builder import MockChangeBuilder
from tests.unit.test_queue import _write_proposed_dec


def test_decide_accepts_decision_and_unblocks(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-071", title="Decide").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    dec = _write_proposed_dec(tmp_path, "CHG-071")
    rel = str(builder.change_dir)
    ret = main(["decide", rel, "--decision", "DEC-0001", "--status", "accepted"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "accepted" in out
    meta, _ = parse_frontmatter(dec.read_text(encoding="utf-8"))
    assert meta["status"] == "accepted"
    selected = select_next(build_work_queue(tmp_path))
    assert selected is not None
    assert selected.skill == "analyze"


def test_decide_does_not_run_from_next(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-072", title="No auto").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    dec = _write_proposed_dec(tmp_path, "CHG-072")
    before = dec.read_text(encoding="utf-8")
    assert main(["next", str(tmp_path)]) == 1
    assert dec.read_text(encoding="utf-8") == before


def test_decide_rejects_without_flags(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret = main(["decide", str(tmp_path), "--status", "accepted"])
    _, err = capsys.readouterr()
    assert ret == 1
    assert "exactly one" in err
