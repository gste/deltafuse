"""Schema registry and validation utilities for DeltaFuse Draft 2020-12 schemas."""

from __future__ import annotations
import datetime
import re
from pathlib import Path
from typing import Any
import yaml
import jsonschema
from jsonschema.validators import validator_for

from deltafuse.core.assets import AssetError, resolve_assets

_UNEXP_PROPS = re.compile(
    r"Additional properties are not allowed \((.+) (?:was|were) unexpected\)"
)
_SHORT_CR = re.compile(r"^CR-[0-9]{1,2}$")
_TASK_WITH_SLUG = re.compile(r"^TASK-[0-9]{3,}-")


_REQUIRED_PROP = re.compile(r"'([^']+)' is a required property")


def _unexpected_keys(error: jsonschema.ValidationError) -> list[str]:
    params = getattr(error, "params", None)
    raw = params.get("unexpected") if isinstance(params, dict) else None
    if isinstance(raw, (list, tuple, set)):
        return [str(k) for k in raw]
    if isinstance(raw, str):
        return [k.strip(" '\"") for k in raw.split(",") if k.strip(" '\"")]
    match = _UNEXP_PROPS.search(error.message or "")
    if not match:
        return []
    return [k.strip(" '\"") for k in match.group(1).split(",") if k.strip(" '\"")]


def _hint_for_schema_error(schema_name: str, error: jsonschema.ValidationError) -> str | None:
    """Name the expected key or pattern when the Worker wrote a close synonym."""
    path = tuple(error.path)
    instance = error.instance
    validator = error.validator

    if validator == "additionalProperties":
        keys = _unexpected_keys(error)
        hints: list[str] = []
        for key in keys:
            if schema_name == "change" and not path and key == "provenance":
                hints.append(
                    "do not add provenance: to change.yaml; write a Provenance section in "
                    "request.md and set source.request / source.intake_refs"
                )
            elif schema_name == "change" and path == ("framework",) and key == "source":
                hints.append(
                    "source is a top-level sibling of framework; copy framework.content_hash "
                    "from .deltafuse/lock.yaml"
                )
            elif schema_name == "change" and path == ("source",) and key in {
                "path",
                "type",
                "hash",
                "provenance",
            }:
                hints.append(
                    "source only allows request and intake_refs; put intake file paths in "
                    "intake_refs"
                )
            elif schema_name in {"routing", "slice"} and key in {"capability", "primary"}:
                hints.append("use primary_capability")
            elif schema_name == "slice" and key in {
                "intent",
                "delta_kind",
                "design_impact",
                "requirement_delta",
                "risk",
                "size",
            }:
                hints.append(
                    "put classification in the markdown body, not slice frontmatter"
                )
            elif schema_name == "task" and key == "title":
                hints.append("task frontmatter has no title; use the markdown heading")
            elif schema_name == "task" and key == "claims":
                hints.append(
                    "task frontmatter has no claims; claims live in request.md and slice frontmatter"
                )
            elif schema_name == "task" and key == "dependencies":
                hints.append("use depends_on")
        if hints:
            return "; ".join(dict.fromkeys(hints))

    if validator == "required":
        missing = None
        params = getattr(error, "params", None)
        if isinstance(params, dict):
            missing = params.get("property")
        if not missing:
            req = _REQUIRED_PROP.search(error.message or "")
            missing = req.group(1) if req else None
        if schema_name == "change" and not path and missing == "source":
            return "required key is source (not provenance)"
        if schema_name == "routing" and missing == "primary_capability":
            return "required key is primary_capability (not capability or primary)"
        if schema_name == "change" and path[:1] == ("slices",) and missing in {
            "id",
            "status",
            "file",
        }:
            return "each slices[] item is an object {id, status, file}, not a bare id"
        if schema_name == "task" and missing == "depends_on":
            return "required key is depends_on (not dependencies)"

    if validator == "type":
        if schema_name == "routing" and path == ("claims",):
            return "claims is a map keyed by CR-001, not a list"
        if schema_name == "change" and path[:1] == ("slices",) and isinstance(instance, str):
            return "each slices[] item is an object {id, status, file}, not a string"
        if schema_name == "change" and path[:1] == ("tasks",) and isinstance(instance, dict):
            return "change.yaml tasks[] is a list of TASK-001 strings, not objects"

    if validator == "pattern" and isinstance(instance, str):
        if _SHORT_CR.match(instance) or (
            schema_name in {"routing", "coverage"} and _SHORT_CR.match(str(path[-1]) if path else "")
        ):
            return "use CR-001 (three digits), not CR-01"
        if schema_name == "task" and path[-1:] == ("id",) and _TASK_WITH_SLUG.match(instance):
            return "id is TASK-001 (digits only); a slug belongs in the filename, not in id"
        if schema_name == "slice" and isinstance(instance, str) and instance.startswith("CR-"):
            return "use CR-001 (three digits), not CR-01"

    if validator == "enum" and isinstance(instance, str):
        allowed = error.validator_value if isinstance(error.validator_value, list) else []
        if instance == "add" and "added" in allowed:
            return "use added, not add"
        if instance == "proposed" and "draft" in allowed:
            return "new slice status is draft, not proposed"
        if instance == "proposed" and "pending" in allowed:
            return "new task status is pending, not proposed"

    if validator == "propertyNames" and isinstance(instance, str) and _SHORT_CR.match(instance):
        return "use CR-001 (three digits), not CR-01"

    return None


