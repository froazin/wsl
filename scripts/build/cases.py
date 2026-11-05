"""The meta-data cases the user-data is checked against, each with what its merged cloud-config must hold."""

from typing import Any, NamedTuple

V1 = {
    "cloud_name": "wsl", "platform": "wsl", "cloud_id": "wsl",
    "distro": "ubuntu", "distro_release": "resolute", "distro_version": "26.04",
    "instance_id": "ubuntu-wsl", "local_hostname": "host", "region": None,
    "availability_zone": None, "kernel_release": "6", "machine": "x86_64",
    "python_version": "3", "variant": "ubuntu", "subplatform": "unknown",
    "system_platform": "x", "public_ssh_keys": [],
}  # fmt: skip
"""The v1 instance-data a WSL instance has at boot, which the parts' Jinja can read."""

PROGRAM = "/mnt/c/Users/<you>/op-ssh-sign-wsl.exe"
HOSTILE = 'O\'Hara "Q" \\ # ; {{ x }}'
BAD_EXTENSIONS = [
    "a.b; rm -rf ~", "$(id).x", "a.b'c", 'a"b.c', "no-dot", ".x", "x.",
    "-a.b", "a.b.c", "a b.c", "a\nb.c", "\u00fcn.code", "\U0001f600.x",
    "C:\\new\\cext.vsix", "{{ x }}", 42, None,
]  # fmt: skip
BAD_GH_EXTENSIONS = [
    "a/b; rm -rf ~", "$(id)/x", "a/b'c", 'a"b/c', "no-slash", "/a/b", "a/b/", "-a/b",
    "a/b/c/d", "a b/c", "a\nb/c", ".", "./gh-x", "../a/b", "a/.b", "\u00fcn/gh-x",
    "\U0001f600/x", "http://github.com/a/gh-b", "https://github.com/a",
    "https://a/b/c/d", "git@github.com:a/gh-b", "C:\\x\\gh-y", "a/{{ x }}", 42, None,
]  # fmt: skip


class Case(NamedTuple):
    """One meta-data case: the meta-data to render with, and what the merged cloud-config must hold.

    expect has these keys:
      user          - whether user-specific config should render
      username      - the only user `users` may list
      gh_dir        - expected ~/workspaces/github.com/<owner> directory, or ""
      git_name      - exact user.name git must read back from the rendered .gitconfig
      extensions    - VS Code extension IDs installed, in order
      skipped       - vscode_extensions entries reported as invalid
      gh_extensions - gh extensions installed, in order
      gh_skipped    - gh_extensions entries reported as invalid
      signer        - principal git should verify git_signingkey's signatures as, or None for no allowed_signers file
      signer_key    - private key that signs for signer
      ssh_program   - gpg.ssh.program git must read back
    """

    name: str
    meta_data: dict[str, Any]
    expect: dict[str, Any]


def skipped(entries: list[Any]) -> list[str]:
    """Returns entries as the user-data reports them when it skips them: as ASCII text, with backslash escapes."""

    return [str(e).encode("ascii", "backslashreplace").decode("ascii") for e in entries]


def instance_data(meta_data: dict[str, Any]) -> dict[str, Any]:
    """Returns the instance-data cloud-init renders the parts' Jinja with, for an instance with this meta-data."""

    return {"v1": V1, "ds": {"meta_data": meta_data}}


