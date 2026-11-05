# Contributing

How changes reach this repository, how to set up and run the checks, and what CI and the release workflow run.

## Issues and pull requests

Issues and pull requests are limited to the repository's collaborators. The config runs as root on the collaborators' own machines, so every change comes from someone they trust.

You're free to use the config as it is, or to fork the repository and change your copy. A fork doesn't need anything from this repository: it's [MIT licensed](LICENSE).

## How changes land

- `main` is protected. Every change goes through a pull request from a short-lived branch, and is squash-merged.
- Branches are named `feature/<slug>`, `bugfix/<slug>` or `other/<slug>`, with a lowercase, hyphenated slug.
- Commit messages and pull request titles follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat(cloud-init): Install tree`. A pull request's title and description become its commit on `main`, so write them as a commit header and body. The types of the commits that change `src/` decide the next release's version.
- Keep each pull request to one change. Rebase a branch on `main` to bring it up to date. Don't merge `main` into it.

## Set up

Work on Ubuntu 26.04, or in a WSL instance built from this config, with the system Python 3.14 and [uv](https://docs.astral.sh/uv/). Install the tools from apt, then create the virtual environment with the system site packages, so the validation can import apt's `cloud-init`:

```sh
sudo apt-get install cloud-init python3-yaml git openssh-client shellcheck shfmt
uv venv --system-site-packages --python /usr/bin/python3
uv sync
```

## Checks

Run these from the repository's root:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run invoke validate
shellcheck .github/scripts/*.sh
shfmt -d .
```

- `uv run invoke build` builds each distro's fragments in `src/` into `dist/<distro>.user-data`. Edit `src/`, never `dist/`.
- `uv run invoke validate` builds `dist/`, then merges the user-data for each mock meta-data case as cloud-init does at boot and checks the result. It exits 1 when a check fails. Add a case for every new meta-data key or conditional, including the key being unset. [docs/build.md](docs/build.md#validation) says what it checks, and [docs/provisioning.md](docs/provisioning.md#validation) what it doesn't prove.
- shfmt reads its options from `.editorconfig`, so run it without formatting flags: any flag such as `-i` makes it ignore `.editorconfig`.

To test a real first boot, install a throwaway instance as the README's [Testing a change](README.md#testing-a-change) describes.

## CI and releases

- **Pull requests:** every pull request to `main` that changes more than docs runs the checks above. Claude then reviews the change by [REVIEW.md](REVIEW.md) and comments on the pull request. A pull request merges once CI passes and every review thread is resolved. [docs/ci.md](docs/ci.md) describes each job.
- **Releases:** every push to `main` that changes more than docs builds and validates the config again. When the built files differ from the latest release's, it installs an instance on Windows runners, with and without a user, checks what the config set up and publishes a `vX.Y.Z` release with the files. The commits that change `src/` decide the version. [docs/releases.md](docs/releases.md) describes how.
