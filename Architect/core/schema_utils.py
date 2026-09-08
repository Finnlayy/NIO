"""Shared lightweight JSON-Schema validation helpers (Phase 4).

The blueprint kernel is stdlib-only; Jules's Architect preserves that
divergence philosophy for the learning engine, so instead of pulling in the
`jsonschema` package we keep a small, dependency-free validator that mirrors
the subset of JSON Schema used by `Architect/schemas/*.schema.json`
(`type`, `required`, `enum`, `minimum`, `maximum`, `properties`,
`additionalProperties`).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SchemaInvalid(ValueError):
    """Raised when a record fails validation against its JSON schema."""


def load_schema(schema_path) -> dict:
    """Load a JSON schema file from disk."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Schemas live in Architect/schemas/; resolve relative to this module so the
# defaults work from any working directory (repo root or Architect/).
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


def default_schema_path(filename: str) -> str:
    return str(SCHEMAS_DIR / filename)


def _check_type(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_value(value, schema: dict, path: str, errors: list):
    """Recursive mini-validator for the schema subset we support."""
    if schema is None:
        return
    if "oneOf" in schema:
        sub_errors = []
        matched = False
        for sub in schema["oneOf"]:
            sub_errs = []
            _validate_value(value, sub, path, sub_errs)
            if not sub_errs:
                matched = True
                break
            sub_errors.extend(sub_errs)
        if not matched:
            errors.append(f"{path}: does not match any allowed variant ({'; '.join(sub_errors)})")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']}")
        return
    expected = schema.get("type")
    if expected and not _check_type(value, expected):
        errors.append(f"{path}: expected type {expected}, got {type(value).__name__}")
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value {value} above maximum {schema['maximum']}")
    if expected == "object" or isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")
        props = schema.get("properties", {})
        if isinstance(value, dict):
            for key, val in value.items():
                if key in props:
                    _validate_value(val, props[key], f"{path}.{key}", errors)
    if expected == "array" or isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema and isinstance(value, list):
            for i, item in enumerate(value):
                _validate_value(item, item_schema, f"{path}[{i}]", errors)


def validate_against_schema(record: dict, schema: dict) -> list:
    """Validate `record` against `schema`; return list of error strings (empty = valid)."""
    errors: list = []
    _validate_value(record, schema, "$", errors)
    return errors
