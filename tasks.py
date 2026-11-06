"""
Task definitions for the WSL config.

Each task is a thin wrapper around a package in pkg, which does the work. See docs/build.md.
"""

from pathlib import Path

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.tasks import task

from pkg.errors import BuildError
from pkg.manifest import Manifest

ROOT = Path(__file__).parent
MANIFESTS_SCHEMA = ROOT / "schemas" / "manifest.schema.json"
MANIFESTS_SRC = ROOT / "src" / "manifests"
FRAGMENTS_SRC = ROOT / "src" / "fragments"
DIST_DIR = ROOT / "dist"


@task(
    help={
        "filter": "Filters to only the manifests whose name matches this string. Case doesn't matter.",
    }
)
def build(_: Context, filter: str | None = None):
    if not MANIFESTS_SCHEMA.is_file():
        raise Exit(f"{MANIFESTS_SCHEMA} not found.", code=1)

    if not MANIFESTS_SRC.is_dir():
        raise Exit(f"{MANIFESTS_SRC} not found.", code=1)

    try:
        paths = sorted(p for p in MANIFESTS_SRC.glob("*.y*ml") if not filter or filter.lower() in p.stem.lower())

        if len({p.stem.lower() for p in paths}) != len(paths):
            raise BuildError("Duplicate manifest files found.")

        if not paths:
            raise BuildError(
                f"No manifests in {MANIFESTS_SRC} match {filter}." if filter else f"No manifests in {MANIFESTS_SRC}."
            )

        manifests = [Manifest.from_file(p, FRAGMENTS_SRC, schema=MANIFESTS_SCHEMA) for p in paths]

        if len({m.name.lower() for m in manifests}) != len(manifests):
            raise BuildError("Duplicate manifest names found.")

        for m in manifests:
            m.build(DIST_DIR)
    except BuildError as error:
        raise Exit(str(error), code=1) from error
