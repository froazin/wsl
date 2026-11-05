"""Checks the built user-data: merges each distro's for each case in scripts/build/cases.py as cloud-init does at boot,
then checks what each case's cloud-config holds, and checks src/ and dist/ for mistakes no single case shows.
"""

import email
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, cast

import yaml
from cloudinit import handlers, helpers
from cloudinit.handlers.cloud_config import CloudConfigPartHandler
from cloudinit.handlers.jinja_template import JinjaTemplatePartHandler, render_jinja_payload
from cloudinit.settings import PER_INSTANCE
from cloudinit.user_data import UserDataProcessor
from cloudinit.util import shellify

from scripts.build.build import part_type
from scripts.build.cases import Case, cases, instance_data
from scripts.build.config import (
    DIST_FOLDER,
    JINJA_HEADER,
    JINJA_PART_TYPE,
    MANIFEST_FILE,
    MANIFEST_SCHEMA,
    META_DATA_EXAMPLE_MARKER,
    META_DATA_FILLED_KEYS,
    README_FILE,
    SRC_FOLDER,
    USER_DATA_SUFFIX,
)
from scripts.build.errors import BuildError
from scripts.build.manifest import Distro, load_distros, shared_fragments

REQUIRED_COMMANDS = ("cloud-init", "git", "shellcheck", "ssh-keygen")
MERGED_LISTS = ("packages", "write_files", "runcmd")
LEAKED_PATH = re.compile(r"/mnt/c/Users/[^<*/ ]+/")
"""A concrete Windows profile path, which means a username has leaked into the repository."""

type Doc = dict[str, Any]


def validate(
    src: str = SRC_FOLDER, dist: str = DIST_FOLDER, readme: str = README_FILE, schema: str = MANIFEST_SCHEMA
) -> None:
    """Checks each distro's user-data in dist/ against every case, and src/ and dist/ as a whole. Prints
    `ok   <distro>: <case>` or `FAIL: ...` lines.

    One case renders with the meta-data example in readme. Raises a BuildError when a check fails, or when a command or
    file the checks need is missing.
    """

    missing = [command for command in REQUIRED_COMMANDS if shutil.which(command) is None]
    if missing:
        raise BuildError(f"Missing required commands: {', '.join(missing)}.")
    distros = load_distros(src, schema)
    user_data = {distro.name: read_user_data(dist, distro) for distro in distros}
    example = meta_data_example(readme)

    failed = False
    with TemporaryDirectory() as work:
        keys = os.path.join(work, "keys")
        os.makedirs(keys)
        signer, ecdsa = keygen(keys, "signer", "-t", "ed25519"), keygen(keys, "ecdsa", "-t", "ecdsa", "-b", "256")
        for distro in distros:
            prefix = os.path.join(work, "distros", distro.name)
            os.makedirs(prefix)
            start = None
            for case in cases(keys, signer, ecdsa, example):
                doc, problems = check_case(case, user_data[distro.name], distro, os.path.join(prefix, case.name))
                for problem in problems:
                    print(f"FAIL: {distro.name}: {case.name}: {problem}")
                print(f"{'ok  ' if not problems else 'FAIL'} {distro.name}: {case.name}")
                failed = failed or bool(problems)
                if case.name == "full":
                    start = write_files(doc).get("/usr/local/bin/start")
            # The start script is the same in every case.
            if start is None or not shellcheck(start["content"], os.path.join(prefix, "start")):
                print(f"FAIL: {distro.name}: start: shellcheck")
                failed = True

    for problem in source_problems(src, dist, distros, readme):
        print(f"FAIL: {problem}")
        failed = True
    if failed:
        sys.stdout.flush()  # So the FAIL lines come before the error, which goes to stderr.
        raise BuildError("The user-data failed validation. See the FAIL lines above.")
    print("All cases passed.")


def read_user_data(dist: str, distro: Distro) -> bytes:
    """Returns the distro's built user-data, raising a BuildError when it isn't in dist."""

    path = os.path.join(dist, distro.name + USER_DATA_SUFFIX)
    if not os.path.isfile(path):
        raise BuildError(f"{path} not found. Run `invoke build` first.")
    with open(path, "rb") as f:
        return f.read()


