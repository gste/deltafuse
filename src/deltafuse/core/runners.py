"""Authorized test runners (DF3-006 / B-04).

Evidence commands must come from a project-owned runner allowlist. Defaults
are per route; ``.deltafuse/config.yaml`` may override with explicit command
prefixes under ``workflow.test_commands``. A Worker-substituted command such
as ``python -c "print('green')"`` cannot stamp authentic evidence.
"""

from __future__ import annotations

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
    return name[:-4] if name.lower().endswith(".exe") else name


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
        if _match(argv, CODE_RUNNER_PREFIXES):
            return True
        return (
            python_like
            and "-c" not in argv
            and any(arg.endswith(".py") for arg in argv[1:])
        )
    return _match(argv, DEFAULT_ROUTE_PREFIXES.get(route, CODE_RUNNER_PREFIXES))


def runner_profile(argv: list[str]) -> str:
    """Short structured runner identity for retry diagnostics (no full logs)."""
    if argv:
        head = " ".join(argv[:3])
    else:
        head = ""
    return head
