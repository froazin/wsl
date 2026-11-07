"""The greeting filter plugin. Its docs are in greeting.yml."""

from __future__ import annotations

from ansible.errors import AnsibleFilterError
from ansible.module_utils.datatag import native_type_name


def greeting(name: object) -> str:
    """Return a greeting for ``name``.

    Raises:
        AnsibleFilterError: ``name`` isn't a string, or is blank.
    """
    if not isinstance(name, str):
        # Templated values are tagged subclasses, such as _AnsibleTaggedInt.
        raise AnsibleFilterError(f"greeting expects a string, got {native_type_name(name)}")

    name = name.strip()
    if not name:
        raise AnsibleFilterError("greeting expects a name, got a blank string")

    return f"Hello, {name}!"


class FilterModule:
    """The filters in this file."""

    def filters(self) -> dict[str, object]:
        """Map each filter's name to its function."""
        return {"greeting": greeting}
