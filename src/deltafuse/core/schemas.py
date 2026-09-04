"""Schema registry and validation utilities for DeltaFuse Draft 2020-12 schemas."""

from __future__ import annotations
import datetime
from pathlib import Path
from typing import Any
import yaml
import jsonschema
from jsonschema.validators import validator_for


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
            # Look relative to repository root or package
            base = Path(__file__).resolve().parent.parent.parent.parent
            candidate = base / "process" / "schemas"
            if candidate.is_dir():
                self.schemas_dir = candidate
            else:
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
            path_str = " -> ".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"[{path_str}] {error.message}")
        return errors

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
