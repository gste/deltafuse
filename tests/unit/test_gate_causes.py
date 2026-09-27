"""A gate that meets a hand-written structural file names that first (P7, 2026-09-26)."""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.fsm import check_gate
from tests.fixtures.change_builder import MockChangeBuilder


def test_schema_errors_of_a_hand_written_file_start_with_the_cause(tmp_path: Path):
    builder = MockChangeBuilder(tmp_path, "CHG-601").step_intake().step_analyze()
    (builder.change_dir / "routing.yaml").write_text("claims: nonsense\n", encoding="utf-8")

    errors = check_gate(builder.change_dir, "analyzed")
    assert any("routing.yaml" in err for err in errors[1:]), errors  # the file's own errors follow
    assert "routing.yaml was written by hand" in errors[0]
    assert "deltafuse artifact write --kind routing --change docs/changes/CHG-601" in errors[0]


def test_a_gate_without_errors_adds_nothing(tmp_path: Path):
    builder = MockChangeBuilder(tmp_path, "CHG-602").step_intake()
    assert check_gate(builder.change_dir, "intake") == []
