"""Closed local schemas. No remote reference resolution or implicit defaults."""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from importlib.resources import files

from .model import Record


@lru_cache(maxsize=1)
def validators() -> dict:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from referencing import Registry, Resource
    except ImportError as exc:
        raise RuntimeError("Install the project observation extra: pip install -e '.[observation]'") from exc
    schemas = {}
    registry = Registry()
    for name in ("common", "tag", "event", "state", "relation", "projection", "config"):
        schema = json.loads(files(__package__).joinpath("contracts", name + ".schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    checker = FormatChecker()
    @checker.checks("date-time")
    def valid_utc(value: object) -> bool:
        if not isinstance(value, str):
            return True
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            return False
        return True
    return {name: Draft202012Validator(schema, registry=registry, format_checker=checker)
            for name, schema in schemas.items()}


def resolve_config(overrides: Record | None = None) -> Record:
    config = json.loads(files(__package__).joinpath("contracts", "defaults.json").read_text(encoding="utf-8"))
    config.update(overrides or {})
    if not validators()["config"].is_valid(config):
        raise ValueError("INVALID_CONFIG")
    return config
