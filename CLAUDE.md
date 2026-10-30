# WSL

A reusable cloud-init config that builds an Ubuntu 26.04 WSL instance for development from scratch, and installs the [froazin/dotfiles](https://github.com/froazin/dotfiles) into it. The repository is public, and people copy from it, so it stays generic.

## Contents

1. [Layout](#layout)
1. [Conventions](#conventions)
1. [Contributing](#contributing)

## Layout

| Path | Holds |
| --- | --- |
| `src/` | The three files users copy to their Windows profile: `.wslconfig`, `Ubuntu-26.04.user-data` (a Jinja cloud-config) and `Ubuntu-26.04.meta-data` (a fill-in template). Before you change them, read [docs/provisioning.md](docs/provisioning.md). Before you add or change a meta-data key, read [docs/meta-data.md](docs/meta-data.md) too |
| `tests/validate-user-data.sh` | Renders the user-data against mock meta-data and checks each result. The `validate-user-data` skill says how to run it and what each case proves |
| `docs/` | Design docs for engineers changing the config |
| `.github/workflows/ci.yml`, `.github/scripts/` | CI on pull requests: lint and validation, end-to-end tests on Windows runners and Claude's code review. Before you change them, read [docs/ci.md](docs/ci.md) |
| `.github/dependabot.yml` | The weekly action updates. See [Dependabot](docs/ci.md#dependabot) |
| `REVIEW.md` | Instructions for CI's Claude code review: what counts as Important, the Nit cap, what to skip, what to always check and the evidence a finding needs |
| `.claude/rules/cloud-init.md` | The facts that constrain the user-data. It loads when you touch `src/` |
| `README.md` | The entry point for people who use the config, with the install steps |
| `CONTRIBUTING.md` | Who can open issues and pull requests, how changes land and the checks to run |
| `.editorconfig`, `.gitattributes` | shfmt and editor settings, and LF line endings for every file |

## Conventions

- **Never commit identifying data.** No real names, emails, usernames, signing keys, hostnames or `/mnt/c/Users/<name>/` paths in any file. They go in the user's private meta-data. Use placeholders such as `<you>` or `jdoe` in examples.
- **Prefer native mechanisms:** cloud-init modules, and official installers run as the user so they can update themselves, over custom glue.
- **Keep `packages` in step with the dotfiles.** The user-data's `packages` lists the dotfiles modules' dependencies. When a dotfiles module gains a dependency, add it here too.
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

- **Commit scopes:** `cloud-init`, `wslconfig`, `ci`, `docs`, `claude`, `deps`.
- **Feature flags:** none.
- **Releases:** none. `main` is what people copy.
- **CI:** `ci.yml` on every pull request to `main` that changes more than docs. See [docs/ci.md](docs/ci.md).
- User docs live in `README.md`. The repository has no wiki.
- Issues and pull requests are limited to collaborators, because the config runs as root on their machines.
