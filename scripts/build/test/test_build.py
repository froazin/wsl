import json
import os
import re
import shlex

import pytest

from scripts.build import BuildError, build
from scripts.build.build import make_mime_command, part_type


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def manifest(src: str, distro: str, *fragments: str) -> None:
    write(f"{src}/distros/{distro}/manifest.json", json.dumps({"fragments": list(fragments)}))


def test_part_type_is_jinja2_only_with_the_header_on_the_first_line(tmp_path):
    write(f"{tmp_path}/jinja", "## template: jinja\n#cloud-config\n")
    write(f"{tmp_path}/plain", "#cloud-config\n")
    write(f"{tmp_path}/late", "#cloud-config\n## template: jinja\n")

    assert part_type(f"{tmp_path}/jinja") == "jinja2"
    assert part_type(f"{tmp_path}/plain") == "cloud-config"
    assert part_type(f"{tmp_path}/late") == "cloud-config"


def test_make_mime_command_attaches_each_fragment_by_file_name_from_the_stage(tmp_path):
    write(f"{tmp_path}/shared/10-a.user-data", "#cloud-config\n")
    write(f"{tmp_path}/own/20-b.user-data", "## template: jinja\n#cloud-config\n")
    stage = tmp_path / "my stage"

    command = make_mime_command(
        [f"{tmp_path}/shared/10-a.user-data", f"{tmp_path}/own/20-b.user-data"], str(stage), "dist/out"
    )

    cd, rest = command.split(" && ", 1)
    make_mime, output = rest.split(" > ")
    assert shlex.split(cd) == ["cd", str(stage)]
    assert shlex.split(make_mime) == [
        "cloud-init", "devel", "make-mime", "--attach", "10-a.user-data:cloud-config",
        "--attach", "20-b.user-data:jinja2",
    ]  # fmt: skip
    assert shlex.split(output) == [os.path.abspath("dist/out")]


def test_build_writes_one_user_data_per_distro_from_its_fragments(tmp_path):
    src, dist = tmp_path / "src", tmp_path / "dist"
    write(f"{src}/fragments/10-a.user-data", "#cloud-config\n")
    write(f"{src}/distros/Other-1/20-own.user-data", "#cloud-config\n")
    manifest(str(src), "Other-1", "10-a", "20-own")
    manifest(str(src), "Instance", "10-a")
    write(f"{dist}/stale", "left over\n")
    staged: list[list[str]] = []

    def run(command: str) -> None:
        stage = shlex.split(command.split(" && ", 1)[0])[1]
        staged.append(sorted(os.listdir(stage)))

    outputs = build(run, str(src), str(dist))

    assert outputs == [f"{dist}/Instance.user-data", f"{dist}/Other-1.user-data"]
    assert staged == [["10-a.user-data"], ["10-a.user-data", "20-own.user-data"]]
    assert os.listdir(dist) == []


def test_build_rejects_an_entry_in_src_other_than_fragments_and_distros(tmp_path):
    os.makedirs(tmp_path / "src" / "Ubuntu-26.04.user-data.d")

    with pytest.raises(BuildError, match=re.escape("holds Ubuntu-26.04.user-data.d")):
        build(lambda _: None, str(tmp_path / "src"), str(tmp_path / "dist"))


def test_build_leaves_dist_alone_when_a_manifest_is_wrong(tmp_path):
    src, dist = tmp_path / "src", tmp_path / "dist"
    manifest(str(src), "Instance", "10-missing")
    write(f"{dist}/Instance.user-data", "last build\n")

    with pytest.raises(BuildError, match="10-missing"):
        build(lambda _: None, str(src), str(dist))
    assert os.listdir(dist) == ["Instance.user-data"]
