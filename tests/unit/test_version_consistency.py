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
    assert (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip() == "3.0.0"


def test_pyproject_and_dunder_version_match() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is not None:
        pyproject = tomllib.loads(pyproject_text)
        assert pyproject["project"]["version"] == "3.0.0"
    else:
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject_text)
        assert match and match.group(1) == "3.0.0"
    init = (REPO_ROOT / "src" / "deltafuse" / "__init__.py").read_text(encoding="utf-8")
    assert '__version__ = "3.0.0"' in init


def test_template_config_and_change_declare_release_version() -> None:
    for base in (REPO_ROOT / "process" / "templates", REPO_ROOT / "src" / "deltafuse" / "assets" / "templates"):
        config = yaml.safe_load((base / ".deltafuse" / "config.yaml").read_text(encoding="utf-8"))
        assert config["framework"]["version"] == "3.0.0"
        assert config["framework"]["source"] == "deltafuse://v3.0.0"
        change = yaml.safe_load((base / "change" / "change.yaml").read_text(encoding="utf-8"))
        assert change["framework"]["version"] == "3.0.0"


def test_no_stale_release_versions_in_canonical_sources() -> None:
    stale = re.compile(r"(?<![\d.])2\.5\.0(?![\d.])|(?<![\d.])3\.5\.0(?![\d.])")
    scanned = [
        REPO_ROOT / "VERSION",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "src" / "deltafuse" / "__init__.py",
        REPO_ROOT / "process" / "templates",
        REPO_ROOT / "src" / "deltafuse" / "assets" / "templates",
    ]
    for path in scanned:
        if path.is_file():
            assert not stale.search(path.read_text(encoding="utf-8")), f"stale version in {path}"
        else:
            for file in path.rglob("*"):
                if file.is_file():
                    assert not stale.search(file.read_text(encoding="utf-8")), f"stale version in {file}"