def meta_data_example(readme: str) -> dict[str, Any]:
    """Returns the meta-data example in readme: the yaml code block straight after META_DATA_EXAMPLE_MARKER.

    Raises a BuildError when readme has no such block, the block isn't a YAML mapping, or it doesn't leave each of
    META_DATA_FILLED_KEYS empty on a line of its own, as seed-cloud-init.ps1 needs to fill it in.
    """

    with open(readme) as f:
        text = f.read()
    found = re.search(rf"^{re.escape(META_DATA_EXAMPLE_MARKER)}\n+```yaml\n(.*?)^```$", text, re.MULTILINE | re.DOTALL)
    if not found:
        raise BuildError(f"{readme} has no yaml code block straight after {META_DATA_EXAMPLE_MARKER}.")
    try:
        example = yaml.safe_load(found.group(1))
    except yaml.YAMLError as error:
        raise BuildError(f"The meta-data example in {readme} is not valid YAML: {error}") from error
    if not isinstance(example, dict):
        raise BuildError(f"The meta-data example in {readme} is not a YAML mapping.")
    for key in META_DATA_FILLED_KEYS:
        # The same pattern seed-cloud-init.ps1 fills in.
        if not re.search(rf"^{re.escape(key)}:[ \t]*$", found.group(1), re.MULTILINE):
            raise BuildError(
                f"The meta-data example in {readme} has no empty {key}: line, which the end-to-end tests fill in."
            )
    return cast(dict[str, Any], example)


def keygen(work: str, name: str, *options: str) -> str:
    """Makes a throwaway SSH key pair work/name, and returns its public key.

    The keys are real, so ssh-keygen itself checks the allowed_signers a case renders.
    """

    path = os.path.join(work, name)
    subprocess.run(["ssh-keygen", "-q", *options, "-N", "", "-C", "jane", "-f", path], check=True)
    with open(f"{path}.pub") as f:
        return f.read().strip()


def merge(user_data: bytes, instance: Doc) -> str:
    """Returns the cloud-config cloud-init merges from a MIME user-data at boot, with this instance-data.

    It runs cloud-init's own part handlers, so each Jinja part is rendered on its own and the parts are merged in order
    with their merge_how, as on an instance.
    """

    with TemporaryDirectory() as tmp:
        # The handlers write under the datasource's instance ID, as at boot.
        datasource = SimpleNamespace(get_instance_id=lambda: instance["ds"]["meta_data"]["instance-id"])
        paths = helpers.Paths({"cloud_dir": tmp, "run_dir": tmp}, ds=datasource)
        with open(paths.get_runpath("instance_data_sensitive"), "w") as f:
            json.dump(instance, f)
        cloud_config = CloudConfigPartHandler(paths)
        part_handlers = [cloud_config, JinjaTemplatePartHandler(paths, sub_handlers=[cloud_config])]
        registry = helpers.ContentHandlers()
        for handler in part_handlers:
            registry.register(handler, overwrite=False)
        data = {
            "handlers": registry,
            "handlerdir": tmp,
            "data": {},
            "frequency": PER_INSTANCE,
            "handlercount": 0,
            "excluded": [],
        }
        for handler in part_handlers:
            handlers.call_begin(handler, data["data"], PER_INSTANCE)
        handlers.walk(UserDataProcessor(paths).process(user_data), handlers.walker_callback, data)
        for handler in part_handlers:
            handlers.call_end(handler, data["data"], PER_INSTANCE)
        with open(cloud_config.cloud_fn) as f:
            return f.read()


