# Contributing

How changes reach this repository, how to set up and run the checks, and what CI and the release workflow run.

## Issues and pull requests

Issues and pull requests are limited to the repository's collaborators. The config runs as root on the collaborators' own machines, so every change comes from someone they trust.

You're free to use the config as it is, or to fork the repository and change your copy. A fork doesn't need anything from this repository: it's [MIT licensed](LICENSE).

## How changes land

- `main` is protected. Every change goes through a pull request from a short-lived branch, and is squash-merged.
- Branches are named `feature/<slug>`, `bugfix/<slug>` or `other/<slug>`, with a lowercase, hyphenated slug.
- Commit messages and pull request titles follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat(cloud-init): Install tree`. A pull request's title and description become its commit on `main`, so write them as a commit header and body. Mark a breaking change with `!` in the title.
- Keep each pull request to one change. Rebase a branch on `main` to bring it up to date. Don't merge `main` into it.

## Set up

Work on a current Ubuntu, or in a WSL instance built from this config, so the build uses a cloud-init close to the instance's. Install the tools from apt:

```sh
sudo apt-get install cloud-init make shellcheck shfmt
```

## Checks

Run these from the repository's root:

```sh
make build
shellcheck .github/scripts/*.sh
shfmt -d .
```

- `make build` joins every fragment in `src/fragments/`, in the order of their numbers, into `dist/Ubuntu.user-data`. It only rebuilds it when a fragment is added, changed, removed or renamed, or the `Makefile` changes, and the same fragments build the same file with the same cloud-init. `make clean` deletes `dist/`. Edit `src/fragments/`, never `dist/`.
- There are no unit tests, and nothing validates the rendered user-data. [docs/build.md](docs/build.md#validation) says what `make build` does and doesn't check.
- shfmt reads its options from `.editorconfig`, so run it without formatting flags: any flag such as `-i` makes it ignore `.editorconfig`.

To test a real first boot, install a throwaway instance as the README's [Testing a change](README.md#testing-a-change) describes.

## CI and releases

- **Pull requests:** every pull request to `main` that changes more than docs runs the checks above in `ci.yml`. Claude then reviews the change by [REVIEW.md](REVIEW.md) and comments on the pull request. A pull request merges once CI passes and every review thread is resolved. [docs/ci.md](docs/ci.md) describes each job.
- **Releases:** every push to `main` that changes more than docs runs `release.yml`. It builds the user-data and, when its SHA-1 differs from the latest release's, installs an instance from it on Windows runners and publishes it as a GitHub release, tagged with the commit's date and short SHA. There's no version to bump. [docs/releases.md](docs/releases.md) describes it.
