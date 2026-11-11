# WSL

A reusable cloud-init config that builds an Ubuntu WSL instance for development from scratch, and installs the [froazin/dotfiles](https://github.com/froazin/dotfiles) into it. It's written as numbered cloud-config fragments in `src/`, joined in order into the one user-data file each GitHub release publishes. The repository is public, and people copy from it, so it stays generic.

## Contents

1. [Layout](#layout)
1. [Conventions](#conventions)
1. [Contributing](#contributing)

## Layout

| Path | Holds |
| --- | --- |
| `src/` | Every cloud-config fragment, one per feature, named `<NN>-<feature>.user-data` and merged in the order of their numbers. Before you add, change or renumber one, read [docs/provisioning.md](docs/provisioning.md) and [docs/build.md](docs/build.md). Before you add or change a meta-data key, read [docs/meta-data.md](docs/meta-data.md) too |
| `dist/` | `Ubuntu.user-data`, the file each release publishes, and the rendered fragments `make lint` checks, in `dist/lint/`. make writes them, and Git ignores them |
| `Makefile` | `make build`, which joins the fragments into `dist/Ubuntu.user-data` with `cloud-init devel make-mime` and a fixed MIME boundary, `make lint`, which renders each fragment with each file in `test/` and checks it with yamllint and `cloud-init schema`, and `make clean`. Before you change it, read [docs/build.md](docs/build.md). Nothing checks the merged user-data |
| `test/`, `.yamllint` | The instance data `make lint` renders the fragments with, one file per case, and yamllint's settings. A new meta-data key goes into `test/meta-data.json`, with a placeholder value |
| `docs/` | Design docs for engineers changing the config |
| `.github/workflows/ci.yml` | CI on pull requests: the checks and Claude's code review. Before you change it, read [docs/ci.md](docs/ci.md) |
| `.github/workflows/release.yml`, `.github/scripts/` | The release workflow on `main`, with the end-to-end test on a Windows runner, and its scripts. Before you change them, read [docs/releases.md](docs/releases.md) |
| `.github/dependabot.yml` | The weekly action updates |
| `REVIEW.md` | Instructions for CI's Claude code review: what counts as Important, the Nit cap, what to skip, what to always check and the evidence a finding needs |
| `.claude/rules/cloud-init.md` | The facts that constrain the user-data. It loads when you touch `src/` |
| `.cz.toml` | commitizen's settings, which the release workflow works out each release's version with. See [docs/releases.md](docs/releases.md#how-the-version-is-decided) |
| `.claude/settings.json` | The project's permissions for Claude Code: the build command and the version preview, `cz bump --get-next --yes --allow-no-commit` |
| `README.md` | The entry point for people who use the config, with the install steps, the meta-data example, the `.wslconfig` example and how to build and check it. Testing on an instance is in [docs/testing.md](docs/testing.md), not the README. The end-to-end tests read the meta-data example after its `<!-- meta-data example -->` comment. Before you change the example, read [docs/meta-data.md](docs/meta-data.md) |
| `.editorconfig`, `.gitattributes`, `.gitignore` | shfmt and editor settings, LF line endings for every file and what Git ignores, such as `dist/` |
| `.vscode/settings.json` | Shared VS Code settings: Jinja YAML highlighting for the cloud-init files and Jinja TOML for `.wslconfig` |
| `LICENSE` | The MIT licence |

## Conventions

- **Never commit identifying data.** No real names, emails, usernames, signing keys, hostnames or `/mnt/c/Users/<name>/` paths in any file, the README's meta-data example included. They go in the user's private meta-data. Use placeholders such as `<you>` or `jdoe` in examples.
- **Prefer native mechanisms:** cloud-init modules, and official installers run as the user so they can update themselves, over custom glue.
- **Edit `src/`, never `dist/`.** Run `make build` to rebuild `dist/`.
- **Each fragment stands alone.** cloud-init renders each fragment's Jinja on its own, so a fragment sets every Jinja variable it uses, and every fragment keeps the shared `merge_how` that appends lists. See [docs/build.md](docs/build.md#how-the-build-works).
- **Number fragments to order them.** A fragment's two-digit number sets where it merges and where its `runcmd` entries run. Number a new one into the gap where it belongs, rather than renumbering the rest. See [docs/build.md](docs/build.md#the-fragments).
- **Build with make and the cloud-init CLI.** The build and its checks are the `Makefile` alone, with no manifests, version files or Python tooling. Keep it that small. The project has no unit tests.
- **Keep `packages` in step with the dotfiles.** The fragments' `packages` list the dotfiles modules' dependencies. When a dotfiles module gains a dependency, add it here too.
- **Don't write outside the repository to test.** Writing to the Windows profile (`%USERPROFILE%\.cloud-init`, `.wslconfig`), or installing or unregistering WSL instances, needs the user's go-ahead.
- Run the checks in the README's [Building it](README.md#building-it) before you say a change works. To test a change on a first boot, read [docs/testing.md](docs/testing.md) before you install the instance, and check Windows interop in the other instances after every `wsl --terminate` or `wsl --unregister`.
- Choose a pull request's type by what it changes, because commitizen works out the release's version from it. See [docs/releases.md](docs/releases.md#how-the-version-is-decided).
- Pin every action a workflow uses to a full commit SHA, with its version in a comment.
- **Squash-merge a pull request once the CI workflow passes, or didn't run because the pull request only changes docs, and every review thread is resolved.** Resolve a thread only after you've fixed what it raises, or replied with why it isn't a problem.
- When you review a change locally, such as with `/code-review`, also follow `REVIEW.md` as it is on `main` (`git show main:REVIEW.md`), not a copy the change edits.
- Update the design doc in `docs/`, and the README when users would notice, in the same pull request as the change that makes them out of date.
- Write in British English.

## Contributing

| Repository | Path | GitHub | Visibility | Default branch | Kind |
| --- | --- | --- | --- | --- | --- |
| Source | `.` | `froazin/wsl` | Public | `main` | Code: PRs, squash-merged |

- **Commit scopes:** `cloud-init`, `tooling` (the `Makefile`), `ci`, `docs`, `claude`, `deps`.
- **Feature flags:** none.
- **Releases:** versioned GitHub releases, tagged `vX.Y.Z` by the release workflow on `main`. It releases `Ubuntu.user-data` when its SHA-1 differs from the latest release's, and commitizen works out the version from the pull request titles since the last release. The first release will be `v0.1.0`. See [docs/releases.md](docs/releases.md).
- **CI:** `ci.yml` on every pull request to `main` that changes more than docs, and `release.yml` on every push to `main` that does. See [docs/ci.md](docs/ci.md) and [docs/releases.md](docs/releases.md).
- User docs live in `README.md`. The repository has no wiki.
- Issues and pull requests are limited to collaborators, because the config runs as root on their machines.
