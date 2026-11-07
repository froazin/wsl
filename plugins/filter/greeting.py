"""The greeting filter plugin. Its docs are in greeting.yml."""

from __future__ import annotations

from ansible_collections.froazin.wsl.plugins.plugin_utils.greeting import greeting


class FilterModule:
    """The filters in this file."""

    def filters(self) -> dict[str, object]:
        """Map each filter's name to its function."""
        return {"greeting": greeting}
