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
