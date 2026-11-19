import pytest
from pathlib import Path
from deltafuse.core.schemas import SchemaRegistry

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent

@pytest.fixture(scope="session")
def schemas_dir(repo_root: Path) -> Path:
    return repo_root / "process" / "schemas"

@pytest.fixture(scope="session")
def templates_dir(repo_root: Path) -> Path:
    return repo_root / "process" / "templates"

@pytest.fixture(scope="session")
def registry(schemas_dir: Path) -> SchemaRegistry:
    return SchemaRegistry(schemas_dir=schemas_dir)


@pytest.fixture(autouse=True)
def _sync_assets_tests_work_on_a_copy(request, tmp_path, monkeypatch, repo_root: Path):
    """tests/unit/test_sync_assets*.py never reach the checkout's own asset bundle.

    Audit 2026-11-17: scripts/sync_assets.py is imported with REPO and ASSETS pointing at the
    checkout, and some tests reload it; a test (or a subprocess) that forgot its own override
    would replace src/deltafuse/assets in place, and under `pytest -n` every pin check running
    meanwhile would see another framework. Each test of those files starts with the module and
    the environment pointed at a private directory, and the real manifest is compared after it.
    """
    if not request.module.__name__.rsplit(".", 1)[-1].startswith("test_sync_assets"):
        yield
        return
    import sys

    scripts = str(repo_root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import sync_assets

    manifest = repo_root / "src" / "deltafuse" / "assets" / "manifest.json"
    before = manifest.read_bytes()
    guard_repo, guard_assets = tmp_path / "guard-repo", tmp_path / "guard-assets"
    monkeypatch.setattr(sync_assets, "REPO", guard_repo)
    monkeypatch.setattr(sync_assets, "ASSETS", guard_assets)
    monkeypatch.setenv("DELTAFUSE_TEST_REPO", str(guard_repo))
    monkeypatch.setenv("DELTAFUSE_TEST_ASSETS", str(guard_assets))
    yield
    assert manifest.read_bytes() == before, "a sync_assets test rewrote the checkout's asset bundle"
    assert not list(manifest.parent.parent.glob("assets.*")), "a sync_assets test left files beside the bundle"
