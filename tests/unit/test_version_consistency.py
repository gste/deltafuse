import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_version_file_is_release_version() -> None:
    release = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", release)


def test_pyproject_and_dunder_version_match() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is not None:
        pyproject = tomllib.loads(pyproject_text)
        assert "version" not in pyproject["project"]
        assert "version" in pyproject["project"]["dynamic"]
        assert pyproject["tool"]["setuptools"]["dynamic"]["version"]["file"] == ["VERSION"]
    else:
        assert 'dynamic = ["version"]' in pyproject_text
        assert 'version = {file = ["VERSION"]}' in pyproject_text
    init = (REPO_ROOT / "src" / "deltafuse" / "__init__.py").read_text(encoding="utf-8")
    assert 'version("deltafuse")' in init
    assert '/ "VERSION"' in init


def test_templates_use_schema_valid_version_marker() -> None:
    for base in (REPO_ROOT / "process" / "templates", REPO_ROOT / "src" / "deltafuse" / "assets" / "templates"):
        config_text = (base / ".deltafuse" / "config.yaml").read_text(encoding="utf-8")
        change_text = (base / "change" / "change.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(config_text)
        change = yaml.safe_load(change_text)
        assert config["framework"]["version"] == "0.0.0"
        assert config["framework"]["source"] == "deltafuse://v0.0.0"
        assert change["framework"]["version"] == "0.0.0"
        assert config_text.count("# deltafuse:version-template") == 2
        assert change_text.count("# deltafuse:version-template") == 1


def test_release_version_is_not_duplicated_in_current_sources() -> None:
    release = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    scanned = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "src" / "deltafuse" / "__init__.py",
        REPO_ROOT / "process" / "templates",
        REPO_ROOT / "src" / "deltafuse" / "assets" / "templates",
        REPO_ROOT / "docs" / "contracts" / "board-snapshot.md",
        REPO_ROOT / "docs" / "state-machine.ru.md",
    ]
    for path in scanned:
        if path.is_file():
            assert release not in path.read_text(encoding="utf-8"), f"release version duplicated in {path}"
        else:
            for file in path.rglob("*"):
                if file.is_file():
                    assert release not in file.read_text(encoding="utf-8"), f"release version duplicated in {file}"
