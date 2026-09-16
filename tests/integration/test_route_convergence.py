"""DF3-002: full lifecycle to archive for code, docs and ops routes."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.archiver import archive_change, is_change_id_archived
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _full_change(tmp_path: Path, repo_root: Path, change_id: str, route: str) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id=change_id, title=route.title(), route=route)
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_declare()
        .step_implement()
        .step_verify()
    )


_ROUTE_IDS = {"code": "CHG-910", "docs": "CHG-920", "ops": "CHG-930"}


@pytest.mark.parametrize("route", ["code", "docs", "ops"])
def test_route_reaches_archive_with_passing_converged_gate(
    tmp_path: Path, repo_root: Path, route: str
):
    change_id = _ROUTE_IDS[route]
    builder = _full_change(tmp_path, repo_root, change_id, route)

    assert check_gate(builder.change_dir, "converged") == []

    dest = archive_change(builder.change_dir, repo_root=tmp_path)
    assert dest.is_dir()
    assert is_change_id_archived(change_id, tmp_path)
    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    assert data["status"] == "archived"


def test_hand_set_terminal_rejected_archives_without_converged_gate(
    tmp_path: Path, repo_root: Path
):
    """DF3-002: explicit non-converged terminal outcomes keep their own policy —
    no converged gate replay, but still archived atomically."""
    builder = _full_change(tmp_path, repo_root, "CHG-940", "code")
    builder._update_change_yaml({"status": "rejected"})

    dest = archive_change(builder.change_dir, repo_root=tmp_path)
    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    assert data["status"] == "archived"


def test_force_cannot_skip_converged_gate_on_hand_set_converged(
    tmp_path: Path, repo_root: Path
):
    """`force` bypasses only the archive-immutability refusal, never the gate:
    a hand-set `converged` without evidence must not archive even with force."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-950", title="Force")
        .step_intake()
    )
    builder._update_change_yaml({"status": "converged"})

    with pytest.raises(Exception, match="gate errors|transition chain invalid"):
        archive_change(builder.change_dir, repo_root=tmp_path, force=True)