def render_fragments(distro: Distro, instance: Doc) -> tuple[dict[str, Doc], list[str]]:
    """Renders each of the distro's fragments on its own, and returns them by name in name order, with any problems.

    A Jinja fragment goes through the same renderer cloud-init's Jinja part handler uses. Any other is plain YAML.
    """

    parts, problems = {}, []
    for path, name in zip(distro.fragments, distro.fragment_names(), strict=True):
        with open(path) as f:
            text = f.read()
        if part_type(path) == JINJA_PART_TYPE:
            try:
                text = render_jinja_payload(text, name, instance)
            except Exception as error:  # Any template error is the fragment's problem, so it's reported, not raised.
                problems.append(f"fragment {name} does not render: {error}")
                continue
            if text is None:
                problems.append(f"fragment {name} does not render")
                continue
        try:
            parts[name] = yaml.safe_load(text) or {}
        except yaml.YAMLError as error:
            problems.append(f"fragment {name} is not valid YAML: {str(error).splitlines()[0]}")
    return parts, problems


def check_case(case: Case, user_data: bytes, distro: Distro, prefix: str) -> tuple[Doc, list[str]]:
    """Merges the user-data for a case, then returns the merged cloud-config and the problems found in it.

    Files the checks hand to other commands are written next to prefix.
    """

    instance = instance_data(case.meta_data)
    text = merge(user_data, instance)
    with open(f"{prefix}.yaml", "w") as f:
        f.write(text)
    problems = []
    if "CI_MISSING_JINJA_VAR" in text:
        problems.append("rendered output references an undefined Jinja variable")
    schema = subprocess.run(["cloud-init", "schema", "-c", f"{prefix}.yaml"], capture_output=True, text=True)
    if schema.returncode != 0:
        lines = [
            line for line in (schema.stdout + schema.stderr).splitlines() if not re.search("obj.pkl|datasource", line)
        ]
        problems.append(f"schema: {'\n'.join(lines[:3])}")
    if not text.startswith("#cloud-config"):
        problems.append("rendered output does not start with #cloud-config")

    doc = yaml.safe_load(text) or {}
    parts, render_problems = render_fragments(distro, instance)
    problems += render_problems
    problems += merge_problems(text, doc, parts)
    problems += expectation_problems(doc, case.expect)
    problems += git_problems(doc, case.expect, prefix)
    return doc, problems


def merge_problems(text: str, doc: Doc, parts: dict[str, Doc]) -> list[str]:
    """Checks that every part was merged, and that each list holds every part's entries appended in name order.

    A part whose merge_how doesn't append would replace the earlier parts' lists instead.
    """

    # cloud-init lists the parts it merged in a comment: "# from <count> files", then "# <name>" for each.
    names = []
    if merged_from := re.search(r"^# from (\d+) files\n((?:# .*\n)*)", text, re.MULTILINE):
        names = [line.removeprefix("# ") for line in merged_from.group(2).splitlines()][: int(merged_from.group(1))]
    problems = [] if names == list(parts) else [f"merged parts {names}, expected {list(parts)}"]
    for key in MERGED_LISTS:
        want = [entry for part in parts.values() for entry in part.get(key) or []]
        got = doc.get(key) or []
        if got != want:
            at = next((i for i, (g, w) in enumerate(zip(got, want, strict=False)) if g != w), min(len(got), len(want)))
            problems.append(
                f"{key} is not every part's {key} appended in name order: {len(got)} entries, expected {len(want)},"
                f" first difference at entry {at}"
            )
    return problems


def write_files(doc: Doc) -> dict[str, Doc]:
    """Returns the merged write_files by path."""

    return {f["path"]: f for f in doc.get("write_files", [])}


def commands(doc: Doc) -> list[list[Any]]:
    """Returns the merged runcmd, each entry as a list."""

    return [c if isinstance(c, list) else [c] for c in doc.get("runcmd", [])]


def first(cmds: list[list[Any]], match: Callable[[list[Any]], bool]) -> int | None:
    """Returns the index of the first command that matches, or None."""

    return next((i for i, c in enumerate(cmds) if match(c)), None)


def expectation_problems(doc: Doc, expect: Doc) -> list[str]:
    """Checks a merged cloud-config against a case's expectations, without running any command."""

    cmds = commands(doc)
    return [
        *user_problems(doc, expect),
        *workspace_problems(cmds, expect),
        *extension_problems(cmds, expect),
        *podman_problems(doc),
        *root_install_problems(cmds, expect),
    ]


