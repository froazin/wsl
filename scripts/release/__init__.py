"""Works out whether the config in dist/ makes a new release, and its version."""

from scripts.release.errors import ReleaseError
from scripts.release.version import next_version

__all__ = ["ReleaseError", "next_version"]
