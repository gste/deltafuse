"""A bugfix stopped by another Change's specification edit is offered an exit that works (O4).

Round 2 (open item 4): a bugfix that skipped Specify, running beside a Change whose accepted
specification moved `docs/spec/**`, was stopped at its next gate and told the human sends it back
with `decide --spec --status rejected`; that exited 1 with "spec-delta.md is missing", and only
`decide --close` got out.
"""

from __future__ import annotations

import re
from pathlib import Path

from deltafuse.cli import main
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _bugfix_past_decompose(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-341", title="Bugfix").step_intake(intent="bugfix")
    builder.step_analyze().step_decompose()
    # Another Change's accepted specification lands in docs/spec/**.
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## REQ-77 Other\n\nThe system MUST log.\n", encoding="utf-8")
    return builder


def _offered(errors: list[str]) -> list[str]:
    return [m for e in errors for m in re.findall(r"`(deltafuse decide [^`]+)`", e)]


def test_a_bugfix_with_no_spec_delta_is_offered_the_close(tmp_path: Path, repo_root: Path, capsys):
    builder = _bugfix_past_decompose(tmp_path, repo_root)
    errors = check_gate(builder.change_dir, "declaring")
    offered = _offered(errors)
    assert offered and all("--spec" not in cmd for cmd in offered), errors
    (command,) = {cmd for cmd in offered}
    argv = command.replace("<change-dir>", str(builder.change_dir)).replace('"<why>"', "why").split()[1:]
    assert main(argv) == 0, capsys.readouterr()


def test_a_bugfix_with_a_spec_delta_is_offered_the_rejection_and_it_works(tmp_path: Path, repo_root: Path, capsys):
    """The twin: with a spec-delta.md to answer, the rejection is the exit, and it runs."""
    builder = _bugfix_past_decompose(tmp_path, repo_root)
    (builder.change_dir / "spec-delta.md").write_text(
        f"---\nchange: {builder.change_id}\nstatus: proposed\nslices: [SLICE-01]\n"
        "added: []\nmodified: []\nremoved: []\n---\n\n# Spec\n",
        encoding="utf-8",
    )
    errors = check_gate(builder.change_dir, "declaring")
    offered = _offered(errors)
    assert any("--spec --status rejected" in cmd for cmd in offered), errors
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "rejected"]) == 0, capsys.readouterr()
