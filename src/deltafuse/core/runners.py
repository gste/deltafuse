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


def _match(argv: list[str], prefixes: tuple[tuple[str, ...], ...]) -> bool:
    return any(
        len(argv) >= len(prefix) and tuple(argv[: len(prefix)]) == prefix
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
    exe = Path(argv[0]).name.lower()
    python_like = exe in {"python", "python.exe", "python3", "python3.exe"}
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
        # pytest-family runners, or a real script file on disk — never a
        # ``python -c`` one-liner substituted for the project runner.
        if _match(argv, CODE_RUNNER_PREFIXES):
            return True
        return (
            argv[0] in {"python", "python3"}
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
