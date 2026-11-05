"""The error scripts.release raises for a failure the user can fix."""


class ReleaseError(Exception):
    """A failure the user can fix, such as an empty dist/ or semantic-release failing.

    Its message is ready to show as it is. tasks.py turns it into an Exit with status 1. Any other exception is a bug,
    so it keeps its traceback.
    """
