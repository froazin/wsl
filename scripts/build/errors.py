"""The error scripts.build raises for a failure the user can fix."""


class BuildError(Exception):
    """A failure the user can fix, such as a parts folder with no parts in it.

    Its message is ready to show as it is. tasks.py turns it into an Exit with status 1. Any other exception is a bug,
    so it keeps its traceback.
    """