def user_problems(doc: Doc, expect: Doc) -> list[str]:
    """Checks the user and their .gitconfig render only when the case has a user."""

    problems = []
    has_user = "users" in doc
    gitconfig = gitconfig_file(doc)
    if has_user != expect["user"]:
        problems.append(f"users rendered={has_user}, expected {expect['user']}")
    elif has_user and [u.get("name") for u in doc["users"]] != [expect["username"]]:
        problems.append(f"users {doc['users']!r}, expected only {expect['username']!r}")
    if (gitconfig is not None) != expect["user"]:
        problems.append(f".gitconfig rendered={gitconfig is not None}, expected {expect['user']}")
    return problems


def workspace_problems(cmds: list[list[Any]], expect: Doc) -> list[str]:
    """Checks runcmd makes the ~/workspaces/github.com/<owner> directory the case expects, and no other."""

    want = expect["gh_dir"]
    mkdirs = [a for c in cmds for a in map(str, c) if a.startswith("/home/") and "/workspaces/github.com/" in a]
    if want and not any(d.endswith(f"/workspaces/github.com/{want}") for d in mkdirs):
        return [f"expected workspace dir github.com/{want}, got {mkdirs}"]
    if not want and mkdirs:
        return [f"unexpected workspace dirs {mkdirs}"]
    return []


def extension_problems(cmds: list[list[Any]], expect: Doc) -> list[str]:
    """Checks the VS Code and gh extensions installed as the user, in order, and the entries reported as skipped."""

    problems = []
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
    return problems


def podman_problems(doc: Doc) -> list[str]:
    """Checks podman.socket is enabled for users before any user's systemd manager starts, and for root, and that
    runcmd can be written as a script.
    """

    problems = []
    cmds = commands(doc)
    # The first `runuser -l` starts the user's systemd manager, which only reads global wants when it starts.
    podman = first(cmds, lambda c: c == ["systemctl", "--global", "enable", "podman.socket"])
    first_login = first(cmds, lambda c: c[:2] == ["runuser", "-l"])
    if podman is None:
        problems.append("runcmd does not enable podman.socket for users")
    elif first_login is not None and first_login < podman:
        problems.append("podman.socket is enabled after the first runuser -l starts the user's manager")
    if ["systemctl", "enable", "--now", "podman.socket"] not in cmds:
        problems.append("runcmd does not enable the system podman.socket for root")
    not_root = write_files(doc).get("/etc/systemd/user/podman.socket.d/10-not-root.conf", {})
    if "ConditionUser=!root" not in not_root.get("content", "").splitlines():
        problems.append("root's user manager is not kept from starting the user podman.socket")

    # cc_runcmd writes the whole script as UTF-8; one unencodable item fails all of it.
    try:
        shellify(doc.get("runcmd", [])).encode("utf-8")
    except Exception as e:
        problems.append(f"runcmd cannot be written as a script: {e}")
    return problems


def root_install_problems(cmds: list[list[Any]], expect: Doc) -> list[str]:
    """Checks root gets zsh as its login shell, then the dotfiles, after the user's clone when there is a user."""

    problems = []
    root_shell = first(cmds, lambda c: "usermod -s /usr/bin/zsh root" in " ".join(map(str, c)))
    root_install = first(cmds, lambda c: c[:3] == ["runuser", "-l", "root"])
    user_install = first(
        cmds, lambda c: c[:2] == ["runuser", "-l"] and c[2] != "root" and "src/install.sh" in str(c[-1])
    )
    if root_shell is None:
        problems.append("runcmd does not set root's login shell")
    if root_install is None:
        problems.append("runcmd does not install the dotfiles for root")
        return problems
    script = str(cmds[root_install][-1])
    if root_shell is not None and root_install < root_shell:
        problems.append("root's dotfiles install runs before its login shell is set")
    if "~" in script:
        problems.append("root's install path uses ~, which runuser -l expands to /root")
    if expect["user"] and (user_install is None or root_install < user_install):
        problems.append("root's install does not follow the user's clone")
    if not expect["user"] and "mktemp" not in script:
        problems.append("root's install without a user does not use a throwaway clone")
    return problems


