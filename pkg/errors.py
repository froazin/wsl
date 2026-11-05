"""The error scripts.build raises for a failure the user can fix."""


class BuildError(Exception):
    """
    A failure the user can fix, such as a manifest that lists a fragment that doesn't exist.

    Its message is ready to show as it is. tasks.py turns it into an Exit with status 1. Any other exception is a bug,
    so it keeps its traceback.
    """
