"""Fail-closed, local-only JSON decoding and schema validation for J03."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError as JsonSchemaValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable


SCHEMA_ROOT = Path(__file__).with_name("schemas")
SCHEMA_FILES = {
    "event": "event.schema.json",
    "evidence-ref": "evidence-ref.schema.json",
}


class ValidationError(ValueError):
    """Input could not be safely decoded or did not satisfy a local schema."""


def _reject_constant(value: str) -> None:
    raise ValidationError(f"nonfinite JSON number: {value}")


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_ROOT / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_closed_object, parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load local schema {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"local schema {name} is not an object")
    return value


def _schema_registry(schemas: list[dict[str, Any]]) -> Registry:
    resources = []
    for schema in schemas:
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id.startswith("urn:deltafuse:j03:"):
            raise ValidationError("schema $id must be a local J03 URN")
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _assert_local_refs(value: Any, allowed_ids: frozenset[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#") and ref not in allowed_ids:
            raise ValidationError(f"nonlocal schema reference is forbidden: {ref}")
        for child in value.values():
            _assert_local_refs(child, allowed_ids)
    elif isinstance(value, list):
        for child in value:
            _assert_local_refs(child, allowed_ids)


def decode_validate(kind: str, raw: bytes) -> dict[str, Any]:
    """Decode *raw* and validate it against a fixed local schema kind."""
    if kind not in SCHEMA_FILES:
        raise ValidationError(f"unknown schema kind: {kind}")
    if not isinstance(raw, bytes):
        raise ValidationError("raw JSON must be bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_closed_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("decoded JSON root must be an object")
    evidence_schema = _load_schema(SCHEMA_FILES["evidence-ref"])
    target_schema = evidence_schema if kind == "evidence-ref" else _load_schema(SCHEMA_FILES[kind])
    schemas = [evidence_schema] if kind == "evidence-ref" else [evidence_schema, target_schema]
    allowed_ids = frozenset(schema["$id"] for schema in schemas)
    for schema in schemas:
        _assert_local_refs(schema, allowed_ids)
    try:
        Draft202012Validator.check_schema(target_schema)
        validator = Draft202012Validator(target_schema, registry=_schema_registry(schemas), format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(value), key=lambda error: tuple(str(part) for part in error.absolute_path))
    except (SchemaError, Unresolvable) as exc:
        raise ValidationError(f"local schema resolution failed: {exc}") from exc
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValidationError(f"schema validation failed at {location}: {error.message}")
    return value
