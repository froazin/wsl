"""Task definitions for the WSL config.

Each task is a thin wrapper around a package in scripts, which does the work. See docs/build.md.
"""

from collections.abc import Generator
from contextlib import contextmanager

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.tasks import task

from scripts import build as builder
from scripts import release

SKIP_BUILD_HELP = "Check the files already in dist/ instead of building them first."
PREVIOUS_HELP = "The folder holding the latest release's files. Missing or empty before the first release."


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

    Each distro in src/distros/ becomes dist/<distro>.user-data, a MIME multipart file of the fragments its
    manifest.json lists, made with `cloud-init devel make-mime`. See docs/build.md and docs/distros.md.

    Examples:
      invoke build
    """

    with _exit_on_build_error():
        builder.build(c.run)


@task(help={"skip_build": SKIP_BUILD_HELP})
def validate(c: Context, skip_build: bool = False) -> None:
    """Builds the config, then checks each distro's user-data in dist/ against every meta-data case.

    For each distro and each case in scripts/build/cases.py, merges the user-data's parts with cloud-init's own part
    handlers, as an instance does at boot, then checks the result with `cloud-init schema`, git, ssh-keygen and
    ShellCheck. Also checks each fragment's lists are appended in name order, Jinja tags sit at column 0, every shared
    fragment is in a manifest and no Windows profile path names a user. See docs/build.md.

    Examples:
      invoke validate
      invoke validate --skip-build
    """

    with _exit_on_build_error():
        if not skip_build:
            builder.build(c.run)
        builder.validate()


@contextmanager
def _exit_on_release_error() -> Generator[None]:
    """Turns a ReleaseError into an Exit with status 1, so Invoke prints its message without a traceback."""

    try:
        yield
    except release.ReleaseError as error:
        raise Exit(str(error), code=1) from error


@task(help={"previous": PREVIOUS_HELP})
def version(_: Context, previous: str) -> None:
    """Prints the next release's version, or nothing when dist/ is the same as the latest release.

    Compares dist/ with the latest release's files, so run invoke build first. When they differ, semantic-release
    works out the version from the commits on main that changed src/, as a patch when none calls for a bump. Run it
    from the repository root, on main. See docs/releases.md.

    Examples:
      invoke version --previous /tmp/latest-release
    """

    with _exit_on_release_error():
        next_version = release.next_version(previous)
    if next_version:
        print(next_version)
