"""
Task definitions for the WSL config.

Each task is a thin wrapper around a package in pkg, which does the work. See docs/build.md.
"""

from pathlib import Path

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.tasks import task

from pkg.errors import BuildError
from pkg.manifest import load_manifests, release_version

ROOT = Path(__file__).parent
MANIFESTS_SCHEMA = ROOT / "schemas" / "manifest.schema.json"
MANIFESTS_SRC = ROOT / "src" / "manifests"
FRAGMENTS_SRC = ROOT / "src" / "fragments"
DIST_DIR = ROOT / "dist"


def _check_sources() -> None:
    if not MANIFESTS_SCHEMA.is_file():
        raise Exit(f"{MANIFESTS_SCHEMA} not found.", code=1)

    if not MANIFESTS_SRC.is_dir():
        raise Exit(f"{MANIFESTS_SRC} not found.", code=1)


@task(
    help={
        "filter": "Filters to only the manifests whose name matches this string. Case doesn't matter.",
    }
)
def build(_: Context, filter: str | None = None):
    _check_sources()
    try:
        for m in load_manifests(MANIFESTS_SRC, FRAGMENTS_SRC, MANIFESTS_SCHEMA, filter):
            m.build(DIST_DIR)
    except BuildError as error:
        raise Exit(str(error), code=1) from error


@task
def version(_: Context):
    """Prints the manifests' version, which a release is tagged with, without a v."""

    _check_sources()
    try:
        print(release_version(load_manifests(MANIFESTS_SRC, FRAGMENTS_SRC, MANIFESTS_SCHEMA)))
    except BuildError as error:
        raise Exit(str(error), code=1) from error
