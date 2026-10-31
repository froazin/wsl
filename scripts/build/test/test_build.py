import os
import shlex

import pytest

from scripts.build import BuildError, build
from scripts.build.build import make_mime_command, part_names, part_type


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def test_part_type_is_jinja2_only_with_the_header_on_the_first_line(tmp_path):
    write(f"{tmp_path}/jinja", "## template: jinja\n#cloud-config\n")
    write(f"{tmp_path}/plain", "#cloud-config\n")
    write(f"{tmp_path}/late", "#cloud-config\n## template: jinja\n")

    assert part_type(f"{tmp_path}/jinja") == "jinja2"
    assert part_type(f"{tmp_path}/plain") == "cloud-config"
    assert part_type(f"{tmp_path}/late") == "cloud-config"


def test_part_names_are_files_in_name_order(tmp_path):
    for name in ("20-b", "10-a", "99-z"):
        write(f"{tmp_path}/{name}", "#cloud-config\n")
    os.makedirs(f"{tmp_path}/50-folder")

    assert part_names(str(tmp_path)) == ["10-a", "20-b", "99-z"]


def test_part_names_rejects_an_empty_folder(tmp_path):
    with pytest.raises(BuildError, match="has no parts"):
        part_names(str(tmp_path))


def test_make_mime_command_attaches_each_part_by_name_from_the_folder(tmp_path):
    parts = tmp_path / "my parts.d"
    write(f"{parts}/10-a", "#cloud-config\n")
    write(f"{parts}/20-b", "## template: jinja\n#cloud-config\n")

    command = make_mime_command(str(parts), "dist/out")

    cd, rest = command.split(" && ", 1)
    make_mime, output = rest.split(" > ")
    assert shlex.split(cd) == ["cd", str(parts)]
    assert shlex.split(make_mime) == [
        "cloud-init", "devel", "make-mime", "--attach", "10-a:cloud-config", "--attach", "20-b:jinja2",
    ]  # fmt: skip
    assert shlex.split(output) == [os.path.abspath("dist/out")]


def test_build_joins_parts_folders_and_copies_files(tmp_path):
    src, dist = tmp_path / "src", tmp_path / "dist"
    write(f"{src}/Instance.user-data.d/10-a.user-data", "#cloud-config\n")
    write(f"{src}/Instance.meta-data", "instance-id: x\n")
    write(f"{dist}/stale", "left over\n")
    commands: list[str] = []

    outputs = build(commands.append, str(src), str(dist))

    assert outputs == [f"{dist}/Instance.meta-data", f"{dist}/Instance.user-data"]
    assert len(commands) == 1
    assert commands[0].endswith(shlex.quote(f"{dist}/Instance.user-data"))
    assert sorted(os.listdir(dist)) == ["Instance.meta-data"]
    with open(f"{dist}/Instance.meta-data") as f:
        assert f.read() == "instance-id: x\n"


def test_build_rejects_a_folder_without_the_parts_suffix(tmp_path):
    os.makedirs(tmp_path / "src" / "stray")

    with pytest.raises(BuildError, match="neither a file nor a folder"):
        build(lambda _: None, str(tmp_path / "src"), str(tmp_path / "dist"))
