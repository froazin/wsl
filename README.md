# WSL

A reusable cloud-init config that builds an Ubuntu 26.04 WSL instance for development from scratch, on its first boot.

## What it sets up

- The packages a zsh workstation needs, plus podman and tools such as `gh`, `ripgrep`, `fd` and `btop`.
- A KVM and libvirt stack for running virtual machines inside WSL.
- podman's Docker-compatible API socket: rootless for every user, and the system socket for root.
- `/etc/wsl.conf` with systemd on, and swap off, which WSL turns on by default.
- Windows tools (VS Code, the 1Password CLI, OpenSSH and `clip`) linked into the Linux `PATH`, and `$BROWSER` set so `xdg-open` opens things in Windows.
- A user with zsh and passwordless sudo, when you give a username.
- For that user: `uv`, `pulumi`, Biome, `nvm`, Claude Code, the Claude Platform CLI (`ant`) and the VS Code and GitHub CLI extensions you list.
- A git config for that user, with optional commit signing.
- The [froazin/dotfiles](https://github.com/froazin/dotfiles) zsh, git, podman and Claude Code config, for the user and for root.

## Using it

You need Windows with WSL 2. Each [release](https://github.com/froazin/wsl/releases) has two files:

| File | Copy to | What it is |
| --- | --- | --- |
| `Ubuntu-26.04.user-data` | `%USERPROFILE%\.cloud-init\Ubuntu-26.04.user-data` | The cloud-init config. It holds nothing personal |
| `Ubuntu-26.04.meta-data` | `%USERPROFILE%\.cloud-init\Ubuntu-26.04.meta-data` | Your username, git identity and extension lists. Fill it in, and keep your copy to yourself |

1. Download the latest release's files. From PowerShell:

   ```powershell
   $base = 'https://github.com/froazin/wsl/releases/latest/download'
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.cloud-init" | Out-Null
   foreach ($f in 'Ubuntu-26.04.user-data', 'Ubuntu-26.04.meta-data') {
       Invoke-WebRequest "$base/$f" -OutFile "$env:USERPROFILE\.cloud-init\$f"
   }
   ```

1. Fill in `%USERPROFILE%\.cloud-init\Ubuntu-26.04.meta-data`. Its comments describe each value, and an empty value is skipped.
1. Optionally, set up `.wslconfig` as [The .wslconfig example](#the-wslconfig-example) describes.
1. Install the distribution under its default name, which is the name cloud-init matches the files by:

   ```powershell
   wsl --install Ubuntu-26.04
   ```

   cloud-init runs on the first boot only, and the first launch waits for it.

1. When it finishes, restart the instance so the `wsl.conf` settings and the new group memberships take effect:

   ```powershell
   wsl --terminate Ubuntu-26.04
   ```

### Reading what it runs

The user-data is a MIME multipart file of cloud-config parts, and each part is base64-encoded, so it isn't readable as text. Read the parts in [`src/Ubuntu-26.04.user-data.d/`](src/Ubuntu-26.04.user-data.d/) at the release's tag instead: `https://github.com/froazin/wsl/tree/<tag>/src/Ubuntu-26.04.user-data.d`, with the tag, such as `v1.2.3`, from the release's page.

### The .wslconfig example

`%USERPROFILE%\.wslconfig` holds the settings for the WSL 2 virtual machine, shared by every instance. The config works without one. This example suits a large workstation: copy it, or merge it into yours by hand.

```ini
[wsl2]
networkingMode=Mirrored

dnsTunneling=true
autoProxy=true

swap=0
defaultVhdSize=64GB

processors=12
memory=32GB
kernelCommandLine=cgroup_no_v1=all

nestedVirtualization=true

[general]
instanceIdleTimeout=-1

[experimental]
hostAddressLoopback=true
sparseVhd=true
```

- Check `processors` and `memory` fit your machine.
- `networkingMode=Mirrored` needs Windows 11 22H2 or later. Where it isn't supported, WSL falls back to no network, so remove the line.
- WSL reads the file when its virtual machine starts, so run `wsl --shutdown` after you change it.

### Without a username

If the meta-data gives no `username`, WSL asks you to create a user as normal, and that user gets zsh and the virtualisation groups. Root is already configured. Finish setting up the user yourself:

```bash
curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
curl -fsSL https://get.pulumi.com | sh -s -- --no-edit-path
curl -fsSL https://biomejs.dev/install | bash -s -- --no-modify-path
git clone https://github.com/nvm-sh/nvm.git ~/workspaces/github.com/nvm-sh/nvm
cd ~/workspaces/github.com/nvm-sh/nvm
git checkout "$(git describe --abbrev=0 --tags --match 'v[0-9]*' "$(git rev-list --tags --max-count=1)")"
# Installs that release into ~/.nvm. The zsh config from the dotfiles loads it, so leave the profiles alone.
PROFILE=/dev/null bash install.sh
cd
curl -fsSL https://claude.ai/install.sh | bash
v="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/anthropics/anthropic-cli/releases/latest)"; v="${v##*/v}"
case "$(uname -m)" in aarch64) a=arm64 ;; *) a=amd64 ;; esac
mkdir -p ~/.local/bin && curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v$v/ant_${v}_linux_$a.tar.gz" | tar -xzmf - -C ~/.local/bin ant
# The extensions in your meta-data's vscode_extensions, for example:
code --install-extension Anthropic.claude-code --install-extension ms-python.python
# The extensions in your meta-data's gh_extensions, for example:
gh extension install https://github.com/nektos/gh-act
git clone https://github.com/froazin/dotfiles.git ~/workspaces/github.com/froazin/dotfiles
# Until the ~/.zshenv from the dotfiles exists, the installer can't see tools in ~/.local/bin.
PATH="$HOME/.local/bin:$HOME/.pulumi/bin:$PATH" sh ~/workspaces/github.com/froazin/dotfiles/src/install.sh
```


### Testing a change

Build the files with `uv run invoke build`, as [CONTRIBUTING.md](CONTRIBUTING.md#set-up) describes. Copy `dist/Ubuntu-26.04.user-data` and `dist/Ubuntu-26.04.meta-data` as `ci-test.user-data` and `ci-test.meta-data` to match a throwaway instance, then install it and remove it when you're done:

```powershell
wsl --install Ubuntu-26.04 --name ci-test
wsl --unregister ci-test
```

WSL instances share one cgroup tree, so stop your main instance first if you're testing the user's systemd services, such as `podman.socket`. While another instance runs a systemd session for the same uid, the test instance's user session fails to start.

### Making it your own

Fork the repository and change the parts in [`src/Ubuntu-26.04.user-data.d/`](src/Ubuntu-26.04.user-data.d/), then build your own files with `uv run invoke build`, which writes them to `dist/`. The user-data clones and installs [froazin/dotfiles](https://github.com/froazin/dotfiles): point `dotfiles_repo` near the top of [`99-dotfiles.user-data`](src/Ubuntu-26.04.user-data.d/99-dotfiles.user-data) at your own dotfiles, which need a `src/install.sh`, or remove the entries that run it.

## How it works

The config is plain cloud-init, written as one part per feature. `invoke build` joins the parts into one user-data file, because WSL reads only one, and the release workflow publishes it. cloud-init's WSL datasource reads the files on the instance's first boot:

```mermaid
flowchart LR
    accTitle: How the files reach the instance
    accDescr: invoke build joins the parts in src into one MIME user-data, and the release workflow publishes it with the meta-data template. You download both into your Windows profile and fill in the meta-data. cloud-init's WSL datasource reads them, renders each part's Jinja with the meta-data, merges the parts in name order and runs the cloud-config, which installs the dotfiles for the user and for root. WSL reads the optional .wslconfig.
    parts["src/Ubuntu-26.04.user-data.d/"] -->|"invoke build"| release["GitHub release"]
    meta["src/Ubuntu-26.04.meta-data"] -->|"copied as it is"| release
    release -->|"downloaded to .cloud-init, meta-data filled in"| ds["cloud-init WSL datasource"]
    ds -->|"renders each part, merges them in name order"| modules["cloud-init modules"]
    wslconfig["optional .wslconfig"] -->|"read by WSL"| vm["WSL 2 virtual machine"]
    vm -->|hosts| modules
    modules -->|"clones and runs install.sh"| dotfiles["froazin/dotfiles"]
```

The design docs explain each part, for anyone changing it:

- [Provisioning](docs/provisioning.md): how the user-data's parts, stages and `runcmd` work.
- [WSL meta-data](docs/meta-data.md): how each meta-data key is validated and where it ends up.
- [Build and validation](docs/build.md): how `tasks.py` and `scripts/` build the parts into `dist/` and check the result.
- [CI](docs/ci.md): the checks and the code review that run on each pull request.
- [Releases](docs/releases.md): how `main` is released, with the end-to-end tests on Windows runners.

## Contributing

Issues and pull requests are open to this repository's collaborators only, because the config runs as root on their machines. You're welcome to use the config as it is, or to fork the repository and keep your own version. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[MIT](LICENSE).
