"""Red is judged against a base that holds what Specify wrote.

Fuse-Back, shopkit (2026-10-08): Specify changed `docs/spec/shared/general_utilities.md` and nobody
committed between steps (the bench runner does; a real product's host need not). Red's
Core-computed `changed_paths` took the spec file along with the test, `deltafuse evidence` said
"authentic", and the `declaring` gate refused it as outside the Declare contract - a step later,
with no way back but the human. The `specified` gate now records the digests of the uncommitted
specification files it accepted; evidence leaves out a file whose bytes still match. A spec file
changed after acceptance still counts, and evidence names it at once.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.transitions import load_receipts
from tests.fixtures.change_builder import MockChangeBuilder

SPEC = "docs/spec/shared/utilities.md"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    )


def _specified_with_uncommitted_spec(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    (tmp_path / SPEC).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / SPEC).write_text("# utilities\n\n## REQ-U-01\n\nOld.\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "base")
    builder = MockChangeBuilder(tmp_path, change_id="CHG-210", title="Blank").step_intake().step_analyze()
    (tmp_path / SPEC).write_text("# utilities\n\n## REQ-U-01\n\nNew: is_blank.\n", encoding="utf-8")
    return builder.step_specify()


def _red(tmp_path: Path, builder: MockChangeBuilder):
    test = tmp_path / "tests" / "test_task-001.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text("def test_blank():\n    assert 1 == 2\n", encoding="utf-8")
    return run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_task-001.py"],
    )


def test_the_specified_gate_records_the_uncommitted_spec(tmp_path: Path, repo_root: Path):
    _specified_with_uncommitted_spec(tmp_path, repo_root)
    specified = [r for r in load_receipts(tmp_path, "CHG-210") if r.get("gate") == "specified"]
    assert specified and SPEC in (specified[-1].get("spec_snapshot") or {})


def test_red_leaves_out_the_spec_specify_wrote(tmp_path: Path, repo_root: Path):
    builder = _specified_with_uncommitted_spec(tmp_path, repo_root).step_decompose()
    outcome = _red(tmp_path, builder)
    assert SPEC not in outcome.payload["changed_paths"]
    assert "tests/test_task-001.py" in outcome.payload["changed_paths"]
    assert not any("outside the phase contract" in e for e in outcome.errors), outcome.errors
    gate = check_gate(builder.change_dir, "declaring")
    assert not any(SPEC in e for e in gate), gate


def test_a_spec_changed_after_acceptance_is_named_at_once(tmp_path: Path, repo_root: Path):
    builder = _specified_with_uncommitted_spec(tmp_path, repo_root).step_decompose()
    (tmp_path / SPEC).write_text("# utilities\n\n## REQ-U-01\n\nEdited in Declare.\n", encoding="utf-8")
    outcome = _red(tmp_path, builder)
    assert SPEC in outcome.payload["changed_paths"]
    assert not outcome.authentic
    named = [e for e in outcome.errors if SPEC in e]
    assert named and "outside the phase contract" in named[0]
    assert "after the `specified` gate" in named[0]
