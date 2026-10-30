# Contributing

How changes reach this repository, the checks to run before you open a pull request, and what to do if you want to change the config yourself.

## Issues and pull requests

Issues and pull requests are limited to the repository's collaborators. The config runs as root on the collaborators' own machines, so every change comes from someone they trust.

You're free to use the config as it is, or to fork the repository and change your copy. A fork doesn't need anything from this repository: it's [MIT licensed](LICENSE).

## How changes land

- `main` is protected. Every change goes through a pull request from a short-lived branch, and is squash-merged.
- Branches are named `feature/<slug>`, `bugfix/<slug>` or `other/<slug>`, with a lowercase, hyphenated slug.
- Commit messages and pull request titles follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), such as `feat(cloud-init): Install tree`. A pull request's title and description become its commit on `main`, so write them as a commit header and body.
- Keep each pull request to one change. Rebase a branch on `main` to bring it up to date. Don't merge `main` into it.

## Checks

Run these from the repository's root on Ubuntu 26.04, or in a WSL instance built from this config. They need `cloud-init`, `python3` with PyYAML, `git`, `shellcheck`, `shfmt` and `ssh-keygen`:

```sh
shellcheck tests/*.sh
shfmt -d .
tests/validate-user-data.sh
```

shfmt reads its options from `.editorconfig`, so run it without formatting flags: any flag such as `-i` makes it ignore `.editorconfig`.

`tests/validate-user-data.sh` renders the user-data with `cloud-init devel render` against mock meta-data, runs `cloud-init schema` on each result and checks it. It exits 0 when every case passes, 1 when a case fails and 2 when it can't run. Add a case for every new meta-data key or conditional, including the key being unset. [docs/provisioning.md](docs/provisioning.md#validation) says what it does and doesn't prove.

To test a real first boot, install a throwaway instance as the README's [Testing a change](README.md#testing-a-change) describes.
