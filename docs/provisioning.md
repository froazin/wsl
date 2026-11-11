# Provisioning

How the cloud-init fragments in [`src/`](../src/) build a WSL instance from scratch on its first boot, in the order of their numbers. It's for engineers changing the user-data. The meta-data keys have their own doc, [WSL meta-data](meta-data.md), and how the parts are joined is in [Build](build.md).

## Contents

1. [Overview](#overview)
1. [How it works](#how-it-works)
1. [Interfaces](#interfaces)
1. [Errors and logging](#errors-and-logging)
1. [Security and privacy](#security-and-privacy)
1. [Decisions](#decisions)
1. [Validation](#validation)
1. [Limits](#limits)
1. [Sources](#sources)

## Overview

The user puts two files in their Windows profile, as the [README](../README.md#using-it) describes:

| File | From | Copied to | Role |
| --- | --- | --- | --- |
| `Ubuntu.user-data` | Each release, built from every fragment, in order | `%USERPROFILE%\.cloud-init\Ubuntu.user-data` | A MIME multipart file of cloud-config parts. Generic, and the same for every user |
| `Ubuntu.meta-data` | The README's [meta-data example](../README.md#the-meta-data-example) | `%USERPROFILE%\.cloud-init\Ubuntu.meta-data` | The user's identity and choices, which they fill in. See [WSL meta-data](meta-data.md) |

The user-data installs packages, writes system config, bridges Windows tools into Linux, creates the user and runs [`install.sh`](https://github.com/froazin/dotfiles/blob/main/src/install.sh) from the [dotfiles](https://github.com/froazin/dotfiles) for that user and for root. It holds nothing personal: every personal value comes from the meta-data.

The README also offers a `.wslconfig` as an optional example for `%USERPROFILE%\.wslconfig`. Nothing in the user-data needs it, and the [end-to-end tests](releases.md#end-to-end-tests) run without one.

This flowchart shows how the files reach the instance:

```mermaid
flowchart LR
    accTitle: How the WSL files reach the instance
    accDescr: The build joins the fragments, in order, into one MIME user-data, and a release publishes it. The user downloads it into their Windows profile, writes the meta-data beside it from the README's example and can add the optional .wslconfig, which WSL reads. cloud-init's WSL datasource reads the user-data and meta-data, renders each Jinja part, merges the parts and runs the cloud-config, which runs install.sh as the user and as root.
    parts["src/"] -->|"make build"| release["GitHub release"]
    release -->|"user-data, downloaded to .cloud-init"| ds["cloud-init WSL datasource"]
    example["README meta-data example"] -->|"copied to .cloud-init and filled in"| ds
    wslconfig["optional .wslconfig"] -->|"in the Windows profile"| vm["WSL 2 virtual machine"]
    ds -->|"each part, with ds.meta_data"| jinja["Jinja render"]
    jinja -->|"parts merged in order"| modules["cloud-init modules"]
    modules -->|"runuser -l"| install["dotfiles src/install.sh"]
    vm -->|hosts| modules
```

## How it works

### Finding the files

cloud-init's WSL datasource loads one user-data file, picked by instance name first, and only `<Instance>.meta-data`, which must contain `instance-id`. Both files are named for the instance, `Ubuntu`, the default name `wsl --install Ubuntu` gives. An instance of a specific release, such as one from `wsl --install Ubuntu-26.04 --name Ubuntu`, reads them too, because it has the same name. A test instance installed with `--name Test` needs copies named `Test.user-data` and `Test.meta-data`. The datasource merges nothing except Ubuntu Pro's `agent.yaml`.

cloud-init runs once, on first boot, and Ubuntu's out-of-box experience (OOBE), `/usr/lib/wsl/wsl-setup`, waits for it.

### Parts and rendering

The user-data is one part per fragment, and one fragment per feature, such as `40-podman.user-data`, each a cloud-config. This doc calls each fragment by its feature, such as `podman`. cloud-init renders each part that starts with `## template: jinja` on its own, reading the meta-data from `ds.meta_data`, then merges the parts in the order of their numbers. Every part's `merge_how` appends its lists to the earlier parts', so `packages` and `write_files` hold every part's entries and `runcmd` runs in the fragments' order. [Build](build.md#how-the-build-works) covers the parts' rules.

A fragment sets every variable it uses, such as `user`, and normalises and validates the keys it reads, as [WSL meta-data](meta-data.md) describes. `development` and `dotfiles` build paths with the `workspace` macro, which turns a clone URL into `workspaces/<host>/<owner>/<repo>`, so the dotfiles' clone lands in `~/workspaces/github.com/froazin/dotfiles`.

Jinja runs with `trim_blocks` on and `lstrip_blocks` off, so every `{% %}` and `{# #}` tag sits at column 0. An indented tag would leave its indentation behind and break the YAML.

### Stages

cloud-init runs its modules in a fixed order, not in the order the keys appear in the fragments. This flowchart shows the modules the user-data uses, in the order Ubuntu's `/etc/cloud/cloud.cfg` lists them (observed):

```mermaid
flowchart TD
    accTitle: cloud-init modules the user-data uses
    accDescr: The init stage writes the non-deferred files and creates the user. The config stage sets the locale, adds the GitHub CLI apt source and writes the runcmd script. The final stage installs packages, writes the deferred files and runs the runcmd script.
    wf["write_files"] -->|then| users["users_groups"]
    users -->|config stage| locale["locale, apt_configure"]
    locale -->|then| runcmd["runcmd writes its script"]
    runcmd -->|final stage| pkg["package_update_upgrade_install"]
    pkg -->|packages installed| deferred["write_files_deferred"]
    deferred -->|then| scripts["scripts_user runs the runcmd script"]
```

- **Init stage:** `write_files` writes the system files, then `users` creates the user, named by `username` or `wsluser`, with uid 1000, zsh, passwordless sudo and a locked password.
- **Config stage:** `locale` sets `en_GB.UTF-8` and apt adds the GitHub CLI source and its key. The `runcmd` module then writes the commands out as a script.
- **Final stage:** apt updates, upgrades and installs `packages`. The deferred files go into the user's home. The `runcmd` script runs last.

Anything that needs a package, or a group a package creates such as `libvirt`, is in `runcmd` or a deferred file. The files in the user's home are deferred because `write_files` runs before `users_groups` creates the user.

### System files

| Path | Why |
| --- | --- |
| `/etc/wsl.conf` (`wsl`) | Turns on systemd, remounts `/` shared at boot and keeps the Windows `PATH` out (`appendWindowsPath=false`). Has no `[user]` section, because the OOBE writes `default=` |
| `/etc/apt/apt.conf.d/94cloud-init-config` (`base`) | `APT::Install-Recommends "false"`, from the `apt` module's `conf`. It's in place before the packages install, and stays for later installs |
| `/etc/apt/preferences.d/github-cli` (`github-cli`) | Pins `gh` from `cli.github.com` at 600, above the 510 Ubuntu Pro gives ESM |
| `/etc/containers/nodocker` (`podman`) | Stops `podman-docker`'s `docker` wrapper printing its "Emulate Docker CLI using podman" notice |
| `/etc/containers/containers.conf.d/50-compose.conf` (`podman`) | Makes `/usr/bin/podman-compose` the provider for `podman compose`, and `docker compose` through `podman-docker`, and turns off the notice podman prints before running an external provider |
| `/etc/profile.d/browser.sh`, `/etc/environment.d/90-browser.conf` (`windows`) | Set `BROWSER=/usr/local/bin/start` |
| `/etc/systemd/system/disable-swap.service` (`wsl`) | Runs `swapoff -a`, because WSL attaches swap before systemd starts: by default, and even with `swap=0` in `.wslconfig` |
| `/etc/systemd/system/make-root-rshared.service` (`podman`) | Runs `mount --make-rshared /` before `sysinit.target`, backing up the `[boot]` command podman needs |
| `/etc/systemd/user/podman.socket.d/10-not-root.conf` (`podman`) | `ConditionUser=!root`, so root's user manager doesn't start a second rootful podman API |
| `/usr/local/bin/start` (`windows`) | Opens a URL or file with its Windows handler through PowerShell `Start-Process`. Used as `$BROWSER` |

`git` writes two deferred files into the user's home: `~/.gitconfig` and `~/.config/git/allowed_signers`. [WSL meta-data](meta-data.md) says when each is written.

### runcmd

cloud-init writes `runcmd` out as one `#!/bin/sh` script with no `set -e`, so each entry runs whatever the others return. The entries run in the order of the fragments' numbers, and the order still matters. This flowchart shows it, with the fragment each entry comes from:

```mermaid
flowchart TD
    accTitle: runcmd order
    accDescr: runcmd runs the fragments' entries in the order of their numbers. It links the Windows tools and fd, enables the system units and the global podman socket, sets up libvirt and masks the iSCSI units, sets zsh for root, then makes the user's workspaces, installs their tools, Node.js and extensions and runs install.sh for the user and root.
    links["windows, utilities: ln -sfn Windows tools and fd"] -->|then| units["wsl, podman: daemon-reload, enable --now disable-swap, make-root-rshared"]
    units -->|then| global["podman: systemctl --global enable podman.socket, enable --now podman.socket"]
    global -->|then| virsh["virtualisation: virsh net-autostart default, usermod -aG libvirt, mask finalrd and iscsid"]
    virsh -->|then| shells["users: usermod -s for root"]
    shells -->|then| prep["git: mkdir workspaces"]
    prep -->|runuser -l| tools["development: uv, pulumi, biome, nvm, Node.js LTS, claude, ant"]
    tools -->|runuser -l| ext["vscode, github-cli: code --install-extension, gh extension install"]
    ext -->|runuser -l| userinstall["dotfiles: install.sh as the user"]
    userinstall -->|runuser -l root| rootinstall["dotfiles: install.sh as root"]
```

- Ubuntu installs `fd-find`'s command as `fdfind`, because another package owns the name `fd`. `runcmd` links `/usr/local/bin/fd` to `/usr/bin/fdfind`, which apt has installed by then.
- The global `podman.socket` enable, in `podman`, comes before the first `runuser -l`, in `development`. That entry starts the user's systemd manager, which reads global wants only when it starts.
- `virtualisation` masks `finalrd.service` and `iscsid.socket`. They come from `open-iscsi`, which libvirt's iSCSI storage driver brings in only as a recommend, so a fresh instance doesn't have them. The masks keep them off if a later install brings them in: `iscsid.socket` binds an abstract socket that clashes between instances (see [Testing](testing.md#running-beside-another-instance)), and `finalrd` sets up a pivot root for shutdown that a WSL instance doesn't need.
- `development` installs the current Node.js LTS with nvm, under `bash`, and makes `lts/*` nvm's default, for the user only. The dotfiles' zsh loads nvm in interactive shells, which puts `node` and `npm` on `PATH` there.
- Root's `usermod -s` runs only when `/usr/bin/zsh` is executable, so a failed package install can't leave a login shell that doesn't exist. Root's shell is set before root's install, so the zsh module's `$SHELL` check sees zsh and doesn't warn.
- The user's install puts `~/.local/bin` and `~/.pulumi/bin` on `PATH` itself, because `~/.zshenv` doesn't exist yet. Without that, `install.sh` can't find `claude` and skips the claude module.
- Root's install uses the absolute path `/home/<user>/workspaces/...`, because `~` under `runuser -l root` is `/root`.

## Interfaces

- **Windows tools:** `runcmd` links `code`, `op`, `ssh`, `ssh-add` and `clip` from fixed paths under `/mnt/c/` into `/usr/local/bin/`. A link to a missing program is left dangling.
- **The dotfiles:** the user-data clones [`froazin/dotfiles`](https://github.com/froazin/dotfiles) and expects [`src/install.sh`](https://github.com/froazin/dotfiles/blob/main/src/install.sh) at a fixed path in it, and `~/.zshenv` from its [zsh module](https://github.com/froazin/dotfiles/blob/main/docs/zsh/overview.md) to put `~/.local/bin` and `~/.pulumi/bin` on `PATH` later. `~/.zshenv` also exports `BROWSER=/usr/local/bin/start` when that file is executable.
- **Workspaces:** `~/workspaces/<host>/<owner>/<repo>` is the layout the zsh `ws` picker reads. The user-data clones nvm and the dotfiles there.

## Errors and logging

- One bad name in `packages` fails the whole package install. `qemu-kvm` is a virtual package and isn't listed for that reason.
- A failing `runcmd` entry doesn't stop the rest. Each VS Code and gh extension has its own entry for this reason.
- Rejected meta-data values are reported with `printf` lines in `runcmd`, as [WSL meta-data](meta-data.md#reporting-rejected-values) describes. They go to cloud-init's output log (inferred).
- `install.sh` logs as described in the dotfiles' [installer doc](https://github.com/froazin/dotfiles/blob/main/docs/installer.md), and exits non-zero when a module fails.

## Security and privacy

- The repository is public. The fragments hold no personal usernames, emails, signing keys, hostnames or `/mnt/c/Users/<name>/` paths: they come from the user's private meta-data. The only personal account name in them is the dotfiles' repository URL.
- Only validated meta-data values reach shell commands. `username` is the exception: it's trusted as written (see [WSL meta-data](meta-data.md#limits)).
- The GitHub CLI apt key is embedded in `github-cli`, with its fingerprint in a comment, rather than fetched at boot.
- `uv`, `pulumi`, Biome, Claude Code and `ant` are fetched over HTTPS and run as the user, and nvm is cloned over HTTPS and its `install.sh` run as the user, then downloads Node.js from nodejs.org. Their integrity rests on those hosts and TLS.
- `/usr/local/bin/start` passes its target to PowerShell in an environment variable through `WSLENV`, never in the command, so the target is never parsed as code.
- The user named by `username`, or `wsluser`, gets passwordless sudo, and their password is locked.

## Decisions

- **One fragment per feature.** cloud-init's own MIME parts and merging join them, so each feature reads on its own, and a fragment's number places it in the merge. See [Build](build.md#decisions).
- **No recommended packages.** Recommends brought in about 180 packages a headless instance doesn't use, such as a GUI terminal, X11 tools, QEMU's GUI and audio modules, extra libvirt storage drivers and `docker-compose-v2`. The `apt` module's `conf` turns them off for every install, the only way cloud-init offers: `packages` has no per-package option. Each fragment lists the recommends it needs instead, such as `passt`, `aardvark-dns`, `catatonit`, `containers-storage` and `nftables` for rootless podman and podman-compose. The setting stays, so packages installed by hand later come without their recommends too.
- **podman-compose as the compose provider.** It's set in a `containers.conf.d` drop-in rather than left to podman's search, which uses the first compose tool it finds, so installing `docker-compose` later would change it.
- **Native cloud-init modules over custom scripts.** Files, users, apt sources and packages use their modules. `runcmd` holds only what has no module.
- **Installers run as the user** with `runuser -l`, so the tools live in the user's home and update themselves. nvm is cloned and checked out at its newest tag, and `ant` is unpacked with `tar -m` so zsh notices the new binary and regenerates its completion.
- **`systemctl --global` instead of `--user`.** `runcmd` has no user bus. The `ConditionUser=!root` drop-in keeps the global enable out of root's user manager, which `sudo su` starts.
- **Root's shell through `usermod`.** `users:` skips existing users, root included, and would lock root's password.
- **Windows tools by link, not the Windows `PATH`.** With the Windows `PATH` appended, `xdg-open` finds `explorer.exe` and bypasses `$BROWSER`. The links bring in only the five tools listed.
- **`WSL_DISTRO_NAME` from `wslpath`.** VS Code's launcher installs into `~/.vscode-server` only when it's set, and `runuser` clears it. The value only labels the remote.
- **No `power_state` or `package_reboot_if_required`.** They restart the instance in the middle of the OOBE. The [README](../README.md) tells the user to restart it with `wsl --terminate` once cloud-init finishes instead.

## Validation

Nothing checks the merged user-data before a release, as [Build](build.md#validation) says. `make build` only joins the fragments, and `make lint` checks each fragment on its own.

Only a throwaway instance, as [Testing](testing.md) describes, exercises the datasource, the OOBE and the package installs. The [end-to-end tests](releases.md#end-to-end-tests) install one on Windows runners before each release, though without the OOBE.

## Limits

- The README's `.wslconfig` example holds fixed values, such as `processors=12` and `memory=32GB`, and applies to every WSL 2 instance on the machine. Another machine may need different values.
- The user-data runs once. Changing it doesn't change an existing instance.
- cloud-init finishes with a recoverable error, "Failed to wait for network", on every instance. The user-data is a MIME multipart file, not plain cloud-config, so cloud-init waits for the network at the start of its network stage by starting `systemd-networkd-wait-online.service`, which Ubuntu's WSL image masks. `cloud-init status --long` lists it, and nothing else is affected (observed with the earlier single Jinja file; cloud-init's `_should_wait_via_user_data` waits for any user-data that isn't plain cloud-config).
- The Windows tool paths are fixed. A tool installed elsewhere gets a dangling link.
- `ant`'s architecture is chosen only for `x86_64` and `aarch64`.
- WSL instances share one VM, with its cgroup tree, network namespace and `binfmt_misc` table. Two instances built from this config clash over uid 1000's user manager, libvirt's `default` network and other units, and stopping one can break Windows interop in the other. [Testing](testing.md#running-beside-another-instance) lists what was observed and how to recover.
- `node` and `npm` are on `PATH` only in shells that load nvm, such as the dotfiles' interactive zsh. Scripts run with `zsh -c` or `sh` don't get them.

## Sources

- https://cloudinit.readthedocs.io/en/latest/reference/datasources/wsl.html
- https://cloudinit.readthedocs.io/en/latest/explanation/instancedata.html
- https://cloudinit.readthedocs.io/en/latest/reference/modules.html
- https://cloudinit.readthedocs.io/en/latest/reference/merging.html
- https://learn.microsoft.com/en-us/windows/wsl/wsl-config
