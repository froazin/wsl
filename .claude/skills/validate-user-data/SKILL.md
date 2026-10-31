---
name: validate-user-data
description: Build and validate the WSL cloud-init user-data (the parts in src/Ubuntu-26.04.user-data.d/) against mock meta-data. Use after any change to a part in src/Ubuntu-26.04.user-data.d/, to the meta-data example in README.md or to scripts/build/, before saying a change works.
allowed-tools: Bash(uv run invoke validate) Bash(uv run invoke validate *) Bash(uv run invoke build)
---

# Validate the WSL user-data

The parts in `src/Ubuntu-26.04.user-data.d/` only mean something once
cloud-init has rendered and merged them, so running `cloud-init schema` on a
part proves nothing. Run, from the repository root:

```sh
uv run invoke validate              # builds dist/ first
uv run invoke validate --skip-build # checks the dist/ already built
```

It merges `dist/Ubuntu-26.04.user-data` with cloud-init's own part handlers
for each mock meta-data case, as an instance does at boot, then runs
`cloud-init schema` on the merged cloud-config and checks it.
[docs/build.md](../../../docs/build.md#validation) describes each check. The
cases are in `scripts/build/cases.py`:

| Case | Proves |
| ---- | ------ |
| `full` | every key renders; user, `.gitconfig`, `allowed_signers` and GitHub workspace dir appear |
| `empty-values`, `no-meta-data` | nothing user-specific renders, YAML stays valid |
| `hostile-name` | `"`, `\`, `#`, `;`, `'` and `{{ }}` in `git_name` read back exactly through `git config` |
| `legacy-noreply`, `plain-email`, `path-traversal` | the `~/workspaces/github.com/<owner>` extraction only accepts GitHub noreply addresses with a safe owner name |
| `readme-example` | the README's meta-data example, after `<!-- meta-data example -->`, parses and its `vscode_extensions` and `gh_extensions` install |
| `extensions-string` | a comma/space-separated `vscode_extensions` string installs each ID |
| `extensions-hostile` | only `publisher.name` IDs reach the shell; every other entry is reported with `printf`, ASCII-escaped, including non-BMP characters and backslashes |
| `extensions-mapping`, `extensions-number`, `extensions-no-user` | other types install nothing, and nothing installs without a user |
| `gh-extensions-string` | a comma/space-separated `gh_extensions` string installs each one |
| `gh-extensions-hostile` | only `[https://][host/]owner/repo` IDs reach the shell, and a URL needs all three parts; every other entry is reported with `printf`, ASCII-escaped |
| `gh-extensions-mapping`, `gh-extensions-number`, `gh-extensions-no-user` | other `gh_extensions` types install nothing, and nothing installs without a user |
| `signingkey-ecdsa` | a `key::`-prefixed ECDSA key is trusted for `git_email` |
| `signingkey-no-email`, `signingkey-odd-email`, `signingkey-unicode-email` | a whitespace-padded key without `git_email`, or with one unsafe as a principal, is trusted for any identity (`*`), and `user.signingkey` is trimmed so git still reads it as a literal key |
| `signingkey-path`, `signingkey-bare-ecdsa`, `signingkey-hostile`, `signingkey-unknown-type`, `signingkey-bad-type`, `signingkey-unicode-type`, `signingkey-unicode-data`, `signingkey-type-only`, `signingkey-list`, `signingkey-no-user` | only a key git reads as literal (`key::` or `ssh-`) with a valid `<type> <base64>` gets an `allowed_signers` file and `gpg.ssh.allowedSignersFile`, and only with a user; `gpg.ssh.program` is kept without one |

Every case also checks that each part renders on its own as valid YAML, and
that the merged `packages`, `write_files` and `runcmd` are every part's
entries appended in name order, which proves each part's `merge_how`. It
checks one VS Code and one gh extension install per expected ID, run as the
user; that `podman.socket` is enabled with `systemctl --global` before the
first `runuser -l` starts the user's systemd manager, while root gets the
system socket and a `ConditionUser=!root` drop-in instead; and that
cloud-init can write the whole runcmd out as a UTF-8 script. Where an
`allowed_signers` file is expected, it signs a message with a throwaway key
and checks that `ssh-keygen` finds the expected principal and verifies it, as
git does, but not outside the `git` namespace.

After the cases, it shellchecks `/usr/local/bin/start` from the `full` case,
and fails if a concrete `/mnt/c/Users/<name>/` path appears in `src/` or
`dist/`, or a Jinja part in `src/` has a `{%` or `{#` tag away from column 0.

It ends with `All cases passed.` and exit 0. Otherwise each `FAIL:` line
names the case and what broke, and it exits 1. It also exits 1 when a
command it needs (`cloud-init`, `git`, `shellcheck`, `ssh-keygen`), a file
in `dist/` or the README's meta-data example is missing. If `uv run` can't import `cloudinit`, set up the venv
as `CONTRIBUTING.md` describes.

When adding a meta-data key or a new conditional block, add a case for it to
the table in `cases()` in `scripts/build/cases.py`, including the "key unset"
side.

This does not replace a real first boot. Only an end-to-end run on a
throwaway instance (see the README) exercises the WSL datasource, the OOBE and
the package installs, and it writes to the user's Windows profile, so ask
before doing it.