def gitconfig_file(doc: Doc) -> Doc | None:
    """Returns the merged write_files entry for the user's .gitconfig, or None."""

    return next((f for p, f in write_files(doc).items() if p.endswith("/.gitconfig")), None)


def git_problems(doc: Doc, expect: Doc, prefix: str) -> list[str]:
    """Checks what git reads back from the rendered .gitconfig, and that the allowed_signers file works with ssh-keygen
    as git uses it.
    """

    files = write_files(doc)
    gitconfig = gitconfig_file(doc)
    signers_path = next((p for p in files if p.endswith("/.config/git/allowed_signers")), None)
    signers = files.get(signers_path) if signers_path else None
    problems = []
    if gitconfig is not None:
        problems += gitconfig_problems(gitconfig["content"], expect, f"{prefix}.gitconfig")
    if (signers is not None) != (expect["signer"] is not None):
        problems.append(f"allowed_signers rendered={signers is not None}, expected {expect['signer'] is not None}")
    if signers is not None:
        if (signers_path, signers.get("owner"), signers.get("defer")) != (
            "/home/jdoe/.config/git/allowed_signers",
            "jdoe:jdoe",
            True,
        ):
            problems.append("allowed_signers is not a deferred file owned by the user in their home")
        if len(signers["content"].splitlines()) != 1:
            problems.append(f"allowed_signers is not one line: {signers['content']!r}")
        problems += signer_problems(signers["content"], expect, prefix)
    return problems


def gitconfig_problems(content: str, expect: Doc, path: str) -> list[str]:
    """Checks git parses the .gitconfig and reads back the values the case expects."""

    with open(path, "w") as f:
        f.write(content)

    def get(key: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "config", "-f", path, "--get", key], capture_output=True, text=True)

    problems = []
    name = get("user.name")
    if name.returncode not in (0, 1):
        problems.append(f"git cannot parse .gitconfig: {name.stderr.strip()}")
    elif name.stdout.rstrip("\n") != expect["git_name"]:
        problems.append(f"user.name read back as {name.stdout.rstrip()!r}, expected {expect['git_name']!r}")

    want_file = "~/.config/git/allowed_signers" if expect["signer"] is not None else ""
    if (got := get("gpg.ssh.allowedSignersFile").stdout.rstrip("\n")) != want_file:
        problems.append(f"gpg.ssh.allowedSignersFile is {got!r}, expected {want_file!r}")
    if (got := get("gpg.ssh.program").stdout.rstrip("\n")) != expect["ssh_program"]:
        problems.append(f"gpg.ssh.program is {got!r}, expected {expect['ssh_program']!r}")
    # git signs with a literal key only when it starts with key:: or ssh-.
    signingkey = get("user.signingkey").stdout.rstrip("\n")
    if expect["signer"] is not None and not signingkey.startswith(("key::", "ssh-")):
        problems.append(f"user.signingkey {signingkey!r} is not a key git reads as literal")
    return problems


def signer_problems(content: str, expect: Doc, prefix: str) -> list[str]:
    """Does what git does with allowed_signers: signs, finds the principal for the key, then verifies as it.

    Also checks the key isn't trusted outside the git namespace.
    """

    signers, sig = f"{prefix}.allowed_signers", f"{prefix}.sig"
    with open(signers, "w") as f:
        f.write(content)
    signed = sign(expect["signer_key"], "git", sig)
    found = subprocess.run(
        ["ssh-keygen", "-Y", "find-principals", "-f", signers, "-s", sig], capture_output=True, text=True
    )
    principal = found.stdout.strip()
    verified = verify(signers, principal, "git", sig)
    if signed.returncode != 0:
        return [f"could not sign the test message: {signed.stderr.decode().strip()}"]
    if principal != expect["signer"]:
        return [f"signer found as {principal!r}, expected {expect['signer']!r}: {found.stderr.strip()}"]
    if verified.returncode != 0:
        return [f"signature does not verify: {verified.stderr.decode().strip()}"]
    # A signature carries its namespace, so this needs one made for "file".
    sign(expect["signer_key"], "file", f"{prefix}.file.sig")
    if verify(signers, principal, "file", f"{prefix}.file.sig").returncode == 0:
        return ["allowed_signers trusts the key outside the git namespace"]
    return []


