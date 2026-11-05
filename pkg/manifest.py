"""Each distro's manifest, src/manifests/<distro>.yml, which lists the fragments its user-data is built from."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import fragments
from .errors import BuildError
from .fragments import SUFFIX as FRAGMENT_SUFFIX
from .schema import check_schema

SCHEMA: Path | None = None
"""schemas/manifest.schema.json, which tasks.py finds and sets when a task runs."""


@dataclass(frozen=True, kw_only=True)
class Manifest:
    name: str
    version: str
    description: str
    fragments: dict[int, Path]

    @classmethod
    def from_file(cls, path: str | Path, fragments_dir: str | Path, schema: Path | None = None) -> Manifest:
        """
        Reads a manifest and checks it against the schema, with its fragments in the order cloud-init merges them in.

        Each fragment's name becomes its path in fragments_dir. Raises a BuildError when the file can't be read or
        isn't valid.
        """

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except OSError as error:
            raise BuildError(f"{path} can't be read: {error.strerror}.") from error
        except yaml.YAMLError as error:
            raise BuildError(f"{path} isn't valid YAML: {error}") from error

        if schema:
            check_schema(path, data, schema)

        fragments = sorted(
            (int(key), Path(fragments_dir) / f"{name}{FRAGMENT_SUFFIX}") for key, name in data["fragments"].items()
        )
        return Manifest(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            fragments=dict(fragments),
        )

    def build(self, out_dir: str | Path) -> Path:
        """Joins the fragments, in order, into one MIME multipart user-data file, out_dir/<name>.user-data."""

        out = Path(out_dir) / f"{self.name}.user-data"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(fragments.create_mime_message_from_paths(self.fragments.values()))
        return out
