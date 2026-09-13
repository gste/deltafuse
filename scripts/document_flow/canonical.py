"""Canonical JSON helpers for sealed document-flow evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


class CanonicalError(ValueError):
    """Raised when a value cannot be represented by the benchmark profile."""


def _validate(value: Any) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        raise CanonicalError("floating-point values are not canonical")
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate(item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError("canonical object keys must be strings")
            _validate(item)
        return
    raise CanonicalError(f"unsupported canonical value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return the single UTF-8 JSON representation accepted by the store."""

    _validate(value)
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise CanonicalError(str(exc)) from exc
    return text.encode("utf-8")


def content_hash(value: Any, *, exclude: Iterable[str] = ()) -> str:
    """Hash a value, optionally omitting named top-level mapping fields."""

    excluded = frozenset(exclude)
    if excluded:
        if not isinstance(value, Mapping):
            raise CanonicalError("excluded fields require an object")
        value = {key: item for key, item in value.items() if key not in excluded}
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    """Copy an object and bind its canonical content to ``field``."""

    if not isinstance(field, str) or not field:
        raise CanonicalError("self-hash field must be a non-empty string")
    result = dict(value)
    result.pop(field, None)
    result[field] = content_hash(result)
    return result
