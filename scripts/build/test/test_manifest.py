import json
import os
import re

import pytest

from scripts.build import BuildError, load_distros
from scripts.build.manifest import shared_fragments


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def manifest(src: str, distro: str, content: object) -> None:
    write(f"{src}/distros/{distro}/manifest.json", json.dumps(content))


@pytest.fixture
def src(tmp_path) -> str:
    """A src/ with two shared fragments and no distros."""

    for name in ("10-a", "20-b"):
        write(f"{tmp_path}/src/fragments/{name}.user-data", "#cloud-config\n")
    return f"{tmp_path}/src"


def test_a_distro_finds_shared_fragments_and_its_own_in_name_order(src):
    write(f"{src}/distros/Instance/15-own.user-data", "#cloud-config\n")
    manifest(src, "Instance", {"fragments": ["10-a", "15-own", "20-b"]})

    [distro] = load_distros(src)

    assert distro.name == "Instance"
    assert distro.fragments == (
        f"{src}/fragments/10-a.user-data",
        f"{src}/distros/Instance/15-own.user-data",
        f"{src}/fragments/20-b.user-data",
    )
    assert distro.fragment_names() == ["10-a.user-data", "15-own.user-data", "20-b.user-data"]


def test_distros_load_in_name_order(src):
    manifest(src, "b", {"fragments": ["10-a"]})
    manifest(src, "A", {"fragments": ["20-b"]})

    assert [distro.name for distro in load_distros(src)] == ["A", "b"]


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ({}, "'fragments' is a required property"),
        ({"fragments": []}, "is too short"),
        ({"fragments": ["10-a", "10-a"]}, "has non-unique elements"),
        ({"fragments": ["10-a"], "name": "x"}, "Additional properties are not allowed"),
        ({"fragments": ["10-a.user-data"]}, "does not match"),
        ({"fragments": ["20-b", "10-a"]}, "must list its fragments in name order"),
        ({"fragments": ["10-a", "30-missing"]}, "lists 30-missing, which is in neither"),
    ],
)
def test_a_wrong_manifest_is_an_error(src, content, error):
    manifest(src, "Instance", content)

    with pytest.raises(BuildError, match=error):
        load_distros(src)


def test_a_fragment_in_both_folders_is_an_error(src):
    write(f"{src}/distros/Instance/10-a.user-data", "#cloud-config\n")
    manifest(src, "Instance", {"fragments": ["10-a"]})

    with pytest.raises(BuildError, match="lists 10-a, which is in both"):
        load_distros(src)


def test_a_file_the_manifest_does_not_list_is_an_error(src):
    write(f"{src}/distros/Instance/15-own.user-data", "#cloud-config\n")
    write(f"{src}/distros/Instance/notes.txt", "\n")
    manifest(src, "Instance", {"fragments": ["10-a"]})

    error = "holds 15-own.user-data, notes.txt, which manifest.json doesn't list"
    with pytest.raises(BuildError, match=re.escape(error)):
        load_distros(src)


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        (lambda src: os.makedirs(f"{src}/distros/Instance"), "manifest.json not found"),
        (lambda src: write(f"{src}/distros/Instance/manifest.json", "{"), "isn't valid JSON"),
        (lambda src: manifest(src, "-bad name", {"fragments": ["10-a"]}), "isn't a WSL distribution name"),
        (lambda src: os.makedirs(f"{src}/distros"), "has no distros to build"),
        (lambda src: write(f"{src}/distros/Debian-13.json", "{}"), "holds Debian-13.json. Each distro is a folder"),
        (lambda src: None, "distros not found"),
    ],
)
def test_a_missing_or_broken_distro_is_an_error(src, setup, error):
    setup(src)

    with pytest.raises(BuildError, match=error):
        load_distros(src)


def test_the_repository_manifests_are_valid():
    distros = load_distros()

    assert distros
    assert all(distro.fragments for distro in distros)


def test_shared_fragments_are_every_file_in_the_fragments_folder(src, tmp_path):
    assert shared_fragments(src) == [f"{src}/fragments/10-a.user-data", f"{src}/fragments/20-b.user-data"]
    assert shared_fragments(f"{tmp_path}/none") == []
