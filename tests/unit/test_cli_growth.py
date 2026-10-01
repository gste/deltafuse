"""Two small CLI changes from the log analysis of 2026-09-26.

P9: a wrong subcommand says what was probably meant. Workers called the host's tool
    name as a command (`deltafuse artifact_write`, 8 times) and got a list of every command.
P2: an Artifact Writer call leaves a journal line, refused or not. `artifact write` was
    invisible to the command journal, so no metric could tell a Worker that fought the
    Writer from one that never touched it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from deltafuse import cli


def _run(argv: list[str], capsys) -> tuple[int, str]:
    try:
        code = cli.main(argv)
    except SystemExit as ex:
        code = int(ex.code) if isinstance(ex.code, int) else 2
    captured = capsys.readouterr()
    return code, captured.err + captured.out


def test_a_tool_name_used_as_a_command_gets_the_command_it_meant(capsys):
    code, text = _run(["artifact_write"], capsys)
    assert code == 2
    assert "Did you mean: deltafuse artifact write" in text


def test_the_hint_survives_either_argparse_quoting_of_choices(capsys):
    """argparse quotes the choices in `invalid choice: ... (choose from ...)` on some
    Python versions (3.10/3.11) and does not on others (3.12+, CI runs both): the choice
    value itself is unquoted-and-quoted the same way regardless, but the list of valid
    choices in the message text is not - reading it from the parser's own subparsers
    action instead must not care which wording is in front of it. Reproduced in CI on a
    matrix Python that quotes: the hint silently stopped firing (2026-09-27), because the
    old code split the quoted list on commas without stripping the quote characters, so
    `given in choices` and the difflib match against `"'artifact'"` (with quotes) never hit."""
    parser = cli._HintingParser(prog="deltafuse")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("artifact")
    sub.add_parser("check-gate")
    with pytest.raises(SystemExit):
        parser.error("argument command: invalid choice: 'artifact_write' (choose from 'artifact', 'check-gate')")
    text = capsys.readouterr().err
    assert "Did you mean: deltafuse artifact write" in text


def test_a_typo_gets_the_nearest_command_and_nonsense_gets_none(capsys):
    _, text = _run(["chek-gate"], capsys)
    assert "Did you mean: deltafuse check-gate" in text
    _, text = _run(["zzzzzz"], capsys)
    assert "Did you mean" not in text and "invalid choice" in text


@pytest.fixture()
def journal(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr(cli, "_journal", lambda start, **event: events.append({"start": str(start), **event}))
    return events


def test_a_refused_writer_call_is_journaled_with_its_reason(tmp_path: Path, journal, capsys):
    payload = tmp_path / "in.json"
    payload.write_text(json.dumps({"identity": "TASK-001", "fields": {"title": "x"}, "body": "b"}), encoding="utf-8")
    real_out, real_err = sys.stdout, sys.stderr

    code, text = _run(
        ["artifact", "write", "--kind", "task", "--change", str(tmp_path), "--input", str(payload)], capsys
    )
    assert code != 0 and "missing_change_authority" in text  # the Worker still sees the refusal
    assert sys.stdout is real_out and sys.stderr is real_err  # and the streams are given back

    (event,) = journal
    assert event["cmd"] == "artifact" and event["sub"] == "write" and event["kind"] == "task"
    assert event["ok"] is False and event["refusal"] == "missing_change_authority"
    assert any("change.yaml" in line for line in event["errors"])
    assert event["start"] == str(tmp_path)


def test_only_writes_are_journaled(tmp_path: Path, journal, capsys):
    _run(["artifact", "describe", "--kind", "task"], capsys)
    _run(["validate-config", str(tmp_path)], capsys)
    assert [e for e in journal if e.get("cmd") == "artifact"] == []


def test_advance_converged_prints_the_p12_advisory_findings(tmp_path: Path, monkeypatch, capsys):
    """F15: the Worker makes one call to close a gate now, `advance`, so the advisory
    claim-to-test findings that `check-gate` printed come out of `advance`. They are
    advice, never a refusal: the transition still happens and the exit code is 0."""
    monkeypatch.setattr(cli, "_journal", lambda start, **event: None)
    monkeypatch.setattr(
        cli, "advance_change",
        lambda target, gate: {"ok": True, "gate": gate, "from": "verifying", "to": "converged", "receipt": "a" * 64},
    )
    monkeypatch.setattr(cli, "claim_trace_warnings", lambda target: ["CR-013 names no test"])
    code = cli.main(["advance", str(tmp_path), "--gate", "converged"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Gate converged (advisory): CR-013 names no test" in captured.err
    # another gate prints none
    assert cli.main(["advance", str(tmp_path), "--gate", "analyzed"]) == 0
    assert "advisory" not in capsys.readouterr().err
