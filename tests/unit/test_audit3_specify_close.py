"""The Specify close pass proposes and then runs `next`; it never runs `advance --gate specified`.

Audit 3 (A-11, B-7): the skill, using.md and the `next` reason told the Worker to close Specify
with `deltafuse advance <change-dir> --gate specified`. That call always fails there - before the
verdict the gate needs the human's acceptance, after it the Change is already `specified`
(decide applied the gate) - and its error named `deltafuse decide`, a command the Worker could
run itself with no password set.
"""

from __future__ import annotations

import json
from pathlib import Path

from deltafuse.cli import main
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder
from tests.unit.test_decide import _change_status, _spec_proposed
from tests.unit.test_specify import _set_slice_status

REPO = Path(__file__).resolve().parents[2]


def _all_slices_specified(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-301", title="Close").step_intake().step_analyze()
    builder._core_advance("analyzed")
    _set_slice_status(builder.change_dir, "SLICE-01", "specified")
    return builder


def test_next_close_pass_proposes_and_names_next_not_advance(tmp_path: Path, repo_root: Path, capsys):
    _all_slices_specified(tmp_path, repo_root)
    assert main(["next", str(tmp_path), "--human", "--step", "specify"]) == 0
    out, _ = capsys.readouterr()
    assert "specify_pass: close" in out
    assert "--gate specified" not in out
    assert "--status specification-proposed" in out
    assert "deltafuse decide" not in out

    assert main(["next", str(tmp_path), "--json", "--step", "specify"]) == 0
    selected = json.loads(capsys.readouterr()[0])["selected"]
    assert "advance" not in selected["reason"]
    assert "specification-proposed" in selected["reason"]


def test_advance_before_the_verdict_names_no_decide_command(tmp_path: Path, repo_root: Path, capsys):
    builder = _spec_proposed(tmp_path, repo_root, "CHG-302", "proposed")
    assert main(["advance", str(builder.change_dir), "--gate", "specified"]) == 1
    _, err = capsys.readouterr()
    assert "Human Gate" in err
    assert "deltafuse decide" not in err
    assert "deltafuse next" in err
    assert _change_status(builder) == "specification-proposed"


def test_advance_after_the_verdict_points_to_next(tmp_path: Path, repo_root: Path, capsys):
    """The twin path: the human accepted (decide applied the gate) and the Worker then runs advance."""
    builder = _spec_proposed(tmp_path, repo_root, "CHG-303", "proposed")
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0
    capsys.readouterr()
    assert main(["advance", str(builder.change_dir), "--gate", "specified"]) == 1
    _, err = capsys.readouterr()
    assert "already 'specified'" in err
    assert "deltafuse next" in err
    assert "deltafuse decide" not in err


def test_skill_and_using_close_with_next():
    for rel in (
        "process/skills/specify/SKILL.md",
        "src/deltafuse/assets/skills/specify/SKILL.md",
        "docs/using.md",
        "docs/using.ru.md",
        "docs/workflow.md",
        "docs/workflow.ru.md",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "--gate specified`" not in text.replace("advance --gate specified` yet", ""), rel
