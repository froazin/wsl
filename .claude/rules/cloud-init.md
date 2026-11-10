---
paths:
  - "src/**"
---

# WSL cloud-init (`src/`)

The user-data is written as cloud-config fragments in `fragments/`, named
`<NN>-<feature>.user-data`. `make build` joins every fragment, in the order
of their numbers, with `cloud-init devel make-mime` into
`dist/Ubuntu.user-data`, a MIME multipart file with one part per fragment.
Edit `src/`, never `dist/`. Each release publishes `Ubuntu.user-data`;
users download it to `%USERPROFILE%\.cloud-init\` and write the meta-data
beside it from the example in `README.md`, matching the instance `Ubuntu`,
the default name from `wsl --install Ubuntu`. It runs once, on first boot,
and Ubuntu's OOBE (`/usr/lib/wsl/wsl-setup`) waits for it. Read
`docs/build.md` before you add, rename or renumber a fragment. A change to a
fragment is released from `main` once the end-to-end tests pass, with a
version commitizen works out from the pull request's title, so choose its
type by what the change does and mark a breaking change with `!`.

## Keep it native

Prefer plain cloud-init modules and semantics over custom scripts.
Identifying values come only from `<InstanceName>.meta-data`, read in each
fragment that uses them as `ds.meta_data.*`. Don't add loaders that read
other files from the Windows side.

## Facts that constrain the design

- The WSL datasource loads exactly one user-data file
  (`<Instance>` > `<ID>-<VERSION_ID>` > `<ID>-all` > `default`) and only
  `<Instance>.meta-data`, which must contain `instance-id`. Nothing is merged
  except Ubuntu Pro's `agent.yaml`, so never add an `ubuntu_pro` key.
- With `agent.yaml` present the datasource wraps a user-data that isn't
  plain cloud-config, such as the MIME file, in `#include`; the parts still
  render (inferred from the datasource's source).
- cloud-init merges the parts in the order they're attached, which is the
  order of the fragments' numbers. Every fragment keeps the shared
  `merge_how` (`list(append)`, `dict(no_replace, recurse_list)`), or its
  lists replace the earlier fragments' lists. A fragment's number sets where
  its `runcmd` entries run, so give a new one a number between those of the
  fragments it runs after and before.
- A fragment that reads meta-data starts with `## template: jinja`.
  cloud-init renders each part on its own, so a fragment sets every variable
  and macro it uses, such as `user`; another fragment's are undefined, and an
  undefined name in a condition is silently false.
- Jinja runs with `trim_blocks` on and `lstrip_blocks` off: put every
  `{% %}` / `{# #}` tag at column 0, or its indentation is left behind and
  breaks YAML. Never write `{#`, `{{` or `{%` inside embedded shell.
- Undefined meta-data keys are falsy; read them as `ds.meta_data.x or ''`.
  Values rendered into `.gitconfig` go through the `gitval` macro. Meta-data
  is YAML, so a key can be a list (`vscode_extensions`, `gh_extensions`);
  normalise its type first, and let only validated items into shell. Report
  the rest with `printf %s` and an ASCII-escaped `tojson` value: a non-BMP
  character otherwise becomes lone surrogates that fail all of runcmd.
- runcmd runs as root with no user bus, so `systemctl --user` fails there;
  enable user units with `systemctl --global enable`. The first
  `runuser -l <user>` entry starts the user's manager (pam_systemd), which
  reads the global wants only when it starts, so global enables go in an
  earlier fragment. `--global` also reaches root's user manager, which
  `sudo su` starts; keep a unit out of it with a `ConditionUser=!root`
  drop-in.
- Module order: init stage runs `write_files` and `users`; final stage runs
  packages, deferred `write_files`, then `runcmd` (a `#!/bin/sh` script with
  no `set -e`, so entries are independent). Anything that needs a package or
  a package-created group (`libvirt`) belongs in `runcmd` or deferred
  `write_files`. Listing `libvirt` in `users.groups` makes it an ordinary
  group that takes gid 1000.
- `/etc/wsl.conf` must keep `systemd=true` and `appendWindowsPath=false`
  (otherwise `xdg-open` bypasses `$BROWSER`), and must have no `[user]` or
  `[time]` section: the OOBE writes `[user] default=`, and the time zone
  follows Windows.
- WSL attaches swap before systemd starts; only `swapoff -a` (the
  `disable-swap.service` unit) removes it.
- `qemu-kvm` is a virtual package and `*-hwe` packages conflict with the base
  virt stack; one bad name fails the whole `packages` install. Check
  candidates with `apt-cache policy` before adding packages.
- Never set `power_state` or `package_reboot_if_required`: they restart the
  instance in the middle of the OOBE.
- Run user-scoped installers with `runuser -l <user>` so HOME is the user's.
  runcmd itself has no HOME, so this applies to root too; `~` in a
  `runuser -l root` command is `/root`, so point it at the user's checkout
  with an absolute path.
- `users:` skips existing users, root included (and would lock root's
  password). Root's login shell is set with a guarded `usermod` in runcmd,
  before root's dotfiles install so its `$SHELL` check sees zsh.

## Privacy

The repo is public. No usernames, emails, signing keys, hostnames or
`/mnt/c/Users/<name>/` paths in any file here; they belong in the user's
private meta-data. Nothing checks for such a path, so look for one
yourself. The README's meta-data example is public too: identifying values
stay empty, and only generic defaults such as `vscode_extensions` and
`gh_extensions` are filled in. A key added to the user-data goes into the
example.

## Check a change

Nothing renders the user-data or runs `cloud-init schema` on it before a
release. After every change, run `make build`, which only joins the
fragments, and tell the user that the user-data couldn't be validated. The
end-to-end tests install it on a first boot only when a release is due.
