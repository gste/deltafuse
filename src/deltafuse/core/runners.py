"""Authorized test runners (DF3-006 / B-04).

Evidence commands must come from a project-owned runner allowlist. Defaults
are per route; ``.deltafuse/config.yaml`` may override with explicit command
prefixes under ``workflow.test_commands``. A Worker-substituted command such
as ``python -c "print('green')"`` cannot stamp authentic evidence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

CODE_RUNNER_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python", "-m", "tox"),
    ("tox",),
    ("npm", "test"),
    ("cargo", "test"),
    ("go", "test"),
)
# Maven and Gradle take their flags before the goal (`mvn -B test`,
# `gradle --no-daemon test`), so a prefix never matches them. They are
# recognised by the name of the tool plus a goal that runs tests - the shape
# the allowlist actually cares about. Until 3.3.4 no JVM runner was listed at
# all and a Java product could stamp no evidence without configuring
# `workflow.test_commands` by hand.
JVM_RUNNERS = frozenset({"mvn", "mvnw", "gradle", "gradlew"})
JVM_TEST_GOALS = frozenset({"test", "verify", "check", "integration-test"})


def _is_jvm_test_command(argv: list[str]) -> bool:
    if _as_runner_name(argv[0]).lower() not in JVM_RUNNERS:
        return False
    return any(arg.split(":")[-1].lower() in JVM_TEST_GOALS for arg in argv[1:])


# docs/ops routes verify file-oracle style checks; plain interpreters are fine.
DEFAULT_ROUTE_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "code": CODE_RUNNER_PREFIXES,
    "docs": (("python",), ("python3",)),
    "ops": (("python",), ("python3",)),
}
CONFIG_PATH = Path(".deltafuse") / "config.yaml"


def _as_runner_name(argv0: str) -> str:
    """`D:/proj/.venv/Scripts/pytest.exe` -> `pytest`.

    The allowlist compared argv[0] literally, so the pytest of a virtualenv -
    the normal way to run tests where pytest is not on PATH - was refused as
    a substituted runner. In the isolated environment that took every
    evidence command a run made: 27 of 27 (M01 run 3, 2026-09-23). The name
    is what identifies the runner; the full argv stays in the evidence
    record, so a substitution is still visible to a reader.
    """
    name = Path(argv0.replace("\\", "/")).name
    for suffix in (".exe", ".cmd", ".bat"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def _match(argv: list[str], prefixes: tuple[tuple[str, ...], ...]) -> bool:
    if not argv:
        return False
    head = [_as_runner_name(argv[0]), *argv[1:]]
    return any(
        len(head) >= len(prefix) and tuple(head[: len(prefix)]) == prefix
        for prefix in prefixes
    )


def _load_config_prefixes(product_root: Path | None) -> tuple[tuple[str, ...], ...]:
    if product_root is None:
        return ()
    path = product_root / CONFIG_PATH
    if not path.is_file():
        return ()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return ()
    workflow: Any = data.get("workflow") if isinstance(data, dict) else None
    raw = workflow.get("test_commands") if isinstance(workflow, dict) else None
    if not isinstance(raw, list):
        return ()
    out: list[tuple[str, ...]] = []
    for entry in raw:
        parts = tuple(str(p) for p in str(entry).replace("\\", "/").split(" ") if p)
        if parts:
            out.append(parts)
    return tuple(out)


_JVM_BUILD_FILES = ("pom.xml", "mvnw", "build.gradle", "build.gradle.kts", "settings.gradle",
                    "settings.gradle.kts", "gradlew")
_PYTEST_CONFIG_FILES = ("pytest.ini", ".pytest.ini", "conftest.py", "tests/conftest.py", "test/conftest.py")
_PYTEST_SECTIONS = (("pyproject.toml", "[tool.pytest.ini_options]"), ("tox.ini", "[pytest]"),
                    ("setup.cfg", "[tool:pytest]"))
_PYTEST_TEST = re.compile(r"(?m)^\s*(?:async\s+)?def test|^class Test")


def product_test_runner(product_root: Path | None) -> str:
    """`pytest` or `jvm` when the product's tests run under a runner whose report the Core reads;
    `` when they do not, or it cannot tell.

    The product's own `workflow.test_commands` decides when it declares any. Otherwise its build
    says so: a Maven/Gradle build file, a pytest configuration, or pytest-style tests (`def test_`
    in `tests/**/test_*.py`).
    """
    from deltafuse.core.test_reports import runner_family

    if product_root is None:
        return ""
    root = Path(product_root)
    configured = _load_config_prefixes(root)
    if configured:
        families = {runner_family(list(entry)) for entry in configured} - {""}
        return sorted(families)[0] if families else ""
    if any((root / name).is_file() for name in _JVM_BUILD_FILES):
        return "jvm"
    if any((root / name).is_file() for name in _PYTEST_CONFIG_FILES):
        return "pytest"
    for name, section in _PYTEST_SECTIONS:
        try:
            if section in (root / name).read_text(encoding="utf-8", errors="replace"):
                return "pytest"
        except OSError:
            continue
    for folder in ("tests", "test"):
        for i, path in enumerate(sorted((root / folder).rglob("*.py")) if (root / folder).is_dir() else []):
            if i >= 500:
                break
            if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
                continue
            try:
                if _PYTEST_TEST.search(path.read_text(encoding="utf-8", errors="replace")):
                    return "pytest"
            except OSError:
                continue
    return ""


def report_less_runner_error(argv: list[str], *, route: str, product_root: Path | None) -> str | None:
    """Why *argv* is no evidence on this product: a bare interpreter (`python <file>.py`,
    `python -c ...`) where the product's tests run under a runner that reports them.

    Audit 2026-11-16 (df-evidence #6, df-gates #2): `python tests/red_check.py` for Red and
    `python tests/green_check.py` for Green and regression converged a Change with no product
    change. Such a run reports no test, so nothing links Green to the Red it answers.
    """
    if route != "code" or not argv:
        return None
    if _as_runner_name(str(argv[0])).lower() not in {"python", "python3"}:
        return None
    from deltafuse.core.test_reports import runner_family

    if runner_family(argv):
        return None  # `python -m pytest`: the runner itself
    family = product_test_runner(product_root)
    if not family:
        return None
    runner = "pytest" if family == "pytest" else "Maven/Gradle"
    return (
        f"`{' '.join(str(a) for a in argv[:3])}` runs a bare interpreter, which reports no test, on a "
        f"product whose tests run under {runner}, which does: record it with the product's test "
        "runner, naming the task's tests"
    )


def runner_is_authorized(
    argv: list[str],
    *,
    route: str,
    product_root: Path | None = None,
) -> bool:
    """True only when the command comes from an authorized runner profile."""
    if not argv:
        return False
    configured = _load_config_prefixes(product_root)
    if configured:
        return _match(argv, configured)
    python_like = _as_runner_name(argv[0]).lower() in {"python", "python3"}
    if route == "code":
        # pytest-family runners, or a real script file on disk — never a
        # ``python -c`` one-liner substituted for the project runner.
        if _match(argv, CODE_RUNNER_PREFIXES) or _is_jvm_test_command(argv):
            return True
        return (
            python_like
            and "-c" not in argv
            and any(arg.endswith(".py") for arg in argv[1:])
        )
    return _match(argv, DEFAULT_ROUTE_PREFIXES.get(route, CODE_RUNNER_PREFIXES))

