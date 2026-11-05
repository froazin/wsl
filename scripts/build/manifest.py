"""Each distro's manifest.json, which lists the fragments its user-data is built from."""

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from scripts.build.config import (
    DISTROS_FOLDER,
    FRAGMENT_SUFFIX,
    FRAGMENTS_FOLDER,
    MANIFEST_FILE,
    MANIFEST_SCHEMA,
    SRC_FOLDER,
)
from scripts.build.errors import BuildError

DISTRO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
"""A WSL distribution's name, such as Ubuntu-26.04. It names files, matrix jobs and wsl.exe arguments."""


@dataclass(frozen=True, kw_only=True)
class Distro:
    """A distro in src/distros/<name>/, and the paths of the fragments its manifest.json lists, in name order.

    schemas/distro-manifest.schema.json describes manifest.json.
    """

    name: str
    fragments: tuple[str, ...]

    def fragment_names(self) -> list[str]:
        """Returns the file name of each fragment, which names its part in the MIME user-data."""

        return [os.path.basename(path) for path in self.fragments]


def distro_names(src: str = SRC_FOLDER) -> list[str]:
    """Returns the name of every folder in src/distros/, in name order."""

    folder = os.path.join(src, DISTROS_FOLDER)
    if not os.path.isdir(folder):
        raise BuildError(f"{folder} not found.")
    entries = sorted(os.listdir(folder))
    files = [name for name in entries if not os.path.isdir(os.path.join(folder, name))]
    if files:
        raise BuildError(f"{folder} holds {', '.join(files)}. Each distro is a folder with a {MANIFEST_FILE}.")
    names = entries
    if not names:
        raise BuildError(f"{folder} has no distros to build.")
    return names


def load_distros(src: str = SRC_FOLDER, schema_path: str = MANIFEST_SCHEMA) -> list[Distro]:
    """Returns every distro in src/distros/, in name order, with its fragments found.

    Raises a BuildError for the first distro whose manifest.json or fragments are wrong.
    """

    with open(schema_path) as f:
        validator = Draft202012Validator(json.load(f))
    return [load_distro(name, src, validator) for name in distro_names(src)]


def load_distro(name: str, src: str, validator: Draft202012Validator) -> Distro:
    """Reads one distro's manifest.json, checks it against the schema and finds each fragment it lists.

    A fragment is <name>.user-data in the distro's own folder or in src/fragments/. Raises a BuildError when a fragment
    is in both or neither, when the distro's folder holds a file its manifest doesn't list, or when the manifest isn't
    valid or doesn't list its fragments in name order.
    """

    folder = os.path.join(src, DISTROS_FOLDER, name)
    path = os.path.join(folder, MANIFEST_FILE)
    if not DISTRO_NAME.fullmatch(name):
        raise BuildError(f"{folder} isn't a WSL distribution name: use letters, digits, '.', '_' and '-'.")
    manifest = read_manifest(path, validator)
    listed: list[str] = manifest["fragments"]
    if listed != sorted(listed):
        raise BuildError(f"{path} must list its fragments in name order, the order cloud-init merges them in.")

    own = {entry for entry in os.listdir(folder) if entry != MANIFEST_FILE}
    unlisted = sorted(own - {fragment + FRAGMENT_SUFFIX for fragment in listed})
    if unlisted:
        raise BuildError(f"{folder} holds {', '.join(unlisted)}, which {MANIFEST_FILE} doesn't list.")

    paths = []
    for fragment in listed:
        candidates = [os.path.join(folder, fragment + FRAGMENT_SUFFIX), fragment_path(src, fragment)]
        found = [candidate for candidate in candidates if os.path.isfile(candidate)]
        if len(found) != 1:
            where = "both" if found else "neither"
            raise BuildError(f"{path} lists {fragment}, which is in {where} of {candidates[0]} and {candidates[1]}.")
        paths.append(found[0])
    return Distro(name=name, fragments=tuple(paths))


def read_manifest(path: str, validator: Draft202012Validator) -> dict[str, Any]:
    """Returns a manifest.json's content, raising a BuildError with every schema error when it isn't valid."""

    try:
        with open(path) as f:
            manifest = json.load(f)
    except FileNotFoundError as error:
        raise BuildError(f"{path} not found. Every folder in {DISTROS_FOLDER}/ needs one.") from error
    except json.JSONDecodeError as error:
        raise BuildError(f"{path} isn't valid JSON: {error}") from error
    errors = sorted(f"- {error.json_path}: {error.message}" for error in validator.iter_errors(manifest))
    if errors:
        raise BuildError(f"{path} doesn't match the distro manifest schema:\n" + "\n".join(errors))
    return manifest


def fragment_path(src: str, fragment: str) -> str:
    """Returns the path of a shared fragment, by its name without .user-data."""

    return os.path.join(src, FRAGMENTS_FOLDER, fragment + FRAGMENT_SUFFIX)


def shared_fragments(src: str = SRC_FOLDER) -> list[str]:
    """Returns the path of every file in src/fragments/, in name order."""

    folder = os.path.join(src, FRAGMENTS_FOLDER)
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, name) for name in sorted(os.listdir(folder))]
