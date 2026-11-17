"""Audit 2026-11, FL-1: "did this Change touch the specification" is the Core's own diff.

A feature skipped the specification Human Gate: after Analyze the Worker set `intent: bugfix`
through the Artifact Writer, wrote no spec-delta.md, added the new requirement to `docs/spec/**`
itself, and the Change converged and archived with no Human Gate receipt at all. Both facts the
`decomposed` and `converged` gates read were the Worker's labels.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import TransitionError, advance_change, set_change_intent
from tests.fixtures.change_builder import MockChangeBuilder

NEW_REQUIREMENT = "\n## REQ-02\n\nWHEN the system starts THE SYSTEM SHALL print a banner.\n"


def _analyzed(tmp_path: Path, repo_root: Path, *, intent: str, cid: str = "CHG-701") -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Walk").step_intake(intent=intent).step_analyze()
    advance_change(builder.change_dir, "analyzed")
    return builder


def _tasks_without_advance(builder: MockChangeBuilder) -> None:
    advance, builder._core_advance = builder._core_advance, lambda gate: None
    try:
        builder.step_decompose()
    finally:
        builder._core_advance = advance


def _write_change(tmp_path: Path, builder: MockChangeBuilder, fields: dict) -> int:
    source = tmp_path / "change-input.json"
    source.write_text(json.dumps({"identity": builder.change_id, "fields": fields}), encoding="utf-8")
    return main(["artifact", "write", "--kind", "change", "--change", str(builder.change_dir), "--input", str(source)])


def test_the_writer_no_longer_takes_intent(tmp_path: Path, repo_root: Path, capsys):
    builder = _analyzed(tmp_path, repo_root, intent="feature")
    assert _write_change(tmp_path, builder, {"intent": "bugfix"}) != 0
    assert "core_owned_field" in capsys.readouterr().err
    assert yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))["intent"] == "feature"


def test_intent_edited_after_intake_is_refused_and_the_recorded_one_decides(tmp_path: Path, repo_root: Path):
    """The same relabel by hand: the gate goes by the intake receipt, and says the field moved."""
    builder = _analyzed(tmp_path, repo_root, intent="feature")
    builder._update_change_yaml({"intent": "bugfix"})
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8") + NEW_REQUIREMENT, encoding="utf-8")
    _tasks_without_advance(builder)

    errors = check_gate(builder.change_dir, "decomposed")
    assert any("Intake closed with 'feature'" in e for e in errors), errors
    assert any("specification Human Gate" in e for e in errors), errors
    with pytest.raises(TransitionError, match="specification Human Gate"):
        advance_change(builder.change_dir, "decomposed")
    # The queue does not offer the bugfix shortcut either.
    assert select_next(build_work_queue(tmp_path)).step == "specify"


def test_a_bugfix_that_adds_a_requirement_does_not_skip_specify(tmp_path: Path, repo_root: Path):
    """The reproduction with an honest label: `bugfix` from Intake on, no spec-delta.md, and the
    requirement written straight into docs/spec."""
    builder = _analyzed(tmp_path, repo_root, intent="bugfix")
    assert select_next(build_work_queue(tmp_path)).step == "decompose"
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8") + NEW_REQUIREMENT, encoding="utf-8")
    _tasks_without_advance(builder)

    errors = check_gate(builder.change_dir, "decomposed")
    assert any("docs/spec/** changed since this Change's Intake" in e and "docs/spec/core.md (modified)" in e for e in errors), errors
    with pytest.raises(TransitionError, match="docs/spec"):
        advance_change(builder.change_dir, "decomposed")
    assert select_next(build_work_queue(tmp_path)).step == "specify"


def test_a_specification_edit_in_analyze_is_still_seen(tmp_path: Path, repo_root: Path):
    """The nearest bypass of a snapshot taken at `analyzed`: edit before that gate. The Core's
    record is the intake gate's."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-702", title="Walk").step_intake(intent="bugfix").step_analyze()
    (tmp_path / "docs" / "spec" / "extra.md").write_text("# Extra\n\n## REQ-90\n\nNew.\n", encoding="utf-8")
    advance_change(builder.change_dir, "analyzed")
    _tasks_without_advance(builder)
    errors = check_gate(builder.change_dir, "decomposed")
    assert any("docs/spec/extra.md (added)" in e for e in errors), errors


def test_a_specification_edit_after_decompose_stops_every_later_gate(tmp_path: Path, repo_root: Path):
    """The other bypass: skip Specify honestly, then write the requirement during Implement."""
    builder = _analyzed(tmp_path, repo_root, intent="bugfix", cid="CHG-703")
    _tasks_without_advance(builder)
    advance_change(builder.change_dir, "decomposed")
    builder.step_declare()
    assert not any("docs/spec" in e for e in check_gate(builder.change_dir, "declaring"))

    spec = tmp_path / "docs" / "spec" / "core.md"
    original = spec.read_bytes()
    spec.write_text(spec.read_text(encoding="utf-8") + NEW_REQUIREMENT, encoding="utf-8")
    for gate in ("declaring", "implemented", "converged"):
        errors = check_gate(builder.change_dir, gate)
        assert any("docs/spec/** changed since this Change's Intake" in e for e in errors), (gate, errors)

    # A checkout that only changed line endings did not change the specification.
    spec.write_bytes(original.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert not any("docs/spec/** changed" in e for e in check_gate(builder.change_dir, "declaring"))


def test_intent_is_set_through_the_core_until_intake_closes(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    assert main(["new", str(tmp_path), "CHG-704", "--title", "Bug"]) == 0
    change = tmp_path / "docs" / "changes" / "CHG-704"
    assert main(["state", str(change), "--change", "--intent", "bugfix"]) == 0
    assert yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["intent"] == "bugfix"
    assert main(["state", str(change), "--change", "--intent", "sideways"]) == 1

    request = change / "request.md"
    request.write_text(request.read_text(encoding="utf-8") + "\n- CR-001 (observation): it crashes.\n", encoding="utf-8")
    result = advance_change(change, "intake")
    assert result["to"] == "analyzing"
    from deltafuse.core.transitions import intake_facts

    facts = intake_facts(tmp_path, "CHG-704")
    assert facts["intent"] == "bugfix" and "docs/spec/_capabilities.yaml" in facts["spec_tree"]

    capsys.readouterr()
    assert main(["state", str(change), "--change", "--intent", "feature"]) == 1
    assert "fixed when Intake closes" in capsys.readouterr().err
    with pytest.raises(TransitionError, match="fixed when Intake closes"):
        set_change_intent(change, "feature")
    assert yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["intent"] == "bugfix"
