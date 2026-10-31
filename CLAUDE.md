# WSL

A reusable cloud-init config that builds an Ubuntu 26.04 WSL instance for development from scratch, and installs the [froazin/dotfiles](https://github.com/froazin/dotfiles) into it. It's written as cloud-config parts in `src/`, built into the files each GitHub release publishes. The repository is public, and people copy from it, so it stays generic.

## Contents

1. [Layout](#layout)
1. [Conventions](#conventions)
1. [Contributing](#contributing)

## Layout

| Path | Holds |
| --- | --- |
| `src/Ubuntu-26.04.user-data.d/` | The user-data as cloud-config parts, one per feature, merged in name order. Before you change them, read [docs/provisioning.md](docs/provisioning.md) and [docs/build.md](docs/build.md). Before you add or change a meta-data key, read [docs/meta-data.md](docs/meta-data.md) too |
| `src/Ubuntu-26.04.meta-data` | The meta-data template users fill in, released as it is. Before you change it, read [docs/meta-data.md](docs/meta-data.md) |
| `dist/` | The built files each release publishes. `invoke build` writes it, and Git ignores it |
| `tasks.py`, `scripts/build/` | The `build` and `validate` tasks: building `src/` into `dist/` with `cloud-init devel make-mime`, and checking the result against the cases in `scripts/build/cases.py`. Before you change them, read [docs/build.md](docs/build.md). The `validate-user-data` skill says how to run the validation and what each case proves |
| `scripts/release/` | The `version` task: whether `dist/` makes a release, and its version. Before you change it, read [docs/releases.md](docs/releases.md) |
| `pyproject.toml`, `pyrightconfig.json` | The Python dependencies and the settings for uv, pytest, Ruff, Pyright and semantic-release. See [Tool configuration](docs/build.md#tool-configuration) |
| `docs/` | Design docs for engineers changing the config |
| `.github/workflows/ci.yml` | CI on pull requests: the checks and Claude's code review. Before you change it, read [docs/ci.md](docs/ci.md) |
| `.github/workflows/release.yml`, `.github/scripts/` | The release workflow on `main`, with the end-to-end tests on Windows runners and their scripts. Before you change them, read [docs/releases.md](docs/releases.md) |
| `.github/dependabot.yml` | The weekly action and uv updates. See [Dependabot](docs/ci.md#dependabot) |
| `REVIEW.md` | Instructions for CI's Claude code review: what counts as Important, the Nit cap, what to skip, what to always check and the evidence a finding needs |
| `.claude/rules/cloud-init.md` | The facts that constrain the user-data. It loads when you touch `src/` |
| `README.md` | The entry point for people who use the config, with the install steps and the `.wslconfig` example |
| `CONTRIBUTING.md` | Who can open issues and pull requests, how changes land, the set-up and the checks to run |
| `.editorconfig`, `.gitattributes` | shfmt and editor settings, and LF line endings for every file |
| `.vscode/settings.json` | Shared VS Code settings: Jinja YAML highlighting for the cloud-init files, and TOML for `.wslconfig` |

## Conventions

- **Never commit identifying data.** No real names, emails, usernames, signing keys, hostnames or `/mnt/c/Users/<name>/` paths in any file. They go in the user's private meta-data. Use placeholders such as `<you>` or `jdoe` in examples.
- **Prefer native mechanisms:** cloud-init modules, and official installers run as the user so they can update themselves, over custom glue.
- **Edit `src/`, never `dist/`.** Run `uv run invoke build` to rebuild `dist/`.
- **Each part stands alone.** cloud-init renders each part's Jinja on its own, so a part sets every Jinja variable it uses, and every part keeps the shared `merge_how` that appends lists. See [docs/build.md](docs/build.md#how-the-build-works).
- **Keep `tasks.py` thin.** A task only calls a package in `scripts/` and turns its error into an exit status. Put logic, and its tests, in `scripts/<package>/`.
- **Keep `packages` in step with the dotfiles.** The parts' `packages` list the dotfiles modules' dependencies. When a dotfiles module gains a dependency, add it here too.
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

- **Commit scopes:** `cloud-init`, `tooling` (`tasks.py`, `scripts/` and the Python settings), `ci`, `docs`, `claude`, `deps`.
- **Feature flags:** none.
- **Releases:** versioned GitHub releases, tagged `vX.Y.Z` by the release workflow on `main`. A release is made only when the content of `dist/` changes, and the commits that change `src/` decide its version. The first release will be `v0.1.0`. See [docs/releases.md](docs/releases.md).
- **CI:** `ci.yml` on every pull request to `main` that changes more than docs, and `release.yml` on every push to `main` that does. See [docs/ci.md](docs/ci.md) and [docs/releases.md](docs/releases.md).
- User docs live in `README.md`. The repository has no wiki.
- Issues and pull requests are limited to collaborators, because the config runs as root on their machines.