def format_schema_error(schema_name: str, error: jsonschema.ValidationError) -> str:
    path_str = " -> ".join(str(p) for p in error.path) if error.path else "root"
    message = f"[{path_str}] {error.message}"
    hint = _hint_for_schema_error(schema_name, error)
    if hint:
        return f"{message}; {hint}"
    return message


class SchemaValidationError(Exception):
    """Raised when validation against a schema fails."""

    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


def _normalize_data_for_json(data: Any) -> Any:
    """Recursively convert Python datetime/date to ISO strings for JSON schema validation."""
    if isinstance(data, (datetime.datetime, datetime.date)):
        if isinstance(data, datetime.datetime) and data.tzinfo is not None:
            return data.isoformat().replace("+00:00", "Z")
        return data.isoformat()
    if isinstance(data, dict):
        return {k: _normalize_data_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize_data_for_json(v) for v in data]
    return data


class SchemaRegistry:
    """Registry and validator for DeltaFuse JSON schemas."""

    def __init__(self, schemas_dir: Path | str | None = None):
        if schemas_dir is None:
            # DF3-005: packaged asset bundle first, source checkout fallback.
            try:
                self.schemas_dir = resolve_assets("schemas")
            except AssetError:
                self.schemas_dir = Path("process/schemas").resolve()
        else:
            self.schemas_dir = Path(schemas_dir).resolve()

        self._schemas: dict[str, dict[str, Any]] = {}
        self._validators: dict[str, Any] = {}
        self._load_all_schemas()

    def _load_all_schemas(self) -> None:
        if not self.schemas_dir.exists():
            return
        for file in self.schemas_dir.glob("*.schema.yaml"):
            schema_key = file.name.replace(".schema.yaml", "")
            with open(file, "r", encoding="utf-8") as f:
                schema_dict = yaml.safe_load(f)
                self._schemas[schema_key] = schema_dict
                validator_cls = validator_for(schema_dict)
                validator_cls.check_schema(schema_dict)
                self._validators[schema_key] = validator_cls(schema_dict)

    def get_schema(self, name: str) -> dict[str, Any]:
        normalized = name.replace(".schema.yaml", "")
        if normalized not in self._schemas:
            raise KeyError(f"Schema '{name}' not found in registry. Available: {list(self._schemas.keys())}")
        return self._schemas[normalized]

    def validate(self, schema_name: str, data: Any) -> list[str]:
        """Validates data against a named schema. Returns a list of error messages (empty if valid)."""
        normalized = schema_name.replace(".schema.yaml", "")
        if normalized not in self._validators:
            raise KeyError(f"Validator for schema '{schema_name}' not found. Available: {list(self._validators.keys())}")
        validator = self._validators[normalized]
        normalized_data = _normalize_data_for_json(data)
        errors = []
        for error in validator.iter_errors(normalized_data):
            errors.append(format_schema_error(normalized, error))
        return errors

    def shape_hint(
        self, schema_name: str, path: tuple[str, ...] = (), *, noun: str = "frontmatter keys"
    ) -> str:
        """One line naming the frontmatter a schema expects, derived from it.

        Appended to schema errors for Worker-written frontmatter: in q0 runs
        the Worker repaired one missing key per retry because an error names
        only the first failing rule.
        """
        schema = self.get_schema(schema_name)
        for step in path:  # "*" steps into additionalProperties (a map's values)
            child = schema.get("additionalProperties") if step == "*" else (schema.get("properties") or {}).get(step)
            schema = child if isinstance(child, dict) else {}
        props = schema.get("properties") or {}
        required = list(schema.get("required") or [])

        def describe(key: str) -> str:
            spec = props.get(key) or {}
            if "enum" in spec:
                return f"{key} ({'|'.join(str(v) for v in spec['enum'])})"
            if spec.get("type") == "array":
                least = "at least one" if int(spec.get("minItems") or 0) > 0 else "may be empty"
                return f"{key} (list, {least})"
            return key

        optional = [key for key in props if key not in required]
        line = f"expected {noun}: " + ", ".join(describe(key) for key in required)
        if optional:
            line += "; optional: " + ", ".join(describe(key) for key in optional)
        if schema.get("additionalProperties") is False:
            line += "; no other keys"
        return line

    def validate_or_raise(self, schema_name: str, data: Any) -> None:
        """Validates data against a schema and raises SchemaValidationError if invalid."""
        errors = self.validate(schema_name, data)
        if errors:
            raise SchemaValidationError(
                f"Validation failed for schema '{schema_name}' with {len(errors)} error(s):\n" + "\n".join(f"  - {e}" for e in errors),
                errors=errors,
            )


# Global default registry instance
default_registry = SchemaRegistry()
