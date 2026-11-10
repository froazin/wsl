"""Each distro's manifest, src/manifests/<distro>.yml, which lists the fragments its user-data is built from."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import BuildError
from .fragments import FRAGMENT_SUFFIX, create_mime_message_from_paths
from .schema import check_schema


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

        names = list(data["fragments"].values())
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise BuildError(f"{path} lists {', '.join(repeated)} more than once. List each fragment once.")

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
        out.write_text(create_mime_message_from_paths(self.fragments.values()))
        return out


def load_manifests(
    manifests_dir: str | Path, fragments_dir: str | Path, schema: Path, filter: str | None = None
) -> list[Manifest]:
    """
    Loads every manifest in manifests_dir whose file name contains filter, ignoring case, in name order.

    WSL finds a user-data by name without regard to case, so two files, or two names, that differ only in case are an
    error. Raises a BuildError when there's no manifest to load, or when one can't be loaded.
    """

    manifests_dir = Path(manifests_dir)
    paths = sorted(p for p in manifests_dir.glob("*.y*ml") if not filter or filter.lower() in p.stem.lower())

    if len({p.stem.lower() for p in paths}) != len(paths):
        raise BuildError("Duplicate manifest files found.")

    if not paths:
        raise BuildError(
            f"No manifests in {manifests_dir} match {filter}." if filter else f"No manifests in {manifests_dir}."
        )

    manifests = [Manifest.from_file(p, fragments_dir, schema=schema) for p in paths]

    if len({m.name.lower() for m in manifests}) != len(manifests):
        raise BuildError("Duplicate manifest names found.")

    return manifests


def release_version(manifests: list[Manifest]) -> str:
    """
    Returns the version every manifest gives, which is the version of the release they're published in.

    Every distro is released together, under one tag, so raises a BuildError when the manifests' versions differ.
    """

    versions = sorted({m.version for m in manifests})
    if len(versions) != 1:
        raise BuildError(f"Every manifest must have the same version, but they have {', '.join(versions)}.")
    return versions[0]