def cases(keys_dir: str, signer: str, ecdsa: str, example: dict[str, Any]) -> list[Case]:
    """Returns every case, with the defaults filled in.

    keys_dir holds the private keys `signer` (ed25519) and `ecdsa`, whose public keys are signer and ecdsa. example is
    the README's meta-data example, which one case renders with as it is, plus a username.
    """

    user = {"user": True, "gh_dir": "", "git_name": ""}
    no_user = {"user": False, "gh_dir": "", "git_name": ""}
    table: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
        "full": ({"username": "jdoe", "git_name": "Jane Doe",
                  "git_email": "1+jdoe@users.noreply.github.com",
                  "git_signingkey": signer,
                  "git_ssh_program": PROGRAM,
                  "vscode_extensions": ["Anthropic.claude-code", "ms-python.python"],
                  "gh_extensions": ["https://github.com/nektos/gh-act", "jdoe/gh-x"]},
                 {"user": True, "gh_dir": "jdoe", "git_name": "Jane Doe",
                  "extensions": ["Anthropic.claude-code", "ms-python.python"],
                  "gh_extensions": ["https://github.com/nektos/gh-act", "jdoe/gh-x"],
                  "signer": "1+jdoe@users.noreply.github.com", "ssh_program": PROGRAM}),
        "signingkey-no-email": ({"username": "jdoe", "git_signingkey": f"  key::{signer}\t"},
                                {**user, "signer": "*"}),
        "signingkey-odd-email": ({"username": "jdoe", "git_email": "a,b *@example.com", "git_signingkey": signer},
                                 {**user, "signer": "*"}),
        "signingkey-unicode-email": ({"username": "jdoe", "git_email": "j\u00e4ne@example.com",
                                      "git_signingkey": signer},
                                     {**user, "signer": "*"}),
        "signingkey-ecdsa": ({"username": "jdoe", "git_email": "jane@example.com", "git_signingkey": f"key::{ecdsa}"},
                             {**user, "signer": "jane@example.com", "signer_key": f"{keys_dir}/ecdsa"}),
        # git reads a bare non-ssh- key as a file path.
        "signingkey-bare-ecdsa": ({"username": "jdoe", "git_signingkey": ecdsa}, user),
        "signingkey-path": ({"username": "jdoe", "git_email": "jane@example.com",
                             "git_signingkey": "~/.ssh/id_ed25519.pub", "git_ssh_program": PROGRAM},
                            {**user, "ssh_program": PROGRAM}),
        "signingkey-hostile": ({"username": "jdoe", "git_signingkey": "ssh-ed25519 AAAA$(id)x jane"}, user),
        "signingkey-unknown-type": ({"username": "jdoe", "git_signingkey": "key::foo-ed25519 AAAA"}, user),
        "signingkey-bad-type": ({"username": "jdoe", "git_signingkey": 'ssh-ed"25519 AAAA'}, user),
        "signingkey-unicode-type": ({"username": "jdoe", "git_signingkey": "ssh-ed\u00b225519 AAAA"}, user),
        "signingkey-unicode-data": ({"username": "jdoe", "git_signingkey": "ssh-ed25519 AAAA\u00e9"}, user),
        "signingkey-type-only": ({"username": "jdoe", "git_signingkey": "ssh-ed25519"}, user),
        "signingkey-list": ({"username": "jdoe", "git_signingkey": [signer]}, user),
        "signingkey-no-user": ({"git_email": "jane@example.com", "git_signingkey": signer}, no_user),
        "readme-example": ({**example, "username": "jdoe"},
                           {**user, "extensions": ["Anthropic.claude-code", "ms-python.python"],
                            "gh_extensions": ["https://github.com/nektos/gh-act"]}),
        "extensions-string": ({"username": "jdoe", "vscode_extensions": "Anthropic.claude-code, ms-python.python"},
                              {**user, "extensions": ["Anthropic.claude-code", "ms-python.python"]}),
        "extensions-hostile": ({"username": "jdoe", "vscode_extensions": ["ok.ext", *BAD_EXTENSIONS, "Pub-1.name-2"]},
                               {**user, "extensions": ["ok.ext", "Pub-1.name-2"],
                                "skipped": skipped(BAD_EXTENSIONS)}),
        "extensions-mapping": ({"username": "jdoe", "vscode_extensions": {"a": "b.c"}}, user),
        "extensions-number": ({"username": "jdoe", "vscode_extensions": 5}, user),
        "extensions-no-user": ({"vscode_extensions": ["Anthropic.claude-code"]}, no_user),
        "gh-extensions-string": ({"username": "jdoe", "gh_extensions": "nektos/gh-act, github.com/jdoe/gh-x"},
                                 {**user, "gh_extensions": ["nektos/gh-act", "github.com/jdoe/gh-x"]}),
        "gh-extensions-hostile": ({"username": "jdoe",
                                   "gh_extensions": ["a/gh-b", *BAD_GH_EXTENSIONS, "example.com/Org_1/gh-x.y",
                                                     "https://github.com/nektos/gh-act.git"]},
                                  {**user, "gh_extensions": ["a/gh-b", "example.com/Org_1/gh-x.y",
                                                             "https://github.com/nektos/gh-act.git"],
                                   "gh_skipped": skipped(BAD_GH_EXTENSIONS)}),
        "gh-extensions-mapping": ({"username": "jdoe", "gh_extensions": {"a": "b/c"}}, user),
        "gh-extensions-number": ({"username": "jdoe", "gh_extensions": 5}, user),
        "gh-extensions-no-user": ({"gh_extensions": ["nektos/gh-act"]}, no_user),
        "empty-values": ({"username": None, "git_name": None}, no_user),
        "no-meta-data": ({}, no_user),
        "hostile-name": ({"username": "jdoe", "git_name": HOSTILE}, {**user, "git_name": HOSTILE}),
        "legacy-noreply": ({"username": "jdoe", "git_email": "jdoe@users.noreply.github.com"},
                           {**user, "gh_dir": "jdoe"}),
        "plain-email": ({"username": "jdoe", "git_email": "jane@example.com"}, user),
        "path-traversal": ({"username": "jdoe", "git_email": "1+../../etc@users.noreply.github.com"}, user),
    }  # fmt: skip

    result = []
    for name, (meta, expect) in table.items():
        meta = {"instance-id": "ubuntu-wsl", **meta}
        defaults = {
            "extensions": [], "skipped": [], "gh_extensions": [], "gh_skipped": [], "signer": None,
            "signer_key": f"{keys_dir}/signer", "ssh_program": "", "username": meta.get("username"),
        }  # fmt: skip
        result.append(Case(name, meta, {**defaults, **expect}))
    return result
