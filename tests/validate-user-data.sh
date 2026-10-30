#!/usr/bin/env sh
#
# Render src/Ubuntu-26.04.user-data against mock instance-data and validate
# the result; `cloud-init schema` on the raw Jinja template proves nothing.
#
# Usage: validate.sh [path/to/Ubuntu-26.04.user-data
#                     [path/to/Ubuntu-26.04.meta-data]]

set -u

user_data="${1:-src/Ubuntu-26.04.user-data}"
meta_data="${2:-$(dirname "$user_data")/Ubuntu-26.04.meta-data}"
failed="false"

fail()
{
    printf 'FAIL: %s\n' "$*"
    failed="true"
}

die()
{
    printf '%s\n' "$*" >&2
    exit 2
}

for cmd in cloud-init python3 git shellcheck ssh-keygen; do
    command -v "$cmd" > /dev/null 2>&1 || die "missing required command: $cmd"
done

[ -f "$user_data" ] || die "user-data not found: $user_data"
[ -f "$meta_data" ] || die "meta-data not found: $meta_data"

work="$(mktemp -d)" || exit 2
trap 'rm -rf "$work"' EXIT

# Each case is a meta-data mapping plus the expectations checked below:
#   user      - whether user-specific config should render
#   gh_dir    - expected ~/workspaces/github.com/<owner> directory, or ""
#   git_name  - exact user.name git must read back from the rendered .gitconfig
#   extensions - VS Code extension IDs installed, in order (default: none)
#   skipped   - vscode_extensions entries reported as invalid (default: none)
#   gh_extensions - gh extensions installed, in order (default: none)
#   gh_skipped - gh_extensions entries reported as invalid (default: none)
#   signer    - principal git should verify git_signingkey's signatures as, or
#               null for no allowed_signers file (default: null)
#   signer_key - private key that signs for signer (default: the ed25519 key)
#   ssh_program - gpg.ssh.program git must read back (default: "")
python3 -I - "$work" "$meta_data" << 'EOF' || exit 2
import json
import subprocess
import sys

import yaml

work, meta_template = sys.argv[1:]

# Real keys, so the rendered allowed_signers is checked by ssh-keygen itself.
def keygen(name, *opts):
    subprocess.run(["ssh-keygen", "-q", *opts, "-N", "", "-C", "jane", "-f", f"{work}/{name}"], check=True)
    with open(f"{work}/{name}.pub") as f:
        return f.read().strip()

pubkey = keygen("signer", "-t", "ed25519")
ecdsa = keygen("ecdsa", "-t", "ecdsa", "-b", "256")
program = "/mnt/c/Users/<you>/op-ssh-sign-wsl.exe"

v1 = {
    "cloud_name": "wsl", "platform": "wsl", "cloud_id": "wsl",
    "distro": "ubuntu", "distro_release": "resolute", "distro_version": "26.04",
    "instance_id": "ubuntu-wsl", "local_hostname": "host", "region": None,
    "availability_zone": None, "kernel_release": "6", "machine": "x86_64",
    "python_version": "3", "variant": "ubuntu", "subplatform": "unknown",
    "system_platform": "x", "public_ssh_keys": [],
}

hostile = "O'Hara \"Q\" \\ # ; {{ x }}"
bad_extensions = ["a.b; rm -rf ~", "$(id).x", "a.b'c", 'a"b.c', "no-dot", ".x", "x.",
                  "-a.b", "a.b.c", "a b.c", "a\nb.c", "\u00fcn.code", "\U0001F600.x",
                  "C:\\new\\cext.vsix", "{{ x }}", 42, None]
bad_gh_extensions = ["a/b; rm -rf ~", "$(id)/x", "a/b'c", 'a"b/c', "no-slash", "/a/b", "a/b/", "-a/b",
                     "a/b/c/d", "a b/c", "a\nb/c", ".", "./gh-x", "../a/b", "a/.b", "\u00fcn/gh-x",
                     "\U0001F600/x", "http://github.com/a/gh-b", "https://github.com/a",
                     "https://a/b/c/d", "git@github.com:a/gh-b", "C:\\x\\gh-y", "a/{{ x }}", 42, None]

with open(meta_template) as f:
    shipped = yaml.safe_load(f)

