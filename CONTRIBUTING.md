# Contributing

How changes reach this repository, how to set up and run the checks, and what CI and the release workflow run.

## Issues and pull requests

Issues and pull requests are limited to the repository's collaborators. The config runs as root on the collaborators' own machines, so every change comes from someone they trust.

You're free to use the config as it is, or to fork the repository and change your copy. A fork doesn't need anything from this repository: it's [MIT licensed](LICENSE).

## How changes land

- `main` is protected. Every change goes through a pull request from a short-lived branch, and is squash-merged.
- Branches are named `feature/<slug>`, `bugfix/<slug>` or `other/<slug>`, with a lowercase, hyphenated slug.
- Commit messages and pull request titles follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat(cloud-init): Install tree`. A pull request's title and description become its commit on `main`, so write them as a commit header and body. Mark a breaking change with `!` in the title.
- A pull request that changes what `make build` writes to `dist/` bumps the `version` in every manifest in `src/manifests/`, as [docs/releases.md](docs/releases.md#how-the-version-is-decided) says. Without the bump, the change isn't released.
- Keep each pull request to one change. Rebase a branch on `main` to bring it up to date. Don't merge `main` into it.

## Set up

Work on Ubuntu 26.04, or in a WSL instance built from this config, with the system Python 3.14 and [uv](https://docs.astral.sh/uv/). Install the tools from apt, then set up the virtual environment with `make sync`. It creates `.venv` with the system site packages, so the build can import apt's `cloud-init`, `jsonschema` and `yaml`, then installs the dev dependencies:

```sh
sudo apt-get install cloud-init make shellcheck shfmt
make sync
```

uv only gives a venv the system site packages when it creates it, so `make venv` does nothing when `.venv` exists. To start again, delete `.venv` and run `make sync`.

## Checks

Run these from the repository's root:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
make build
uv run invoke version
shellcheck .github/scripts/*.sh
shfmt -d .
```

- `make build` builds each manifest in `src/manifests/` into `dist/<name>.user-data`, and fails with the reason when a manifest doesn't match its schema or lists a fragment that doesn't exist. `make build <filter>` builds only the manifests whose file name contains the filter, such as `make build ubuntu`. Edit `src/`, never `dist/`.
- There are no unit tests, and nothing validates the rendered user-data. [docs/build.md](docs/build.md#validation) says what `make build` does and doesn't check.
- `uv run invoke version` prints the manifests' version, which the release workflow releases as `v<version>` when no tag has it yet. It fails when the manifests' versions differ.
- shfmt reads its options from `.editorconfig`, so run it without formatting flags: any flag such as `-i` makes it ignore `.editorconfig`.

To test a real first boot, install a throwaway instance as the README's [Testing a change](README.md#testing-a-change) describes.

## CI and releases

- **Pull requests:** every pull request to `main` that changes more than docs runs the checks above in `ci.yml`. Claude then reviews the change by [REVIEW.md](REVIEW.md) and comments on the pull request. A pull request merges once CI passes and every review thread is resolved. [docs/ci.md](docs/ci.md) describes each job.
- **Releases:** every push to `main` that changes more than docs runs `release.yml`. It builds the config and, when the manifests' version has no tag yet, installs an instance from it on Windows runners and publishes the files as the GitHub release `v<version>`. [docs/releases.md](docs/releases.md) describes it.
