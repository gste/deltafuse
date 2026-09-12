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
    # Real flow: a Change reaches blocked-on-decision only after the intake gate.
    builder._core_advance("intake")
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


def test_hand_written_accepted_does_not_close_analyzed(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-073", title="Forge accept").step_intake().step_analyze()
    dec = _write_proposed_dec(tmp_path, "CHG-073")
    text = dec.read_text(encoding="utf-8").replace("status: proposed", "status: accepted")
    dec.write_text(text, encoding="utf-8")
    from deltafuse.core.fsm import check_gate

    errs = check_gate(builder.change_dir, "analyzed")
    assert any("without deltafuse decide" in e for e in errs)
    ret = main(["decide", str(builder.change_dir), "--decision", "DEC-0001", "--status", "accepted"])
    assert ret == 1
    dec.write_text(text.replace("status: accepted", "status: proposed"), encoding="utf-8")
    assert main(["decide", str(builder.change_dir), "--decision", "DEC-0001", "--status", "accepted"]) == 0
    assert check_gate(builder.change_dir, "analyzed") == []


def test_bootstrap_decision_with_null_change(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    dec = _write_proposed_dec(tmp_path, "CHG-074")
    text = dec.read_text(encoding="utf-8").replace("change: CHG-074", "change: null")
    dec.write_text(text, encoding="utf-8")
    assert main(["decide", str(tmp_path), "--decision", "DEC-0001", "--status", "accepted"]) == 0
    meta, _ = parse_frontmatter(dec.read_text(encoding="utf-8"))
    assert meta["status"] == "accepted"
    journal = (tmp_path / ".deltafuse" / "gate-journal.jsonl").read_text(encoding="utf-8")
    assert '"kind": "decision"' in journal
    assert "DEC-0001" in journal


def test_hand_written_spec_accepted_does_not_close_specified(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-075", title="Forge spec").step_intake().step_analyze()
    builder._core_advance("analyzed")
    spec_delta = (
        f"---\nchange: {builder.change_id}\nstatus: accepted\nslices: [SLICE-01]\n"
        "added: []\nmodified: []\nremoved: []\n---\n\n# Spec\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    builder._update_change_yaml({"status": "specified"})
    from deltafuse.core.fsm import check_gate

    errs = check_gate(builder.change_dir, "specified")
    assert any("without deltafuse decide" in e for e in errs)
    builder._update_change_yaml({"status": "specification-proposed"})
    spec_delta_proposed = spec_delta.replace("status: accepted", "status: proposed")
    (builder.change_dir / "spec-delta.md").write_text(spec_delta_proposed, encoding="utf-8")
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0
    builder._core_advance("specified")
    assert check_gate(builder.change_dir, "specified") == []
