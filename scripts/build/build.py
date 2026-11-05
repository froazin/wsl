"""Builds dist/ from src/: joins the fragments each distro's manifest lists into one MIME multipart user-data file."""

import os
import shlex
import shutil
from collections.abc import Callable
from tempfile import TemporaryDirectory

from scripts.build.config import (
    CLOUD_CONFIG_PART_TYPE,
    DIST_FOLDER,
    JINJA_HEADER,
    JINJA_PART_TYPE,
    MAKE_MIME_COMMAND,
    MANIFEST_SCHEMA,
    SRC_FOLDER,
    SRC_FOLDERS,
    USER_DATA_SUFFIX,
)
from scripts.build.errors import BuildError
from scripts.build.manifest import Distro, load_distros

type Runner = Callable[[str], object]
"""Runs a shell command, such as invoke's Context.run."""


def part_type(path: str) -> str:
    """Returns the MIME content type make-mime gives a part: jinja2 when its first line is the Jinja header."""

    with open(path) as f:
        first_line = f.readline().rstrip("\n")
    return JINJA_PART_TYPE if first_line == JINJA_HEADER else CLOUD_CONFIG_PART_TYPE


def make_mime_command(paths: list[str], stage: str, output: str) -> str:
    """Returns the shell command that joins the fragments at paths into one MIME multipart file at output.

    make-mime names each part by the path it's given, and cloud-init lists those names in the cloud-config it merges at
    boot. So the command runs make-mime from stage, which must hold a copy of each fragment under its file name.
    """

    attach = [arg for path in paths for arg in ("--attach", f"{os.path.basename(path)}:{part_type(path)}")]
    command = shlex.join([*MAKE_MIME_COMMAND, *attach])
    return f"cd {shlex.quote(stage)} && {command} > {shlex.quote(os.path.abspath(output))}"


def build_distro(run: Runner, distro: Distro, dist: str) -> str:
    """Builds one distro's user-data into dist/<distro>.user-data, and returns its path."""

    output = os.path.join(dist, distro.name + USER_DATA_SUFFIX)
    with TemporaryDirectory() as stage:
        for path in distro.fragments:
            shutil.copyfile(path, os.path.join(stage, os.path.basename(path)))
        run(make_mime_command(list(distro.fragments), stage, output))
    return output


def build(run: Runner, src: str = SRC_FOLDER, dist: str = DIST_FOLDER, schema: str = MANIFEST_SCHEMA) -> list[str]:
    """Empties dist, then builds each distro in src/distros/ into it, and returns the paths it wrote.

    Every manifest is read before dist is emptied, so a broken one leaves the last build in place. Raises a BuildError
    for a manifest or fragment that's wrong, or an entry in src/ other than the fragments and distros folders.
    """

    stray = sorted(set(os.listdir(src)) - set(SRC_FOLDERS))
    if stray:
        raise BuildError(f"{src}/ holds {', '.join(stray)}. It should hold only {' and '.join(SRC_FOLDERS)}.")
    distros = load_distros(src, schema)

    shutil.rmtree(dist, ignore_errors=True)
    os.makedirs(dist)
    outputs = []
    for distro in distros:
        output = build_distro(run, distro, dist)
        print(f"Built {output} from {len(distro.fragments)} fragments")
        outputs.append(output)
    return outputs
