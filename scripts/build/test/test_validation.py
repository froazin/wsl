import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from scripts.build.validation import expectation_problems, indented_tags, leaked_paths, merge_problems, source_problems

EXPECT = {
    "user": True, "username": "jdoe", "gh_dir": "", "extensions": [], "skipped": [], "gh_extensions": [],
    "gh_skipped": [],
}  # fmt: skip
PODMAN_USERS = ["systemctl", "--global", "enable", "podman.socket"]
USER_INSTALL = ["runuser", "-l", "jdoe", "-c", "git clone d ~/d && sh ~/d/src/install.sh"]
ROOT_INSTALL = ["runuser", "-l", "root", "-c", "sh /home/jdoe/d/src/install.sh"]


def merged():
    """Returns a merged cloud-config for jdoe that meets EXPECT."""

    return {
        "users": [{"name": "jdoe"}],
        "write_files": [
            {"path": "/home/jdoe/.gitconfig", "content": ""},
            {"path": "/etc/systemd/user/podman.socket.d/10-not-root.conf", "content": "[Unit]\nConditionUser=!root\n"},
        ],
        "runcmd": [
            PODMAN_USERS,
            ["systemctl", "enable", "--now", "podman.socket"],
            ["sh", "-c", "if [ -x /usr/bin/zsh ]; then usermod -s /usr/bin/zsh root; fi"],
            USER_INSTALL,
            ROOT_INSTALL,
        ],
    }


def test_a_merged_config_that_meets_the_expectations_has_no_problems():
    assert expectation_problems(merged(), EXPECT) == []


def test_a_user_without_one_expected_is_a_problem():
    problems = expectation_problems(merged(), {**EXPECT, "user": False})

    assert "users rendered=True, expected False" in problems
    assert ".gitconfig rendered=True, expected False" in problems


def test_podman_socket_enabled_after_the_first_login_is_a_problem():
    doc = merged()
    doc["runcmd"] = [["runuser", "-l", "jdoe", "-c", "true"], *doc["runcmd"]]

    assert expectation_problems(doc, EXPECT) == [
        "podman.socket is enabled after the first runuser -l starts the user's manager"
    ]


def test_roots_install_before_the_users_clone_or_with_a_tilde_is_a_problem():
    doc = merged()
    doc["runcmd"][-2:] = [["runuser", "-l", "root", "-c", "sh ~/d/src/install.sh"], USER_INSTALL]

    assert expectation_problems(doc, EXPECT) == [
        "root's install path uses ~, which runuser -l expands to /root",
        "root's install does not follow the user's clone",
    ]


def test_extensions_are_checked_in_order_with_the_ones_skipped():
    doc = merged()
    doc["runcmd"] += [
        ["runuser", "-l", "jdoe", "-c", "code --install-extension b.c"],
        ["runuser", "-l", "jdoe", "-c", "code --install-extension a.b"],
        ["printf", "Skipped vscode_extensions entry: %s\n", "x"],
        ["runuser", "-l", "root", "-c", "gh extension install a/b"],
    ]
    expect = {**EXPECT, "extensions": ["a.b", "b.c"], "gh_extensions": ["a/b"]}

    assert expectation_problems(doc, expect) == [
        "extensions installed ['b.c', 'a.b'], expected ['a.b', 'b.c']",
        "extensions reported as skipped ['x'], expected []",
        "a gh extension install does not run as the user",
    ]


def test_runcmd_that_cannot_be_written_as_utf8_is_a_problem():
    doc = merged()
    doc["runcmd"].append(["printf", "%s", "\ud83d"])

    [problem] = expectation_problems(doc, EXPECT)
    assert problem.startswith("runcmd cannot be written as a script: ")


def test_a_workspace_directory_must_match_the_github_owner():
    doc = merged()
    doc["runcmd"].append(["runuser", "-u", "jdoe", "--", "mkdir", "-p", "/home/jdoe/workspaces/github.com/x"])

    assert expectation_problems(doc, EXPECT) == ["unexpected workspace dirs ['/home/jdoe/workspaces/github.com/x']"]
    assert expectation_problems(doc, {**EXPECT, "gh_dir": "x"}) == []


HEADER = "#cloud-config\n\n# from 2 files\n# 10-a\n# 20-b\n\n---\n"
PARTS = {"10-a": {"packages": ["a"], "runcmd": [["a"]]}, "20-b": {"packages": ["b"], "runcmd": None}}


def test_lists_appended_in_name_order_have_no_problems():
    assert merge_problems(HEADER, {"packages": ["a", "b"], "runcmd": [["a"]]}, PARTS) == []


def test_a_part_that_replaces_the_earlier_lists_is_a_problem():
    assert merge_problems(HEADER, {"packages": ["b"], "runcmd": [["a"]]}, PARTS) == [
        "packages is not every part's packages appended in name order: 1 entries, expected 2, first difference at"
        " entry 0"
    ]


def test_a_part_left_out_of_the_merge_is_a_problem():
    header = "#cloud-config\n\n# from 1 files\n# 10-a\n\n---\n"

    assert merge_problems(header, {"packages": ["a", "b"], "runcmd": [["a"]]}, PARTS) == [
        "merged parts ['10-a'], expected ['10-a', '20-b']"
    ]


def test_indented_tags_are_jinja_tags_and_comments_that_start_an_indented_line():
    text = "## template: jinja\n{% if x %}\n  {% endif %}\n\t{# c #}\n  - {{ x }}\n  - a {% if y %}b{% endif %}\n"

    assert indented_tags(text) == [3, 4]


def test_leaked_paths_are_concrete_windows_profile_paths():
    text = "/mnt/c/Users/jdoe/x\n/mnt/c/Users/<you>/x\n/mnt/c/Users/*/x\n/mnt/c/Users/jdoe/<you>\n/mnt/c/Users/\n"

    assert leaked_paths(text) == ["/mnt/c/Users/jdoe/x"]


def test_source_problems_read_mime_parts_and_check_tags_only_in_src(tmp_path):
    src, dist = tmp_path / "src", tmp_path / "dist"
    os.makedirs(src / "x.d")
    os.makedirs(dist)
    (src / "x.d" / "10-a").write_text("## template: jinja\n#cloud-config\n  {% if a %}\n{% endif %}\n")
    part = MIMEText("path: /mnt/c/Users/jdoe/x\n", "cloud-config", "utf-8")
    part.add_header("Content-Disposition", "attachment", filename="10-a")
    mime = MIMEMultipart()
    mime.attach(part)
    (dist / "x").write_bytes(mime.as_bytes())

    assert source_problems(str(src), str(dist)) == [
        f"{dist}/x:10-a contains a concrete /mnt/c/Users/<name>/ path: path: /mnt/c/Users/jdoe/x",
        f"{src}/x.d/10-a:3: a Jinja tag is not at column 0",
    ]
