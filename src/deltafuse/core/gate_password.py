"""Optional Human Gate password.

A Worker that can run `deltafuse decide` could accept its own specification or
Decision, and the receipt would read as the human's. When the human sets a
password, `decide` asks for it before it writes anything; the Worker does not
know it and its shell is not interactive, so it cannot answer.

Only a salted PBKDF2-SHA256 hash is stored, in `.deltafuse/gate-password.yaml`,
a Core-owned file the leash refuses in a Worker diff. The password guards the
`decide` command, not the journal: a model set on forging a receipt line by
hand is stopped by host isolation, not by this file. Standard library only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any

import yaml

PASSWORD_REL = ".deltafuse/gate-password.yaml"
ALG = "pbkdf2-sha256"
ITERATIONS = 600_000
MIN_LENGTH = 8


class GatePasswordError(Exception):
    """The Human Gate password is missing, wrong or cannot be set."""


def password_path(product_root: Path | str) -> Path:
    return Path(product_root) / PASSWORD_REL


def is_enabled(product_root: Path | str) -> bool:
    return password_path(product_root).is_file()


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _load(product_root: Path | str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(password_path(product_root).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as ex:
        raise GatePasswordError(f"cannot read {PASSWORD_REL}: {ex}") from ex
    if not isinstance(data, dict):
        raise GatePasswordError(f"{PASSWORD_REL} is not a mapping")
    return data


def verify_password(product_root: Path | str, password: str | None) -> bool:
    """True only when the password matches the stored hash."""
    if not password or not is_enabled(product_root):
        return False
    data = _load(product_root)
    try:
        if data.get("alg") != ALG:
            return False
        salt = bytes.fromhex(str(data["salt"]))
        expected = bytes.fromhex(str(data["hash"]))
        iterations = int(data["iterations"])
    except (KeyError, ValueError, TypeError):
        return False
    return hmac.compare_digest(_derive(password, salt, iterations), expected)


def _write(product_root: Path | str, content: dict[str, Any]) -> None:
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace

    path = password_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(content, sort_keys=True).encode("utf-8")
    if path.is_file():
        atomic_replace(path, payload)
    else:
        atomic_create(path, payload)


def set_password(product_root: Path | str, password: str, *, current: str | None = None) -> None:
    """Set or change the password; changing it needs the current one."""
    if is_enabled(product_root) and not verify_password(product_root, current):
        raise GatePasswordError("the current Human Gate password is wrong")
    if len(password) < MIN_LENGTH:
        raise GatePasswordError(f"the password needs at least {MIN_LENGTH} characters")
    salt = secrets.token_bytes(16)
    _write(
        product_root,
        {
            "version": 1,
            "alg": ALG,
            "iterations": ITERATIONS,
            "salt": salt.hex(),
            "hash": _derive(password, salt, ITERATIONS).hex(),
        },
    )


def clear_password(product_root: Path | str, current: str | None) -> None:
    """Turn the password off; needs the current one."""
    if not is_enabled(product_root):
        return
    if not verify_password(product_root, current):
        raise GatePasswordError("the current Human Gate password is wrong")
    password_path(product_root).unlink()
