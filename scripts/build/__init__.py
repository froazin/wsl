"""Builds the config in src/ into dist/, and checks the result."""

from scripts.build.build import build
from scripts.build.errors import BuildError
from scripts.build.validation import validate

__all__ = ["BuildError", "build", "validate"]
