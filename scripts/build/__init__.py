"""Builds the config in src/ into dist/, and checks the result."""

from scripts.build.build import build
from scripts.build.errors import BuildError

__all__ = ["BuildError", "build"]
