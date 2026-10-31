"""Task definitions for the WSL config.

Each task is a thin wrapper around a package in scripts, which does the work. See docs/build.md.
"""

from collections.abc import Generator
from contextlib import contextmanager

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.tasks import task

from scripts import build as builder


@contextmanager
def _exit_on_build_error() -> Generator[None]:
    """Turns a BuildError into an Exit with status 1, so Invoke prints its message without a traceback."""

    try:
        yield
    except builder.BuildError as error:
        raise Exit(str(error), code=1) from error


@task
def build(c: Context) -> None:
    """Builds the config in src/ into dist/, after emptying dist/.

    Each folder named <name>.d in src/ becomes dist/<name>, a MIME multipart file of its parts made with
    `cloud-init devel make-mime`. Every other file in src/ is copied. See docs/build.md.

    Examples:
      invoke build
    """

    with _exit_on_build_error():
        builder.build(c.run)
