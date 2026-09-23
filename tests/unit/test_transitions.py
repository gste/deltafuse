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