cases = {
    "full": ({"username": "jdoe", "git_name": "Jane Doe",
              "git_email": "1+jdoe@users.noreply.github.com",
              "git_signingkey": pubkey,
              "git_ssh_program": program,
              "vscode_extensions": ["Anthropic.claude-code", "ms-python.python"],
              "gh_extensions": ["https://github.com/nektos/gh-act", "jdoe/gh-x"]},
             {"user": True, "gh_dir": "jdoe", "git_name": "Jane Doe",
              "extensions": ["Anthropic.claude-code", "ms-python.python"],
              "gh_extensions": ["https://github.com/nektos/gh-act", "jdoe/gh-x"],
              "signer": "1+jdoe@users.noreply.github.com", "ssh_program": program}),
    "signingkey-no-email": ({"username": "jdoe", "git_signingkey": f"  key::{pubkey}\t"},
                            {"user": True, "gh_dir": "", "git_name": "", "signer": "*"}),
    "signingkey-odd-email": ({"username": "jdoe", "git_email": "a,b *@example.com", "git_signingkey": pubkey},
                             {"user": True, "gh_dir": "", "git_name": "", "signer": "*"}),
    "signingkey-unicode-email": ({"username": "jdoe", "git_email": "j\u00e4ne@example.com", "git_signingkey": pubkey},
                                 {"user": True, "gh_dir": "", "git_name": "", "signer": "*"}),
    "signingkey-ecdsa": ({"username": "jdoe", "git_email": "jane@example.com", "git_signingkey": f"key::{ecdsa}"},
                         {"user": True, "gh_dir": "", "git_name": "", "signer": "jane@example.com",
                          "signer_key": f"{work}/ecdsa"}),
    # git reads a bare non-ssh- key as a file path.
    "signingkey-bare-ecdsa": ({"username": "jdoe", "git_signingkey": ecdsa},
                              {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-path": ({"username": "jdoe", "git_email": "jane@example.com",
                         "git_signingkey": "~/.ssh/id_ed25519.pub", "git_ssh_program": program},
                        {"user": True, "gh_dir": "", "git_name": "", "ssh_program": program}),
    "signingkey-hostile": ({"username": "jdoe", "git_signingkey": "ssh-ed25519 AAAA$(id)x jane"},
                           {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-unknown-type": ({"username": "jdoe", "git_signingkey": "key::foo-ed25519 AAAA"},
                                {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-bad-type": ({"username": "jdoe", "git_signingkey": 'ssh-ed"25519 AAAA'},
                            {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-unicode-type": ({"username": "jdoe", "git_signingkey": "ssh-ed\u00b225519 AAAA"},
                                {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-unicode-data": ({"username": "jdoe", "git_signingkey": "ssh-ed25519 AAAA\u00e9"},
                                {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-type-only": ({"username": "jdoe", "git_signingkey": "ssh-ed25519"},
                             {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-list": ({"username": "jdoe", "git_signingkey": [pubkey]},
                        {"user": True, "gh_dir": "", "git_name": ""}),
    "signingkey-no-user": ({"git_email": "jane@example.com", "git_signingkey": pubkey},
                           {"user": False, "gh_dir": "", "git_name": ""}),
    "shipped-meta-data": ({**shipped, "username": "jdoe"},
                          {"user": True, "gh_dir": "", "git_name": "",
                           "extensions": ["Anthropic.claude-code", "ms-python.python"],
                           "gh_extensions": ["https://github.com/nektos/gh-act"]}),
    "extensions-string": ({"username": "jdoe", "vscode_extensions": "Anthropic.claude-code, ms-python.python"},
                          {"user": True, "gh_dir": "", "git_name": "",
                           "extensions": ["Anthropic.claude-code", "ms-python.python"]}),
    "extensions-hostile": ({"username": "jdoe", "vscode_extensions": ["ok.ext", *bad_extensions, "Pub-1.name-2"]},
                           {"user": True, "gh_dir": "", "git_name": "",
                            "extensions": ["ok.ext", "Pub-1.name-2"],
                            "skipped": [str(e).encode("ascii", "backslashreplace").decode("ascii")
                                        for e in bad_extensions]}),
    "extensions-mapping": ({"username": "jdoe", "vscode_extensions": {"a": "b.c"}},
                           {"user": True, "gh_dir": "", "git_name": ""}),
    "extensions-number": ({"username": "jdoe", "vscode_extensions": 5},
                          {"user": True, "gh_dir": "", "git_name": ""}),
    "extensions-no-user": ({"vscode_extensions": ["Anthropic.claude-code"]},
                           {"user": False, "gh_dir": "", "git_name": ""}),
    "gh-extensions-string": ({"username": "jdoe", "gh_extensions": "nektos/gh-act, github.com/jdoe/gh-x"},
                             {"user": True, "gh_dir": "", "git_name": "",
                              "gh_extensions": ["nektos/gh-act", "github.com/jdoe/gh-x"]}),
    "gh-extensions-hostile": ({"username": "jdoe",
                               "gh_extensions": ["a/gh-b", *bad_gh_extensions, "example.com/Org_1/gh-x.y",
                                                 "https://github.com/nektos/gh-act.git"]},
                              {"user": True, "gh_dir": "", "git_name": "",
                               "gh_extensions": ["a/gh-b", "example.com/Org_1/gh-x.y",
                                                 "https://github.com/nektos/gh-act.git"],
                               "gh_skipped": [str(e).encode("ascii", "backslashreplace").decode("ascii")
                                              for e in bad_gh_extensions]}),
    "gh-extensions-mapping": ({"username": "jdoe", "gh_extensions": {"a": "b/c"}},
                              {"user": True, "gh_dir": "", "git_name": ""}),
    "gh-extensions-number": ({"username": "jdoe", "gh_extensions": 5},
                             {"user": True, "gh_dir": "", "git_name": ""}),
    "gh-extensions-no-user": ({"gh_extensions": ["nektos/gh-act"]},
                              {"user": False, "gh_dir": "", "git_name": ""}),
    "empty-values": ({"username": None, "git_name": None},
                     {"user": False, "gh_dir": "", "git_name": ""}),
    "no-meta-data": ({}, {"user": False, "gh_dir": "", "git_name": ""}),
    "hostile-name": ({"username": "jdoe", "git_name": hostile},
                     {"user": True, "gh_dir": "", "git_name": hostile}),
    "legacy-noreply": ({"username": "jdoe", "git_email": "jdoe@users.noreply.github.com"},
                       {"user": True, "gh_dir": "jdoe", "git_name": ""}),
    "plain-email": ({"username": "jdoe", "git_email": "jane@example.com"},
                    {"user": True, "gh_dir": "", "git_name": ""}),
    "path-traversal": ({"username": "jdoe", "git_email": "1+../../etc@users.noreply.github.com"},
                       {"user": True, "gh_dir": "", "git_name": ""}),
}

with open(f"{work}/cases", "w") as index:
    for name, (meta, expect) in cases.items():
        meta = {"instance-id": "ubuntu-wsl", **meta}
        expect = {"extensions": [], "skipped": [], "gh_extensions": [], "gh_skipped": [], "signer": None, "signer_key": f"{work}/signer",
                  "ssh_program": "", "username": meta.get("username"), **expect}
        with open(f"{work}/{name}.json", "w") as f:
            json.dump({"v1": v1, "ds": {"meta_data": meta}}, f)
        with open(f"{work}/{name}.expect.json", "w") as f:
            json.dump(expect, f)
        index.write(name + "\n")
EOF

[ -s "$work/cases" ] || die 'no cases were generated'

while read -r case; do
    rendered="$work/$case.yaml"

    if ! cloud-init devel render -i "$work/$case.json" "$user_data" > "$rendered" 2> "$work/$case.err"; then
        fail "$case: render failed: $(tail -1 "$work/$case.err")"
        continue
    fi

    if grep -q 'CI_MISSING_JINJA_VAR' "$rendered"; then
        fail "$case: rendered output references an undefined Jinja variable"
    fi

    if ! cloud-init schema -c "$rendered" > "$work/$case.schema" 2>&1; then
        fail "$case: schema: $(grep -v 'obj.pkl\|datasource' "$work/$case.schema" | head -3)"
    fi

    python3 -I - "$rendered" "$work/$case.expect.json" "$work/$case" << 'EOF' || failed="true"
import json
import subprocess
import sys

import yaml
from cloudinit.util import shellify

rendered, expect_path, prefix = sys.argv[1:]
case = prefix.rsplit("/", 1)[-1]
expect = json.load(open(expect_path))
text = open(rendered).read()
doc = yaml.safe_load(text)
problems = []

if not text.startswith("#cloud-config"):
    problems.append("rendered output does not start with #cloud-config")

files = {f["path"]: f for f in doc.get("write_files", [])}
gitconfig = next((f for p, f in files.items() if p.endswith("/.gitconfig")), None)
has_user = "users" in doc

if has_user != expect["user"]:
    problems.append(f"users rendered={has_user}, expected {expect['user']}")
elif has_user and [u.get("name") for u in doc["users"]] != [expect["username"]]:
    problems.append(f"users {doc['users']!r}, expected only {expect['username']!r}")
if (gitconfig is not None) != expect["user"]:
    problems.append(f".gitconfig rendered={gitconfig is not None}, expected {expect['user']}")

cmds = [c if isinstance(c, list) else [c] for c in doc.get("runcmd", [])]

def find(pred):
    return next((i for i, c in enumerate(cmds) if pred(c)), None)

want = expect["gh_dir"]
mkdirs = [a for c in cmds for a in map(str, c) if a.startswith("/home/") and "/workspaces/github.com/" in a]
if want and not any(d.endswith(f"/workspaces/github.com/{want}") for d in mkdirs):
    problems.append(f"expected workspace dir github.com/{want}, got {mkdirs}")
if not want and mkdirs:
    problems.append(f"unexpected workspace dirs {mkdirs}")

installs = [c for c in cmds if "--install-extension" in str(c[-1])]
installed = [str(c[-1]).rsplit(" ", 1)[-1] for c in installs]
if installed != expect["extensions"]:
    problems.append(f"extensions installed {installed}, expected {expect['extensions']}")
if any(c[:3] != ["runuser", "-l", "jdoe"] for c in installs):
    problems.append("an extension install does not run as the user")
skipped = [c[-1] for c in cmds if c[0] == "printf" and "vscode_extensions" in str(c[1])]
if skipped != expect["skipped"]:
    problems.append(f"extensions reported as skipped {skipped!r}, expected {expect['skipped']!r}")

gh_installs = [c for c in cmds if str(c[-1]).startswith("gh extension install ")]
gh_installed = [str(c[-1]).removeprefix("gh extension install ") for c in gh_installs]
if gh_installed != expect["gh_extensions"]:
    problems.append(f"gh extensions installed {gh_installed}, expected {expect['gh_extensions']}")
if any(c[:4] != ["runuser", "-l", "jdoe", "-c"] for c in gh_installs):
    problems.append("a gh extension install does not run as the user")
gh_skipped = [c[-1] for c in cmds if c[0] == "printf" and "gh_extensions" in str(c[1])]
if gh_skipped != expect["gh_skipped"]:
    problems.append(f"gh extensions reported as skipped {gh_skipped!r}, expected {expect['gh_skipped']!r}")

# The first `runuser -l` starts the user's systemd manager, which only reads
# global wants when it starts.
podman = find(lambda c: c == ["systemctl", "--global", "enable", "podman.socket"])
first_login = find(lambda c: c[:2] == ["runuser", "-l"])
if podman is None:
    problems.append("runcmd does not enable podman.socket for users")
elif first_login is not None and first_login < podman:
    problems.append("podman.socket is enabled after the first runuser -l starts the user's manager")
if ["systemctl", "enable", "--now", "podman.socket"] not in cmds:
    problems.append("runcmd does not enable the system podman.socket for root")
not_root = files.get("/etc/systemd/user/podman.socket.d/10-not-root.conf", {})
if "ConditionUser=!root" not in not_root.get("content", "").splitlines():
    problems.append("root's user manager is not kept from starting the user podman.socket")

# cc_runcmd writes the whole script as UTF-8; one unencodable item fails all of it.
try:
    shellify(doc.get("runcmd", [])).encode("utf-8")
except Exception as e:
    problems.append(f"runcmd cannot be written as a script: {e}")

root_shell = find(lambda c: "usermod -s /usr/bin/zsh root" in " ".join(map(str, c)))
root_install = find(lambda c: c[:3] == ["runuser", "-l", "root"])
user_install = find(lambda c: c[:2] == ["runuser", "-l"] and c[2] != "root" and "src/install.sh" in str(c[-1]))
if root_shell is None:
    problems.append("runcmd does not set root's login shell")
if root_install is None:
    problems.append("runcmd does not install the dotfiles for root")
else:
    script = str(cmds[root_install][-1])
    if root_shell is not None and root_install < root_shell:
        problems.append("root's dotfiles install runs before its login shell is set")
    if "~" in script:
        problems.append("root's install path uses ~, which runuser -l expands to /root")
    if expect["user"] and (user_install is None or root_install < user_install):
        problems.append("root's install does not follow the user's clone")
    if not expect["user"] and "mktemp" not in script:
        problems.append("root's install without a user does not use a throwaway clone")

if gitconfig is not None:
    with open(prefix + ".gitconfig", "w") as f:
        f.write(gitconfig["content"])
    got = subprocess.run(["git", "config", "-f", prefix + ".gitconfig", "--get", "user.name"],
                         capture_output=True, text=True)
    if got.returncode not in (0, 1):
        problems.append(f"git cannot parse .gitconfig: {got.stderr.strip()}")
    elif got.stdout.rstrip("\n") != expect["git_name"]:
        problems.append(f"user.name read back as {got.stdout.rstrip()!r}, expected {expect['git_name']!r}")

signers_path = next((p for p in files if p.endswith("/.config/git/allowed_signers")), None)
signers = files.get(signers_path)
if (signers is not None) != (expect["signer"] is not None):
    problems.append(f"allowed_signers rendered={signers is not None}, expected {expect['signer'] is not None}")

def gitconfig_get(key):
    return subprocess.run(["git", "config", "-f", prefix + ".gitconfig", "--get", key],
                          capture_output=True, text=True).stdout.rstrip("\n")

if gitconfig is not None:
    want_file = "~/.config/git/allowed_signers" if expect["signer"] is not None else ""
    if (got := gitconfig_get("gpg.ssh.allowedSignersFile")) != want_file:
        problems.append(f"gpg.ssh.allowedSignersFile is {got!r}, expected {want_file!r}")
    if (got := gitconfig_get("gpg.ssh.program")) != expect["ssh_program"]:
        problems.append(f"gpg.ssh.program is {got!r}, expected {expect['ssh_program']!r}")
    # git signs with a literal key only when it starts with key:: or ssh-.
    if expect["signer"] is not None and not gitconfig_get("user.signingkey").startswith(("key::", "ssh-")):
        problems.append(f"user.signingkey {gitconfig_get('user.signingkey')!r} is not a key git reads as literal")
if signers is not None:
    if (signers_path, signers.get("owner"), signers.get("defer")) != \
            ("/home/jdoe/.config/git/allowed_signers", "jdoe:jdoe", True):
        problems.append("allowed_signers is not a deferred file owned by the user in their home")
    if len(signers["content"].splitlines()) != 1:
        problems.append(f"allowed_signers is not one line: {signers['content']!r}")
    with open(prefix + ".allowed_signers", "w") as f:
        f.write(signers["content"])
    # What git does: sign, find the principal for the key, then verify as it.
    signed = subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", "git", "-f", expect["signer_key"]],
                            input=b"commit", capture_output=True)
    with open(prefix + ".sig", "wb") as f:
        f.write(signed.stdout)
    found = subprocess.run(["ssh-keygen", "-Y", "find-principals", "-f", prefix + ".allowed_signers",
                            "-s", prefix + ".sig"], capture_output=True, text=True)
    principal = found.stdout.strip()
    verified = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", prefix + ".allowed_signers", "-I", principal,
                               "-n", "git", "-s", prefix + ".sig"], input="commit", capture_output=True, text=True)
    if signed.returncode != 0:
        problems.append(f"could not sign the test message: {signed.stderr.decode().strip()}")
    elif principal != expect["signer"]:
        problems.append(f"signer found as {principal!r}, expected {expect['signer']!r}: {found.stderr.strip()}")
    elif verified.returncode != 0:
        problems.append(f"signature does not verify: {verified.stderr.strip()}")
    else:
        # A signature carries its namespace, so this needs one made for "file".
        with open(prefix + ".file.sig", "wb") as f:
            f.write(subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", "file", "-f", expect["signer_key"]],
                                   input=b"commit", capture_output=True).stdout)
        if subprocess.run(["ssh-keygen", "-Y", "verify", "-f", prefix + ".allowed_signers", "-I", principal,
                           "-n", "file", "-s", prefix + ".file.sig"], input=b"commit",
                          capture_output=True).returncode == 0:
            problems.append("allowed_signers trusts the key outside the git namespace")

start = files.get("/usr/local/bin/start")
if start is not None:
    with open(prefix + ".start", "w") as f:
        f.write(start["content"])

for p in problems:
    print(f"FAIL: {case}: {p}")
print(f"{'ok  ' if not problems else 'FAIL'} {case}")
sys.exit(1 if problems else 0)
EOF
done < "$work/cases"

# The embedded start script is the same in every render.
if [ -f "$work/full.start" ]; then
    shellcheck -s sh "$work/full.start" || fail "start: shellcheck"
fi

# A concrete Windows profile path means a username has leaked into the repo.
if grep -nE '/mnt/c/Users/[^<*/ ]+/' "$user_data" | grep -v '<you>'; then
    fail "user-data contains a concrete /mnt/c/Users/<name>/ path"
fi

if [ "$failed" = "true" ]; then
    exit 1
fi

printf 'All cases passed.\n'
