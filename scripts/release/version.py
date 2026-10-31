"""Works out whether dist/ makes a new release, by comparing it with the latest release's files, and its version."""

import email
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from scripts.build.config import DIST_FOLDER
from scripts.release.errors import ReleaseError

PRINT_LAST_RELEASED = ("version", "--print-last-released")
PRINT_NEXT = ("version", "--print")
PRINT_NEXT_PATCH = ("version", "--print", "--patch")
NO_RELEASE_VERSION = "0.0.0"
"""What semantic-release counts from before the first release, as pyproject.toml allows zero versions."""

type Runner = Callable[[Sequence[str]], str]
"""Runs semantic-release with these arguments and returns its standard output, raising ReleaseError if it fails."""


def run_semantic_release(args: Sequence[str]) -> str:
    """Runs semantic-release with args and returns its standard output, raising ReleaseError if it fails.

    It runs in the working directory, which must be the repository root, where it reads pyproject.toml and resolves the
    path filters. Its log, such as "Token value is missing", goes to standard error, so it never mixes with the
    version. GITHUB_OUTPUT is emptied, because in GitHub Actions it would otherwise add its own outputs to the step.
    """

    result = subprocess.run(
        [sys.executable, "-m", "semantic_release", *args],
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "GITHUB_OUTPUT": ""},
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError(f"semantic-release {' '.join(args)} exited with status {result.returncode}.")
    return result.stdout


def contents(path: Path) -> object:
    """Returns what a release file holds, to compare with another build's.

    For a MIME multipart file, that's each part's file name, content type and decoded payload, because make-mime picks
    a random boundary, so two builds of the same parts differ byte for byte. For any other file, it's the bytes.
    """

    data = path.read_bytes()
    message = email.message_from_bytes(data)
    if not message.is_multipart():
        return data
    return [(part.get_filename(), part.get_content_type(), part.get_payload(decode=True)) for part in message.walk()]


def release_files(folder: str) -> dict[str, object]:
    """Returns the contents of each file directly in folder, by name. A missing folder has none."""

    return {path.name: contents(path) for path in Path(folder).glob("*") if path.is_file()}


def _version(run: Runner, args: Sequence[str]) -> str:
    """Runs semantic-release with args, and returns the version it prints, raising ReleaseError if it prints none."""

    version = run(args).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ReleaseError(
            f"semantic-release {' '.join(args)} printed {version!r}, not a version. It only prints one on main."
        )
    return version


def next_version(previous: str, dist: str = DIST_FOLDER, run: Runner = run_semantic_release) -> str | None:
    """Returns the next release's version, or None when dist is the same as the latest release.

    previous holds the latest release's files, and is missing or empty before the first release. semantic-release works
    out the version from the commits that changed src/. When none of them calls for a bump, such as a refactor, the
    release is a patch, because what users download still changed. Raises ReleaseError if dist has no files.
    """

    built = release_files(dist)
    if not built:
        raise ReleaseError(f"{dist}/ has no files to release. Run invoke build first.")
    if built == release_files(previous):
        return None

    last = run(PRINT_LAST_RELEASED).strip() or NO_RELEASE_VERSION
    version = _version(run, PRINT_NEXT)
    return _version(run, PRINT_NEXT_PATCH) if version == last else version
