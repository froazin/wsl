# Build and validation

How `tasks.py` and the Python packages in [`scripts/`](../scripts/) build the cloud-init fragments in [`src/`](../src/) into the files users download, and how the build is checked. It's for engineers changing a fragment, a task or the tooling. How each distro's manifest picks its fragments is in [Distros and manifests](distros.md), the commands to run are in [CONTRIBUTING.md](../CONTRIBUTING.md#checks), and what the user-data does on an instance is in [Provisioning](provisioning.md).

## Contents

1. [Overview](#overview)
1. [The source layout](#the-source-layout)
1. [How the build works](#how-the-build-works)
1. [Validation](#validation)
1. [Errors](#errors)
1. [Unit tests](#unit-tests)
1. [Tool configuration](#tool-configuration)
1. [Decisions](#decisions)
1. [Limits](#limits)
1. [Sources](#sources)

## Overview

The tooling has two layers:

- **Tasks:** [`tasks.py`](../tasks.py) defines the Invoke tasks `build`, `validate` and `version`. Each is a thin wrapper that calls a package in `scripts/` and turns its error into an exit status.
- **Logic:** [`scripts/build/`](../scripts/build/) builds and validates the config, and [`scripts/release/`](../scripts/release/) works out the next release's version, as [Releases](releases.md) describes. Neither imports Invoke.

This flowchart shows what each task calls, and the files and tools it uses:

```mermaid
flowchart LR
    accTitle: How the tasks build and check the config
    accDescr: The invoke CLI runs a task in tasks.py. The build task calls scripts.build.build, which loads each distro's manifest from src/ with scripts.build.manifest, joins its fragments with cloud-init devel make-mime and writes dist/. The validate task builds first, then calls scripts.build.validation, which takes the cases from scripts.build.cases and the meta-data example from README.md, merges each distro's user-data with cloud-init's part handlers, renders each fragment on its own and runs cloud-init schema, git, ssh-keygen and ShellCheck. The version task calls scripts.release.
    cli["invoke CLI"] -->|"task and flags"| tasks["tasks.py"]
    tasks -->|"build, and validate unless --skip-build"| build["scripts.build.build"]
    tasks -->|validate| validation["scripts.build.validation"]
    tasks -->|version| release["scripts.release"]
    src[("src/")] -->|"manifests and fragments"| manifest["scripts.build.manifest"]
    manifest -->|"each distro's fragments"| build
    manifest -->|"each distro's fragments"| validation
    build -->|"each distro, from a temporary folder"| mime["cloud-init devel make-mime"]
    mime -->|"one MIME user-data per distro"| dist[("dist/")]
    cases["scripts.build.cases"] -->|"32 cases"| validation
    readme["README.md"] -->|"the meta-data example"| validation
    dist -->|"merged with cloud-init's part handlers"| validation
    validation -->|"merged cloud-config"| tools["cloud-init schema, git, ssh-keygen, ShellCheck"]
    dist -->|"compared with the latest release"| release
```

## The source layout

```text
src/
├── fragments/
│   ├── 00-base.user-data            merge_how, locale, apt update and upgrade
│   ├── 10-windows.user-data         Windows tool links, $BROWSER and the start script
│   ├── ...
│   └── 99-dotfiles.user-data        the dotfiles installs, for the user and root
└── distros/
    └── Ubuntu-26.04/
        └── manifest.json            the fragments in dist/Ubuntu-26.04.user-data
```

- Each fragment is a cloud-config named `NN-<feature>.user-data`. The number sets its place in the merge, and so the order of `runcmd`. Each becomes one part of a distro's MIME user-data.
- `src/fragments/` holds the shared fragments, and a distro's folder holds its `manifest.json` and any fragments only it uses. [Distros and manifests](distros.md) says which goes where.
- A fragment that reads meta-data starts with `## template: jinja` on its first line, then `#cloud-config`.
- Every fragment keeps the same `merge_how`: `list(append)` and `dict(no_replace, recurse_list)`. [How the build works](#how-the-build-works) says why.
- Edit `src/`, never `dist/`. `dist/` is ignored by Git, and every build empties it.

## How the build works

`invoke build` calls `build()` in [`build.py`](../scripts/build/build.py). It fails if `src/` holds anything but `fragments/` and `distros/`, and loads every distro's manifest, as [Finding the fragments](distros.md#finding-the-fragments) describes. Then it empties `dist/`, and for each distro, in name order:

1. Copies the fragments its manifest lists into a temporary folder. make-mime names each part by the path it's given, so attaching them from one folder names each part by its file name, wherever the fragment came from.
1. Runs `cloud-init devel make-mime` there, attaching each fragment in name order. A fragment is `jinja2` when its first line is `## template: jinja`, and `cloud-config` otherwise.
1. Writes the result to `dist/<distro>.user-data`.

Nothing else is built: users write the meta-data from the README's example. What follows from the fragments being separate parts:

- **One file for WSL.** cloud-init's WSL datasource reads exactly one user-data file, so it can't read a folder of parts. A MIME multipart file holds them all, and cloud-init splits it at boot.
- **Part order and `merge_how`.** cloud-init merges the parts in the order they appear in the MIME file, which is name order. Without a `merge_how` that appends, a fragment's `packages`, `write_files` or `runcmd` would replace the earlier fragments' lists. Keep order-dependent entries in the right fragment: the global `podman.socket` enable is in `40-podman`, before the first `runuser -l` in `90-development`, as [Provisioning](provisioning.md#runcmd) explains. A distro's own fragments merge in the same order.
- **Jinja per part.** cloud-init renders each Jinja part on its own, with the instance's meta-data, before it merges them. A fragment can't see another fragment's variables or macros, so each sets every variable it uses, such as `user`, and `90-development` and `99-dotfiles` each define the `workspace` macro.
- **Base64 parts.** make-mime base64-encodes each part, so the built user-data isn't readable as text. Read the fragments in `src/` instead.
- **A random boundary.** make-mime picks a new MIME boundary each time, so two builds of the same parts differ byte for byte. The release workflow compares the parts, not the bytes (see [Releases](releases.md#how-the-version-is-decided)).

## Validation

`invoke validate` builds `dist/` first, unless `--skip-build` is given, then calls `validate()` in [`validation.py`](../scripts/build/validation.py). It needs `cloud-init`, `git`, `shellcheck` and `ssh-keygen`, and makes throwaway ed25519 and ECDSA keys for the signing cases.

For each distro, and each case in [`cases.py`](../scripts/build/cases.py), it:

1. Merges `dist/<distro>.user-data` with cloud-init's own part handlers (`UserDataProcessor`, `CloudConfigPartHandler` and `JinjaTemplatePartHandler`), with the case's meta-data as instance-data. That's what cloud-init does at boot. `cloud-init devel render` can't read a MIME file.
1. Checks the merged cloud-config: no undefined Jinja variable, `cloud-init schema -c` passes and it starts with `#cloud-config`.
1. Renders each of the distro's fragments on its own, and checks it renders and is valid YAML. Then it checks the merged config lists every fragment as a part, and that its `packages`, `write_files` and `runcmd` are every fragment's entries appended in name order. A fragment that lost its `merge_how` fails here.
1. Checks the case's expectations: the user, the workspace directory, the extensions installed and skipped, the `podman.socket` order, root's dotfiles install and that `runcmd` can be written as UTF-8.
1. Checks what git reads back from `.gitconfig`, and that `allowed_signers` works with `ssh-keygen` as git uses it.

The `readme-example` case renders with the README's [meta-data example](../README.md#the-meta-data-example), plus a username. `meta_data_example()` finds it as the `yaml` code block straight after the `<!-- meta-data example -->` comment, and raises a `BuildError` when there's no such block, it isn't a YAML mapping or it doesn't leave `username`, `git_name` and `git_email` empty on lines of their own, as `seed-cloud-init.ps1` needs to fill them in.

After each distro's cases, it runs ShellCheck on `/usr/local/bin/start` from its `full` case. Then it checks that every file in `src/fragments/` is in a distro's manifest, every file in `src/` and `dist/`, with the MIME parts decoded, and `README.md`, with its meta-data example, for a concrete `/mnt/c/Users/<name>/` path, and every Jinja fragment in `src/` for a `{%` or `{#` tag that starts a line away from column 0.

It prints `ok   <distro>: <case>` or `FAIL <distro>: <case>` for each case, after a `FAIL: <distro>: <case>: <problem>` line for each problem. It ends with `All cases passed.`, or raises a `BuildError`. The cases and what each proves are in the [validate-user-data skill](../.claude/skills/validate-user-data/SKILL.md). Add a case for every new meta-data key or conditional, including the key being unset.

## Errors

- `scripts.build` raises [`BuildError`](../scripts/build/errors.py), and `scripts.release` raises [`ReleaseError`](../scripts/release/errors.py), for a failure the user can fix. `tasks.py` turns each into an `Exit` with status 1, so Invoke prints the message without a traceback.
- `BuildError` covers a manifest or fragment that's wrong, as [Finding the fragments](distros.md#finding-the-fragments) lists, an entry in `src/` other than `fragments/` and `distros/`, a missing command, a missing user-data in `dist/`, a missing or broken meta-data example in the README and a failed validation.
- A failed `make-mime` raises Invoke's `UnexpectedExit` from `c.run`, which Invoke reports without a traceback (inferred).
- Any other exception is a bug, and keeps its traceback.
- cloud-init's own warnings for a part that fails, such as "Failed loading yaml blob", go to standard error beside the `FAIL:` lines.

## Unit tests

- Tests live in `scripts/<package>/test/`, without an `__init__.py`. `testpaths = ["scripts"]`, so pytest collects only those. `tasks.py` has no tests: it holds no logic.
- `norecursedirs` is pytest's default list without `build`, which would otherwise skip `scripts/build/`.
- `--import-mode=importlib` imports each test file by path, so test files in different packages can share a name.
- The build and validation tests run no external commands. The version tests build test dists with the real `make-mime`, and one runs semantic-release with a bad option.

## Tool configuration

- **Python:** the system Python 3.14. [`pyproject.toml`](../pyproject.toml) sets `python-preference = "only-system"` and `python-downloads = "never"`, so uv never fetches its own Python. `package = false`: nothing is installed, and Invoke and pytest find `scripts` from the repository root.
- **System site packages:** create `.venv` with `uv venv --system-site-packages`. The validation imports `cloudinit` and `yaml` from apt's `cloud-init` and `python3-yaml`, so it uses the same cloud-init as Ubuntu 26.04.
- **Pyright:** [`pyrightconfig.json`](../pyrightconfig.json) sets `standard` mode for Python 3.14, and names no venv. Under `uv run`, Pyright uses the venv's Python with its system site packages. With `venvPath` set it couldn't import `cloudinit` (observed).
- **Ruff:** `[tool.ruff]` in `pyproject.toml`, with a 120-character line.
- **Dependencies:** every Python dependency is in the `dev` group. `exclude-newer = "7 days"` resolves only versions at least 7 days old. `uv.lock` is ignored by Git.
- **Shell:** shfmt reads its options from [`.editorconfig`](../.editorconfig).

## Decisions

- **Real cloud-init parts, joined by cloud-init.** Each fragment is a cloud-config that cloud-init itself merges, rather than a template a custom builder fills in. `make-mime` is cloud-init's own tool for this. The manifests only choose which fragments to join.
- **Validate the merge as cloud-init does it.** The validation calls cloud-init's part handlers rather than merging the YAML itself, so it can't disagree with an instance about the result.
- **Thin tasks.** The logic is in `scripts/`, where it can be tested without Invoke.

## Limits

- A fragment can't share a variable or macro with another, so shared code, such as `user` and `workspace`, is repeated.
- The validation doesn't prove a real first boot. The end-to-end tests in [Releases](releases.md#end-to-end-tests) install an instance on Windows runners.
- Each case runs cloud-init's merge and `cloud-init schema` for every distro, so `invoke validate` takes longer with each distro added: about 10 seconds for one (observed).

## Sources

- https://cloudinit.readthedocs.io/en/latest/explanation/format.html
- https://cloudinit.readthedocs.io/en/latest/reference/merging.html
- https://cloudinit.readthedocs.io/en/latest/reference/datasources/wsl.html
