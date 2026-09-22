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
    assert check_gate(builder.change_dir, "specified") == []


def _spec_proposed(tmp_path: Path, repo_root: Path, change_id: str, delta_status: str):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=change_id, title="Spec gate").step_intake().step_analyze()
    builder._core_advance("analyzed")
    (builder.change_dir / "spec-delta.md").write_text(
        f"---\nchange: {change_id}\nstatus: {delta_status}\nslices: [SLICE-01]\n"
        "added: []\nmodified: []\nremoved: []\n---\n\n# Spec\n",
        encoding="utf-8",
    )
    builder._update_change_yaml({"status": "specification-proposed"})
    return builder


def _change_status(builder) -> str:
    import yaml

    return yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))["status"]


def test_decide_spec_accepted_applies_the_transition_with_a_receipt(tmp_path: Path, repo_root: Path):
    """decide --spec used to write 'specified' into change.yaml itself: no
    transition receipt, so the chain replay refused every later Core command and
    no step existed to repair it. The verdict now goes through advance_change."""
    from deltafuse.core.transitions import load_receipts, receipt_chain_errors

    builder = _spec_proposed(tmp_path, repo_root, "CHG-076", "proposed")
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0

    assert _change_status(builder) == "specified"
    last = [r for r in load_receipts(tmp_path, "CHG-076") if r.get("kind") == "transition"][-1]
    assert (last["gate"], last["from"], last["to"]) == ("specified", "specification-proposed", "specified")
    assert receipt_chain_errors(tmp_path, builder.change_dir) == []
    assert main(["check-gate", str(builder.change_dir), "--gate", "specified"]) == 0


def test_advance_from_proposed_still_needs_the_spec_receipt(tmp_path: Path, repo_root: Path, capsys):
    """Opening specification-proposed -> specified in the gate table must not let
    the Worker skip the Human Gate: a hand-accepted spec-delta without decide's
    receipt still fails the gate, and the status does not move."""
    builder = _spec_proposed(tmp_path, repo_root, "CHG-077", "accepted")
    assert main(["advance", str(builder.change_dir), "--gate", "specified"]) == 1
    _, err = capsys.readouterr()
    assert "without deltafuse decide" in err
    assert _change_status(builder) == "specification-proposed"


def _analyzed_with_delta(tmp_path: Path, repo_root: Path, change_id: str, delta: str):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=change_id, title="Propose").step_intake().step_analyze()
    builder._core_advance("analyzed")
    (builder.change_dir / "spec-delta.md").write_text(delta, encoding="utf-8")
    return builder


def _propose(builder) -> int:
    return main(["state", str(builder.change_dir), "--change", "--status", "specification-proposed"])


def test_proposing_a_malformed_spec_delta_goes_back_to_the_worker(tmp_path: Path, repo_root: Path, capsys):
    """q0 runs M01-1 and M01-2: the model proposed spec-deltas without the
    frontmatter delimiters or without added/modified/removed. The Core let the
    proposal through, the Human Gate could neither accept nor fix it, and both
    runs died on specify. Proposing now requires the machine checks of the
    specified gate; the errors go to the Worker and the status stays put."""
    no_delimiters = _analyzed_with_delta(
        tmp_path / "a", repo_root, "CHG-078", "change: CHG-078\nstatus: proposed\n\n# Spec\n"
    )
    assert _propose(no_delimiters) == 1
    _, err = capsys.readouterr()
    assert "not ready for the Human Gate" in err and "frontmatter" in err
    assert _change_status(no_delimiters) == "analyzed"

    missing_ops = _analyzed_with_delta(
        tmp_path / "b", repo_root, "CHG-079",
        "---\nchange: CHG-079\nstatus: proposed\nslices: [SLICE-01]\n---\n\n# Spec\n",
    )
    assert _propose(missing_ops) == 1
    _, err = capsys.readouterr()
    assert "'added' is a required property" in err
    assert _change_status(missing_ops) == "analyzed"


def test_proposing_a_self_accepted_spec_delta_is_refused(tmp_path: Path, repo_root: Path, capsys):
    """A spec delta the Worker marked accepted itself fails the same check."""
    builder = _analyzed_with_delta(
        tmp_path, repo_root, "CHG-080",
        "---\nchange: CHG-080\nstatus: accepted\nslices: [SLICE-01]\n"
        "added: []\nmodified: []\nremoved: []\n---\n\n# Spec\n",
    )
    assert _propose(builder) == 1
    _, err = capsys.readouterr()
    assert "without deltafuse decide" in err


def test_decide_spec_reports_a_transition_that_did_not_land(tmp_path: Path, repo_root: Path, capsys):
    """If the spec delta breaks after the proposal, accepting it records the
    click but cannot move the Change. decide used to exit 0 with the errors on
    stderr, so the caller clicked the same gate again - 76 times in run M01-1."""
    builder = _spec_proposed(tmp_path, repo_root, "CHG-081", "proposed")
    delta = builder.change_dir / "spec-delta.md"
    delta.write_text(delta.read_text(encoding="utf-8").replace("added: []\n", ""), encoding="utf-8")

    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 1
    _, err = capsys.readouterr()
    assert "gate:" in err and "'added' is a required property" in err
    assert _change_status(builder) == "specification-proposed"


def test_worker_cannot_advance_a_proposed_spec_past_the_human(tmp_path: Path, repo_root: Path, capsys):
    """Campaign 20260921T072327Z: seven seconds after proposing, the model ran
    `deltafuse advance --gate specified` itself and the Change reached
    'specified' with spec-delta.md still 'proposed' and no spec receipt - the
    Human Gate skipped. Leaving specification-proposed needs the human's
    accepted verdict, recorded by decide."""
    builder = _spec_proposed(tmp_path, repo_root, "CHG-082", "proposed")
    assert main(["advance", str(builder.change_dir), "--gate", "specified"]) == 1
    _, err = capsys.readouterr()
    assert "Human Gate" in err
    assert _change_status(builder) == "specification-proposed"

    # The human's click is what moves it.
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0
    assert _change_status(builder) == "specified"
