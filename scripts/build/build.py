"""Builds dist/ from src/: joins each parts folder into one MIME multipart file, and copies every other file."""

import os
import shlex
import shutil
from collections.abc import Callable

from scripts.build.config import (
    CLOUD_CONFIG_PART_TYPE,
    DIST_FOLDER,
    JINJA_HEADER,
    JINJA_PART_TYPE,
    MAKE_MIME_COMMAND,
    PARTS_SUFFIX,
    SRC_FOLDER,
)
from scripts.build.errors import BuildError

type Runner = Callable[[str], object]
"""Runs a shell command, such as invoke's Context.run."""


def part_type(path: str) -> str:
    """Returns the MIME content type make-mime gives a part: jinja2 when its first line is the Jinja header."""

    with open(path) as f:
        first_line = f.readline().rstrip("\n")
    return JINJA_PART_TYPE if first_line == JINJA_HEADER else CLOUD_CONFIG_PART_TYPE


def part_names(parts_dir: str) -> list[str]:
    """Returns the names of the files in a parts folder in name order, which is the order cloud-init merges them in."""

    names = sorted(name for name in os.listdir(parts_dir) if os.path.isfile(os.path.join(parts_dir, name)))
    if not names:
        raise BuildError(f"{parts_dir} has no parts to build.")
    return names


def make_mime_command(parts_dir: str, output: str) -> str:
    """Returns the shell command that joins the parts in parts_dir into one MIME multipart file at output.

    It runs make-mime from parts_dir, so each part is named by its file name, which cloud-init lists in the
    cloud-config it merges at boot.
    """

    names = part_names(parts_dir)
    attach = [arg for name in names for arg in ("--attach", f"{name}:{part_type(os.path.join(parts_dir, name))}")]
    command = shlex.join([*MAKE_MIME_COMMAND, *attach])
    return f"cd {shlex.quote(parts_dir)} && {command} > {shlex.quote(os.path.abspath(output))}"


def build(run: Runner, src: str = SRC_FOLDER, dist: str = DIST_FOLDER) -> list[str]:
    """Empties dist, then builds every entry in src into it, and returns the paths it wrote.

    A folder named <name>.d becomes dist/<name>, a MIME multipart file of its parts. Any other file is copied as it is.
    """

    shutil.rmtree(dist, ignore_errors=True)
    os.makedirs(dist)

    outputs = []
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if os.path.isdir(path) and name.endswith(PARTS_SUFFIX):
            output = os.path.join(dist, name.removesuffix(PARTS_SUFFIX))
            run(make_mime_command(path, output))
        elif os.path.isfile(path):
            output = os.path.join(dist, name)
            shutil.copyfile(path, output)
        else:
            raise BuildError(f"{path} is neither a file nor a folder whose name ends in {PARTS_SUFFIX}.")
        print(f"Built {output}")
        outputs.append(output)
    return outputs
