"""Core status transitions that the tables must refuse."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

def test_a_decided_spec_cannot_be_reproposed(tmp_path: Path, repo_root: Path):
    """The status table maps from -> to; reading it backwards let a Change go
    from `specified` back to `specification-proposed`, reopening a Human Gate
    the human had already answered (found 2026-09-23)."""
    from deltafuse.core.installer import install
    from deltafuse.core.transitions import TransitionError, set_artifact_status
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-830", title="Reopen")
    builder.step_intake().step_analyze().step_specify()
    status = yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))["status"]
    assert status == "specified"

    with pytest.raises(TransitionError, match="cannot set Change status"):
        set_artifact_status(builder.change_dir, status="specification-proposed", change_status=True)


def test_record_trace_warnings_writes_the_p12_advisory_findings(tmp_path: Path, repo_root: Path):
    """P12: the Core writes its own advisory findings at `converged`, not the Worker - a
    warning printed to stderr and never written anywhere is one Verify can silently walk
    past."""
    from deltafuse.core.installer import install
    from deltafuse.core.transitions import _record_trace_warnings
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("workflow", {})["trace_claims"] = "warn"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    builder = MockChangeBuilder(tmp_path, change_id="CHG-080", title="Recorded")
    builder.change_dir.mkdir(parents=True, exist_ok=True)
    (builder.change_dir / "request.md").write_text(
        "# Request\n\n- CR-001 (Expectation): `get_stats(key)` must return `total_calls`.\n",
        encoding="utf-8",
    )
    routing = {"change": builder.change_id, "claims": {"CR-001": {"primary_capability": "system.core"}}}
    (builder.change_dir / "routing.yaml").write_text(yaml.safe_dump(routing), encoding="utf-8")
    slices = builder.change_dir / "slices"
    slices.mkdir(parents=True, exist_ok=True)
    (slices / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-080\ntitle: T\nstatus: draft\n"
        "primary_capability: system.core\nspec_refs: []\nclaims: [CR-001]\n---\n\n# SLICE-01\n",
        encoding="utf-8",
    )

    dest = builder.change_dir / "evidence" / "verification" / "trace_warnings.yaml"
    assert not dest.is_file()
    _record_trace_warnings(builder.change_dir)
    assert dest.is_file()
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert any("CR-001" in w for w in data["warnings"])

    # A claim fixed since the last pass does not leave a stale finding on record.
    (builder.change_dir / "request.md").write_text("# Request\n\n- CR-001: no kind stated.\n", encoding="utf-8")
    _record_trace_warnings(builder.change_dir)
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["warnings"] == []


def test_record_trace_warnings_writes_nothing_when_off(tmp_path: Path, repo_root: Path):
    from deltafuse.core.installer import install
    from deltafuse.core.transitions import _record_trace_warnings
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-081", title="Off").step_intake()
    _record_trace_warnings(builder.change_dir)
    assert not (builder.change_dir / "evidence").exists()
