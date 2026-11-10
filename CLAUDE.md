# WSL

A reusable cloud-init config that builds a WSL instance for development from scratch, for each distro in `src/manifests/`, and installs the [froazin/dotfiles](https://github.com/froazin/dotfiles) into it. It's written as cloud-config fragments in `src/`, which each distro's manifest picks from, built into the files each GitHub release publishes. The repository is public, and people copy from it, so it stays generic.

## Contents

1. [Layout](#layout)
1. [Conventions](#conventions)
1. [Contributing](#contributing)

## Layout

| Path | Holds |
| --- | --- |
| `src/fragments/` | Every cloud-config fragment, one per feature, merged in the order a manifest lists them. Before you change them, read [docs/provisioning.md](docs/provisioning.md) and [docs/build.md](docs/build.md). Before you add or change a meta-data key, read [docs/meta-data.md](docs/meta-data.md) too |
| `src/manifests/<distro>.json` | A distro's manifest, named after the distro: the release version, its description and every fragment in its user-data, in the order they merge. Before you add a distro, change a manifest or add a fragment for one distro, read [docs/distros.md](docs/distros.md). Before you change the version, read [docs/releases.md](docs/releases.md#how-the-version-is-decided) |
| `schemas/manifest.schema.json`, `scripts/manifest.jq` | The manifest's schema for editors, and the same rules in jq, which the build checks each manifest with. Keep them in step. Before you change them, read [docs/distros.md](docs/distros.md) |
| `dist/` | The built files each release publishes. `make build` writes it, and Git ignores it |
| `Makefile`, `scripts/user-data.sh`, `scripts/version.jq` | `make build`, which joins each manifest's fragments into `dist/` with `cloud-init devel make-mime`, `make version`, which prints the release version, and `make clean`. Before you change them, read [docs/build.md](docs/build.md). Nothing validates the rendered user-data |
| `docs/` | Design docs for engineers changing the config |
| `.github/workflows/ci.yml` | CI on pull requests: the checks and Claude's code review. Before you change it, read [docs/ci.md](docs/ci.md) |
| `.github/workflows/release.yml`, `.github/scripts/` | The release workflow on `main`, with the end-to-end tests on Windows runners and their scripts. Before you change them, read [docs/releases.md](docs/releases.md) |
| `.github/dependabot.yml` | The weekly action updates |
| `REVIEW.md` | Instructions for CI's Claude code review: what counts as Important, the Nit cap, what to skip, what to always check and the evidence a finding needs |
| `.claude/rules/cloud-init.md` | The facts that constrain the user-data. It loads when you touch `src/` |
| `.claude/settings.json` | The project's permissions for Claude Code: the build and version commands |
| `README.md` | The entry point for people who use the config, with the install steps, the meta-data example and the `.wslconfig` example. The end-to-end tests read the meta-data example after its `<!-- meta-data example -->` comment. Before you change the example, read [docs/meta-data.md](docs/meta-data.md) |
| `CONTRIBUTING.md` | Who can open issues and pull requests, how changes land, the set-up and the checks to run |
| `.editorconfig`, `.gitattributes`, `.gitignore` | shfmt and editor settings, LF line endings for every file and what Git ignores, such as `dist/` |
| `.vscode/settings.json` | Shared VS Code settings: Jinja YAML highlighting for the cloud-init files, Jinja TOML for `.wslconfig` and the schema for each manifest in `src/manifests/` |
| `LICENSE` | The MIT licence |

## Conventions

- **Never commit identifying data.** No real names, emails, usernames, signing keys, hostnames or `/mnt/c/Users/<name>/` paths in any file, the README's meta-data example included. They go in the user's private meta-data. Use placeholders such as `<you>` or `jdoe` in examples.
- **Prefer native mechanisms:** cloud-init modules, and official installers run as the user so they can update themselves, over custom glue.
- **Edit `src/`, never `dist/`.** Run `make build` to rebuild `dist/`.
- **Bump the version with the change.** A change to what's built into `dist/` bumps the `version` in every manifest in the same pull request, or it isn't released. [docs/releases.md](docs/releases.md#how-the-version-is-decided) says which part to bump.
- **Each fragment stands alone.** cloud-init renders each fragment's Jinja on its own, so a fragment sets every Jinja variable it uses, and every fragment keeps the shared `merge_how` that appends lists. See [docs/build.md](docs/build.md#how-the-build-works).
- **Share fragments by default.** List a fragment in only one manifest when what it says is wrong for another distro. Split the part that differs out of a shared fragment rather than copying it. Every distro reads the same meta-data keys. See [docs/distros.md](docs/distros.md#shared-or-distro-fragments).
- **Build with make, jq and the cloud-init CLI.** The project has no Python tooling. Put the build's logic in `scripts/`, as POSIX `sh` that ShellCheck and shfmt check, or as jq filters, and keep `Makefile` recipes to one command. The project has no unit tests.
- **Keep `packages` in step with the dotfiles.** The fragments' `packages` list the dotfiles modules' dependencies. When a dotfiles module gains a dependency, add it here too.
- **Don't write outside the repository to test.** Writing to the Windows profile (`%USERPROFILE%\.cloud-init`, `.wslconfig`), or installing or unregistering WSL instances, needs the user's go-ahead.
- Run the checks in [CONTRIBUTING.md](CONTRIBUTING.md#checks) before you say a change works.
- Pin every action a workflow uses to a full commit SHA, with its version in a comment.
- **Squash-merge a pull request once the CI workflow passes, or didn't run because the pull request only changes docs, and every review thread is resolved.** Resolve a thread only after you've fixed what it raises, or replied with why it isn't a problem.
- When you review a change locally, such as with `/code-review`, also follow `REVIEW.md` as it is on `main` (`git show main:REVIEW.md`), not a copy the change edits.
- Update the design doc in `docs/`, and the README when users would notice, in the same pull request as the change that makes them out of date.
- Write in British English.

## Contributing

| Repository | Path | GitHub | Visibility | Default branch | Kind |
| --- | --- | --- | --- | --- | --- |
| Source | `.` | `froazin/wsl` | Public | `main` | Code: PRs, squash-merged |

- **Commit scopes:** `cloud-init`, `tooling` (the `Makefile`, `scripts/` and the manifest schema), `ci`, `docs`, `claude`, `deps`.
- **Feature flags:** none.
- **Releases:** versioned GitHub releases, tagged `vX.Y.Z` by the release workflow on `main`. The version is the `version` in the manifests, which a pull request that changes what's built into `dist/` bumps by hand. A release is made when no tag has that version yet. The first release will be `v0.0.1`. See [docs/releases.md](docs/releases.md).
- **CI:** `ci.yml` on every pull request to `main` that changes more than docs, and `release.yml` on every push to `main` that does. See [docs/ci.md](docs/ci.md) and [docs/releases.md](docs/releases.md).
- User docs live in `README.md`. The repository has no wiki.
- Issues and pull requests are limited to collaborators, because the config runs as root on their machines.