def sign(key: str, namespace: str, sig: str) -> subprocess.CompletedProcess[bytes]:
    """Signs the test message with key in namespace, writing the signature to sig."""

    command = ["ssh-keygen", "-q", "-Y", "sign", "-n", namespace, "-f", key]
    signed = subprocess.run(command, input=b"commit", capture_output=True)
    with open(sig, "wb") as f:
        f.write(signed.stdout)
    return signed


def verify(signers: str, principal: str, namespace: str, sig: str) -> subprocess.CompletedProcess[bytes]:
    """Verifies the signature sig of the test message as principal in namespace."""

    command = ["ssh-keygen", "-Y", "verify", "-f", signers, "-I", principal, "-n", namespace, "-s", sig]
    return subprocess.run(command, input=b"commit", capture_output=True)


def shellcheck(script: str, path: str) -> bool:
    """Writes script to path, and returns whether ShellCheck passes it as POSIX sh. ShellCheck prints what it finds."""

    with open(path, "w") as f:
        f.write(script)
    return subprocess.run(["shellcheck", "-s", "sh", path]).returncode == 0


def source_problems(src: str, dist: str, distros: list[Distro], readme: str) -> list[str]:
    """Checks every file in src/ and dist/, and readme with its meta-data example, for a leaked Windows profile path,
    every Jinja fragment in src/ for a tag away from column 0, and that every shared fragment is in a distro's manifest.
    """

    listed = {path for distro in distros for path in distro.fragments}
    problems = [
        f"{path} isn't listed in any distro's {MANIFEST_FILE}" for path in shared_fragments(src) if path not in listed
    ]
    with open(readme) as f:
        readme_text = [(readme, f.read())]
    for label, text in texts(src) + texts(dist) + readme_text:
        problems += [f"{label} contains a concrete /mnt/c/Users/<name>/ path: {line}" for line in leaked_paths(text)]
    for label, text in texts(src):
        if text.startswith(JINJA_HEADER + "\n"):
            problems += [f"{label}:{n}: a Jinja tag is not at column 0" for n in indented_tags(text)]
    return problems


def texts(folder: str) -> list[tuple[str, str]]:
    """Returns the text of every file in folder by path. A MIME multipart file gives each part's decoded text instead,
    labelled <path>:<part name>, since make-mime base64-encodes them.
    """

    result = []
    for root, _, names in sorted(os.walk(folder)):
        for path in (os.path.join(root, name) for name in sorted(names)):
            with open(path, "rb") as f:
                content = f.read()
            message = email.message_from_bytes(content)
            if not message.is_multipart():
                result.append((path, content.decode()))
                continue
            for part in message.walk():
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    result.append((f"{path}:{part.get_filename()}", payload.decode()))
    return result


def leaked_paths(text: str) -> list[str]:
    """Returns the lines with a concrete /mnt/c/Users/<name>/ path. A <you> placeholder doesn't count."""

    return [line for line in text.splitlines() if LEAKED_PATH.search(line) and "<you>" not in line]


def indented_tags(text: str) -> list[int]:
    """Returns the line numbers of Jinja block tags and comments that start a line but not at column 0.

    cloud-init renders Jinja with trim_blocks but not lstrip_blocks, so the indent before such a tag stays in the
    output.
    """

    return [
        n
        for n, line in enumerate(text.splitlines(), 1)
        if line.lstrip().startswith(("{%", "{#")) and not line.startswith(("{%", "{#"))
    ]
