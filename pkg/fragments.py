"""The cloud-config fragments in src/fragments/, which each manifest's user-data is built from."""

import io
from collections.abc import Iterable
from pathlib import Path

from cloudinit.cmd.devel.make_mime import create_mime_message

from .errors import BuildError

FRAGMENT_SUFFIX = ".user-data"
FRAGMENT_JINJA_HEADER = "## template: jinja\n"


def create_mime_message_from_paths(paths: Iterable[Path]) -> str:
    """Returns the fragments at paths, in order, as one MIME multipart user-data, as `cloud-init devel make-mime` would.

    Each part is named after its fragment's file, and is jinja2 when the fragment starts with the Jinja header.
    cloud-init merges the parts in the order they're attached. Raises a BuildError, before reading any, when a fragment
    doesn't exist.
    """

    paths = list(paths)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise BuildError(f"Fragments not found: {', '.join(missing)}.")

    parts = []
    for path in paths:
        text = path.read_text()
        part_type = "jinja2" if text.startswith(FRAGMENT_JINJA_HEADER) else "cloud-config"
        parts.append((io.StringIO(text), path.name, part_type))
    message, _ = create_mime_message(parts)
    return f"{message}\n"
