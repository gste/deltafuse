"""Authorized test runners (DF3-006 / B-04).

Evidence commands must come from a project-owned runner allowlist. Defaults
are per route; ``.deltafuse/config.yaml`` may override with explicit command
prefixes under ``workflow.test_commands``. A Worker-substituted command such
as ``python -c "print('green')"`` cannot stamp authentic evidence.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

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
    if _canonical_head(argv[0]) not in JVM_RUNNERS:
        return False
    return any(arg.split(":")[-1].lower() in JVM_TEST_GOALS for arg in argv[1:])


# docs/ops routes verify file-oracle style checks; plain interpreters are fine.
DEFAULT_ROUTE_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "code": CODE_RUNNER_PREFIXES,
    "docs": (("python",),),  # any spelling of the interpreter (`_canonical_head`)
    "ops": (("python",),),
}


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


def _canonical_head(program: object) -> str:
    """The program a command starts with, as one name however it is spelled: no directory, no
    `.exe`/`.cmd`/`.bat`, lower case, and any Python interpreter as `python`.

    Audit 2026-11-17: the allowlist compared the first word almost literally, so `python3 -m
    pytest` and `py -m pytest` were not `python -m pytest` (FE-12), and a declared `./gradlew
    test` - the form `fuseback runner` writes - matched nothing, because the command's first word
    lost its directory and the declared one did not (FP-6).
    """
    from deltafuse.core.test_reports import is_python, runner_head

    head = runner_head(program)
    return "python" if is_python(head) else head


def _canonical(argv: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return (_canonical_head(argv[0]), *[str(a) for a in argv[1:]]) if argv else ()


def _match(argv: list[str], prefixes: tuple[tuple[str, ...], ...]) -> bool:
    if not argv:
        return False
    from deltafuse.core.test_reports import _normalized, runner_family

    head = _canonical(argv)
    # pytest is pytest however it is started: a declared `python -m pytest` also authorizes
    # `python -X utf8 -m pytest` and the virtualenv's `pytest`, compared from `pytest` on.
    as_pytest = tuple(_normalized(list(argv))) if runner_family(list(argv)) == "pytest" else None
    for prefix in prefixes:
        want = _canonical(prefix)
        if len(head) >= len(want) and head[: len(want)] == want:
            return True
        if as_pytest is not None and runner_family(list(prefix)) == "pytest":
            want = tuple(_normalized(list(prefix)))
            if as_pytest[: len(want)] == want:
                return True
    return False


def _load_config_prefixes(product_root: Path | None) -> tuple[tuple[str, ...], ...]:
    if product_root is None:
        return ()
    # Through config_section, the one reader: inside `human_settings_as_committed` it is the
    # committed value, not the Worker's uncommitted edit (audit 3, B-6).
    from deltafuse.core.config import config_section

    raw = config_section(product_root, "workflow").get("test_commands")
    if not isinstance(raw, list):
        return ()
    out: list[tuple[str, ...]] = []
    for entry in raw:
        parts = split_command(str(entry))
        if parts:
            out.append(parts)
    return tuple(out)


def split_command(text: str) -> tuple[str, ...]:
    """A declared command as arguments, the way a shell would pass them.

    Audit 2026-11-17 (FE-13): the entry was split on spaces with its quotes kept, so
    `pytest -m "not slow"` became four words, one of them `"not`, and no command ever matched it.
    A backslash is a path separator here (`.venv\\Scripts\\pytest.exe`), not an escape.
    """
    text = text.replace("\\", "/")
    try:
        return tuple(shlex.split(text))
    except ValueError:  # an unbalanced quote: the words as written
        return tuple(p for p in text.split(" ") if p)


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
    from deltafuse.core.test_reports import names_a_readable_runner, runner_family

    if runner_family(argv):
        return None  # `python -m pytest`, `uv run pytest`, `mvn test`: the runner itself
    # Audit 2026-11-17 (FE-3): a command that runs pytest or Maven through something the
    # Core does not read through (`pipx run pytest`, `bash -c "pytest"`) was a runner without
    # a reader, accepted on its exit code alone - whatever tests it ran. An interpreter is no
    # exception (`python -c "...pytest.main..."`, `python run_pytest.py`): declared as the only
    # entry of workflow.test_commands it read as a product with no reporting runner.
    runner = names_a_readable_runner(argv[1:] if _canonical_head(argv[0]) == "python" else argv)
    if _canonical_head(argv[0]) != "python" or runner is not None:
        if runner is None:
            return None  # `npm test`, `cargo test`: no report the Core reads, judged as before
        return (
            f"`{' '.join(str(a) for a in argv[:4])}` runs {runner} through a command the Core cannot "
            f"read through, so it cannot ask for or find the report of the tests that ran. Run {runner} "
            "in a form it reads: `pytest ...`, `python -m pytest ...` (interpreter options allowed), "
            "`uv run pytest ...`, `poetry run pytest ...`, `mvn ...`, `./mvnw ...`, `gradle ...`, "
            "`./gradlew ...`; if the product's runner needs another form, the human declares it in "
            "workflow.test_commands (a human setting the Worker does not edit)"
        )
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
    from deltafuse.core.test_reports import runner_family

    python_like = _canonical_head(argv[0]) == "python"
    if route == "code":
        # pytest-family runners, or a real script file on disk — never a
        # ``python -c`` one-liner substituted for the project runner.
        if _match(argv, CODE_RUNNER_PREFIXES) or _is_jvm_test_command(argv) or runner_family(argv) == "pytest":
            return True
        return (
            python_like
            and "-c" not in argv
            and any(arg.endswith(".py") for arg in argv[1:])
        )
    return _match(argv, DEFAULT_ROUTE_PREFIXES.get(route, CODE_RUNNER_PREFIXES))

