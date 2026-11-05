import os
import subprocess
from collections.abc import Sequence

import pytest

from scripts.build import build
from scripts.release import ReleaseError, next_version
from scripts.release.version import PRINT_LAST_RELEASED, PRINT_NEXT, PRINT_NEXT_PATCH, run_semantic_release


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def shell(command: str) -> None:
    subprocess.run(command, shell=True, check=True)


def make_src(src: str, part: str = "#cloud-config\npackages: [git]\n") -> None:
    write(f"{src}/fragments/10-a.user-data", part)
    write(f"{src}/distros/Instance/20-b.user-data", "## template: jinja\n#cloud-config\nhostname: {{ x }}\n")
    write(f"{src}/distros/Instance/manifest.json", '{"fragments": ["10-a", "20-b"]}')
    write(f"{src}/distros/Other/manifest.json", '{"fragments": ["10-a"]}')


class FakeSemanticRelease:
    """Answers each semantic-release command with the output given for it, and records the commands it ran."""

    def __init__(self, last: str, next_: str, patch: str = "") -> None:
        self.outputs = {PRINT_LAST_RELEASED: last, PRINT_NEXT: next_, PRINT_NEXT_PATCH: patch}
        self.ran: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.ran.append(tuple(args))
        return self.outputs[tuple(args)] + "\n"


def no_semantic_release(args: Sequence[str]) -> str:
    raise AssertionError(f"semantic-release {args} ran, but no release is due.")


@pytest.fixture
def dist(tmp_path) -> str:
    """A dist/ built from a test src/ with the real make-mime."""

    make_src(f"{tmp_path}/src")
    build(shell, f"{tmp_path}/src", f"{tmp_path}/dist")
    return f"{tmp_path}/dist"


def test_two_builds_of_the_same_parts_make_no_release(tmp_path, dist):
    build(shell, f"{tmp_path}/src", f"{tmp_path}/previous")

    with open(f"{dist}/Instance.user-data", "rb") as a, open(f"{tmp_path}/previous/Instance.user-data", "rb") as b:
        assert a.read() != b.read(), "make-mime should pick a new boundary each time"
    assert next_version(f"{tmp_path}/previous", dist, no_semantic_release) is None


def test_identical_files_make_no_release(tmp_path):
    write(f"{tmp_path}/dist/a", "same\n")
    write(f"{tmp_path}/previous/a", "same\n")

    assert next_version(f"{tmp_path}/previous", f"{tmp_path}/dist", no_semantic_release) is None


@pytest.mark.parametrize("make_previous", [False, True], ids=["missing", "empty"])
def test_no_previous_release_releases(tmp_path, dist, make_previous):
    if make_previous:
        os.makedirs(f"{tmp_path}/previous")

    assert next_version(f"{tmp_path}/previous", dist, FakeSemanticRelease("", "0.1.0")) == "0.1.0"


def test_a_changed_part_releases(tmp_path, dist):
    make_src(f"{tmp_path}/old", part="#cloud-config\npackages: [curl]\n")
    build(shell, f"{tmp_path}/old", f"{tmp_path}/previous")

    assert next_version(f"{tmp_path}/previous", dist, FakeSemanticRelease("0.1.0", "0.2.0")) == "0.2.0"


@pytest.mark.parametrize("change", ["add", "remove"])
def test_an_added_or_removed_file_releases(tmp_path, dist, change):
    build(shell, f"{tmp_path}/src", f"{tmp_path}/previous")
    if change == "add":
        os.remove(f"{tmp_path}/previous/Other.user-data")
    else:
        write(f"{tmp_path}/previous/Instance.extra", "\n")

    assert next_version(f"{tmp_path}/previous", dist, FakeSemanticRelease("0.1.0", "0.1.1")) == "0.1.1"


@pytest.mark.parametrize(("last", "next_", "patch"), [("0.1.0", "0.1.0", "0.1.1"), ("", "0.0.0", "0.0.1")])
def test_changes_without_a_bump_force_a_patch(tmp_path, dist, last, next_, patch):
    semantic_release = FakeSemanticRelease(last, next_, patch)

    assert next_version(f"{tmp_path}/previous", dist, semantic_release) == patch
    assert semantic_release.ran == [PRINT_LAST_RELEASED, PRINT_NEXT, PRINT_NEXT_PATCH]


def test_a_bump_is_used_as_it_is(tmp_path, dist):
    semantic_release = FakeSemanticRelease("0.1.0", "0.2.0")

    assert next_version(f"{tmp_path}/previous", dist, semantic_release) == "0.2.0"
    assert semantic_release.ran == [PRINT_LAST_RELEASED, PRINT_NEXT]


def test_no_version_off_main_raises(tmp_path, dist):
    with pytest.raises(ReleaseError, match="not a version"):
        next_version(f"{tmp_path}/previous", dist, FakeSemanticRelease("", ""))


def test_an_empty_dist_raises(tmp_path):
    os.makedirs(f"{tmp_path}/dist")

    with pytest.raises(ReleaseError, match="no files to release"):
        next_version(f"{tmp_path}/previous", f"{tmp_path}/dist", no_semantic_release)


def test_semantic_release_failing_raises():
    with pytest.raises(ReleaseError, match="exited with status 2"):
        run_semantic_release(["version", "--no-such-option"])
