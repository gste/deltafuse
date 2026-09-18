"""DF3-005: distribution, scaffolding and fail-closed upgrade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.assets import bundle_root, resolve_assets
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import InstallationError, install
from deltafuse.core.scaffold import ScaffoldError, scaffold_change


def test_scaffold_creates_minimal_package_without_closing_intake(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-501-auth", route="code", title="Auth")

    data = yaml.safe_load((change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert data["id"] == "CHG-501-auth"
    assert data["status"] == "normalized", "scaffolding must not close Intake"
    assert data["route"] == "code"
    request = (change_dir / "request.md").read_text(encoding="utf-8")
    assert "claims" not in request, "scaffolding fabricates no claims"
    for sub in ("slices", "tasks", "evidence"):
        assert (change_dir / sub).is_dir()
    assert check_gate(change_dir, "intake"), "Intake gate must stay open"


def test_scaffold_is_deterministic_and_refuses_collisions(
    tmp_path: Path, repo_root: Path
):
    install(target_dir=tmp_path / "a", framework_root=repo_root)
    install(target_dir=tmp_path / "b", framework_root=repo_root)
    first = scaffold_change(tmp_path / "a", "CHG-502", route="ops")
    second = scaffold_change(tmp_path / "b", "CHG-502", route="ops")

    def normalized(path: Path) -> list[str]:
        lines = (path / "change.yaml").read_text(encoding="utf-8").splitlines()
        return [line for line in lines if not line.startswith("created:")]

    assert normalized(first) == normalized(second)

    scaffold_change(tmp_path / "a", "CHG-503")
    with pytest.raises(ScaffoldError, match="already exists"):
        scaffold_change(tmp_path / "a", "CHG-503")


def test_scaffold_rejects_bad_ids_and_routes(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    with pytest.raises(ScaffoldError, match="CHG-"):
        scaffold_change(tmp_path, "bad id")
    with pytest.raises(ScaffoldError, match="route"):
        scaffold_change(tmp_path, "CHG-504", route="product")


def test_new_cli_reports_success(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret = main(["new", str(tmp_path), "CHG-505", "--route", "docs", "--json"])
    out, _ = capsys.readouterr()
    payload = json.loads(out)
    assert ret == 0
    assert payload["ok"] is True
    assert payload["route"] == "docs"

    assert main(["new", str(tmp_path), "CHG-505"]) != 0


def test_wheel_mode_install_uses_bundle_without_source_checkout(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    """Pure wheel install: assets come from the packaged bundle and the lock
    pins the bundle manifest digest, not a source-tree hash."""
    from deltafuse.core import assets as assets_module
    from deltafuse.core import installer as installer_module

    monkeypatch.setattr(assets_module, "source_assets_root", lambda: None)
    monkeypatch.setattr(installer_module, "source_assets_root", lambda: None)

    result = install(target_dir=tmp_path, framework_root=None)

    assert result.version, "wheel install takes the version from the package"
    assert not (tmp_path / "AGENTS.md").exists()
    assert result.agents_md_mode == "preserve"
    assert (tmp_path / ".deltafuse" / "config.yaml").is_file()
    bundle = resolve_assets("templates", prefer="bundle")
    manifest_path = bundle.parent / "manifest.json"
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    lock = (tmp_path / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8")
    assert f"content_hash: sha256:{digest}" in lock


def test_fail_closed_upgrade_blocks_on_active_changes(tmp_path: Path, repo_root: Path):
    """C-02: an upgrade across pin revisions never re-signs active evidence —
    it halts until Changes are closed or migrated."""
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-506")

    lock = tmp_path / ".deltafuse" / "lock.yaml"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace(
            "content_hash: sha256:", "content_hash: sha256:deadbeef"
        ),
        encoding="utf-8",
    )

    with pytest.raises(InstallationError, match="Fail-closed upgrade"):
        install(target_dir=tmp_path, framework_root=repo_root, force=True)
    assert change_dir.is_dir(), "upgrade must not touch active Changes"

    # With no active Changes the upgrade proceeds.
    import shutil

    shutil.rmtree(tmp_path / "docs" / "changes" / "CHG-506")
    install(target_dir=tmp_path, framework_root=repo_root, force=True)


def test_source_and_bundle_schemas_are_semantically_identical(repo_root: Path):
    """One canonical content: every schema in process/schemas equals the
    bundle copy byte-for-byte (no drift between checkout and wheel)."""
    bundle = bundle_root()
    if bundle is None:
        pytest.skip("bundle not importable in this environment")
    source = repo_root / "process" / "schemas"
    for path in sorted(source.glob("*.schema.yaml")):
        assert path.read_bytes() == (bundle / "schemas" / path.name).read_bytes()
