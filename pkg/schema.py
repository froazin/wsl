"""Schema validation for manifests."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .errors import BuildError


def check_schema(path: str | Path, data: Any, schema: Path) -> None:
    """Raises a BuildError with every schema error when a manifest's content doesn't match the schema."""

    # YAML reads the fragments' keys as integers, and JSON Schema only checks the pattern of a string key.
    if isinstance(data, dict) and isinstance(data.get("fragments"), dict):
        data = {**data, "fragments": {str(key): fragment for key, fragment in data["fragments"].items()}}

    validator = Draft202012Validator(json.loads(schema.read_text()))
    errors = sorted(f"- {error.json_path}: {error.message}" for error in validator.iter_errors(data))
    if errors:
        raise BuildError(f"{path} doesn't match the manifest schema:\n" + "\n".join(errors))
