# Releases

How [`.github/workflows/release.yml`](../.github/workflows/release.yml) releases the user-data from `main`: when a release is due, how its version is worked out, the end-to-end test on a Windows runner and the tag and asset it publishes. It's for engineers changing the workflow or the end-to-end scripts in [`.github/scripts/`](../.github/scripts/).

## Contents

1. [Overview](#overview)
1. [When a release is due](#when-a-release-is-due)
1. [How the version is decided](#how-the-version-is-decided)
1. [Tags and assets](#tags-and-assets)
1. [End-to-end tests](#end-to-end-tests)
1. [Security](#security)
1. [Decisions](#decisions)
1. [Limits](#limits)
1. [Sources](#sources)

## Overview

The workflow runs on every push to `main`, with the same `paths` filter as [CI](ci.md#overview), so a docs-only push runs nothing. Runs share the `release` concurrency group: a run waits for the one in progress, and a newer push replaces a run that's still waiting, so two releases never race. The `release` job only publishes from the newest run of the workflow, because a newer run releases the same changes. A docs-only push starts no run, so it doesn't hold a release back. This flowchart shows the jobs:

```mermaid
flowchart LR
    accTitle: The jobs that release the user-data
    accDescr: A push to main that changes more than docs starts the workflow. The build job runs the CI checks, then compares the built user-data's SHA-1 with the latest release's. When they differ, the e2e job installs an Ubuntu instance on a Windows runner with the built user-data. When it passes, the release job creates a tag with the version commitizen works out, and a GitHub release with the user-data as its only asset.
    push["Push to main"] -->|"not only docs"| build["build: make build, ShellCheck, shfmt, sha1sum, cz"]
    latest[("Latest release")] -->|"its Ubuntu.user-data"| build
    build -->|"SHA-1 differs, user-data as an artifact"| e2e["e2e: windows-2025"]
    build -->|"same SHA-1"| stop["Nothing to release"]
    e2e -->|passed| release["release: gh release create"]
    release -->|"tag vX.Y.Z and Ubuntu.user-data"| latest
```

- **`build`** checks out the whole history, sets up the tools as the CI `checks` job does and adds commitizen. It runs the same checks, `make build`, ShellCheck and shfmt, so a push straight to `main` is checked too, and a failed check releases nothing. The code review runs only on pull requests, in CI. The job then compares the user-data with the latest release's, as [When a release is due](#when-a-release-is-due) describes. When a release is due, it works out the version, as [How the version is decided](#how-the-version-is-decided) describes, outputs the tag and uploads `dist/Ubuntu.user-data` as the `dist` artifact. Otherwise it outputs no tag, and the later jobs are skipped.
- **`e2e`** runs only when a release is due. See [End-to-end tests](#end-to-end-tests).
- **`release`** needs both, so a failed build or end-to-end test skips it. It checks it's the newest run with `gh run list`, then downloads the artifact and runs `gh release create "$TAG" dist/Ubuntu.user-data --target "$GITHUB_SHA" --generate-notes`.

## When a release is due

Nobody decides when to release, or bumps a version by hand. A release is due when the user-data changes:

1. The build is reproducible: it replaces make-mime's random MIME boundary with a fixed one, as [Build](build.md#how-the-build-works) describes, so the same fragments build the same file with the same cloud-init.
1. The `build` job takes the SHA-1 of `dist/Ubuntu.user-data` with `sha1sum`.
1. When a release exists, it downloads the latest release's `Ubuntu.user-data` with `gh release download`, and takes its SHA-1 the same way. Before the first release, there's nothing to compare with.
1. When the two SHA-1s match, nothing has changed for users, and there's nothing to release. Otherwise a release is due.

So any change to a fragment, or a change to the `Makefile` that changes its output, makes a release, and any other change, such as to CI, the end-to-end scripts or the README, makes none. That holds while the latest release has the current user-data: after a release that didn't go out, such as after a failed end-to-end test, any later push that changes more than docs tries again. Nobody has to decide whether a change makes a release. Any failure to read the latest release fails the job, so a release is never made because it couldn't be read.

## How the version is decided

When a release is due, the `build` job works out its version with [commitizen](https://commitizen-tools.github.io/commitizen/), from Ubuntu's archive, using the settings in [`.cz.toml`](../.cz.toml). It runs `cz bump --get-next --yes --allow-no-commit`, which only prints the version. commitizen reads the Conventional Commit headers since the latest `v` tag, which are the squash-merged pull requests' titles, so a pull request's title decides its bump:

| Title | Bump before `v1.0.0` | Bump from `v1.0.0` |
| --- | --- | --- |
| Any type with `!` | Minor | Major |
| `feat` | Minor | Minor |
| `fix`, `perf`, `refactor` or anything else | Patch | Patch |

- `version_provider = "scm"` reads the current version from the latest tag, so no file holds a version. The `build` job checks out the whole history for this.
- `major_version_zero = true` keeps a breaking change to a minor bump before `v1.0.0`. Remove it in the change that moves the project to `v1.0.0`, because commitizen 4.11.0 keeps applying it at `1.x` (observed).
- `--allow-no-commit` makes a release whose commits are all of a type with no bump, such as `chore` or `ci`, a patch. A release is only due when the user-data has changed, so it always gets a new version.
- `--yes` answers the question commitizen asks when there's no tag yet. Without it, the command waits for input (observed).
- The first release is `v0.1.0`. With no tags, commitizen counts from `0.0.0`, and the history's `feat` commits give `0.1.0` (observed). The job never releases below `v0.1.0`.
- Choose a pull request's type by what it changes: `feat` for something new an instance sets up, `fix`, `perf` or `refactor` for other changes to the user-data, and `docs`, `ci`, `test` or `chore` for changes that leave it alone. Mark a breaking change with `!`, such as a change that makes users change their meta-data. To preview the next version, run the same command in a clone with the tags.

## Tags and assets

- The tag is `v` and the version, such as `v0.1.0`, as [How the version is decided](#how-the-version-is-decided) describes. GitHub creates it on the commit the run built, through `gh release create --target`. The release notes are GitHub's generated notes.
- The only asset is `Ubuntu.user-data`. The README downloads it from `https://github.com/froazin/wsl/releases/latest/download/Ubuntu.user-data`.
- No meta-data is released. Users write their own from the README's [meta-data example](../README.md#the-meta-data-example).
- The user-data's parts are base64 in the MIME file, so the README sends readers to the fragments in `src/` at the release's tag to read them.

## End-to-end tests

The `e2e` job installs an instance the way the README tells users to, `wsl --install Ubuntu`, on a raw `windows-2025` runner, which comes with WSL, with the user-data the `build` job made. It runs under WSL's default settings, with no `.wslconfig`, because the README's `.wslconfig` is an optional example. Its meta-data is the README's example with `username`, `git_name` and `git_email` filled in from the job's `E2E_USER`, `E2E_GIT_NAME` and `E2E_GIT_EMAIL`.

Each step is a script in `.github/scripts/`:

1. **`seed-cloud-init.ps1`** copies the user-data to `%USERPROFILE%\.cloud-init\Ubuntu.user-data`, and writes the README's meta-data example there as `Ubuntu.meta-data`, with those values filled into its empty keys. It finds the example by the `<!-- meta-data example -->` comment before it, and fails when the comment, the block or an empty key the test fills in is missing. [WSL meta-data](meta-data.md#overview) says what the example must keep.
1. **`install-instance.ps1`** runs `wsl --install Ubuntu --no-launch --web-download`.
1. **`wait-for-cloud-init.ps1`** runs `cloud-init status --wait` as root, which boots the instance for the first time, then shows cloud-init's status and logs. It fails if cloud-init didn't use the WSL datasource, or reports any error or recoverable error. A recoverable error that every instance gets, listed in `$expected`, is only logged.
1. **`restart-instance.ps1`** runs `wsl --terminate`, as the README says to, then fails unless `systemctl is-system-running --wait` says `running`.
1. **`check-instance.ps1`** runs [`check-instance.sh`](../.github/scripts/check-instance.sh) as root inside the instance. It checks the system files, packages, links, units, shells and dotfiles, and the user, their groups, git config, tools and gh extension. WSL attaches swap by default, so its `swap is off` check tests `disable-swap.service`.

`runcmd` doesn't stop at a failing entry, and cloud-init only sees the exit status of the last one, so `check-instance.sh` is what catches a failed install.

## Security

- **One job can write.** The workflow's token can only read, except in `release`, which has `contents: write`. `release` has no checkout and runs no repository code: it publishes the user-data the `build` job made and the end-to-end tests passed.
- **No credentials on disk.** Every checkout sets `persist-credentials: false`. `build` gives `gh` the read-only workflow token to read the latest release.
- **Pinned actions.** Every action is pinned to a full commit SHA, with its version in a comment.

## Decisions

- **The user-data's hash decides when, the commits decide the version.** A release is due exactly when what users download changes, and its version comes from the pull requests' titles, so nobody bumps a version by hand. A change to the `Makefile` that builds the same file makes no release.
- **The CI checks on `main` too.** A change pushed straight to `main` skips CI, so the `build` job lints it before anything is released. The code review stays in CI, where it can comment on a pull request.
- **SHA-1 with `sha1sum`.** It only has to tell two builds apart, not resist an attacker, and `sha1sum` is on every runner.
- **commitizen from Ubuntu's archive.** It's installed with apt, like the build's tools, and works out a Semantic Versioning version from the Conventional Commit headers the project already writes. Tools such as svu and git-cliff would have to be downloaded and pinned by hand.
- **End-to-end tests before a release, not on each pull request.** They take a long time on Windows runners, and only what's released reaches users.
- **A raw runner, not a setup action.** The `e2e` job installs the instance with `wsl.exe` as a user would, so it tests the README's steps rather than an action's.
- **The README's example, filled in.** The `e2e` job fills in the meta-data example users copy rather than using a fixture, so its defaults, such as the gh extension, are tested too.
- **Fail on recoverable errors.** A deprecated key or a schema warning means user-data that needs fixing. The exception is the network wait that every instance gets, which [Provisioning](provisioning.md#limits) explains. It's logged rather than annotated, so the run's annotations only show something to act on.
- **The tag from GitHub's API.** The `release` job needs no checkout or Git credentials to create it.

## Limits

- The tests install whatever release of Ubuntu the Store's `Ubuntu` is, so they move to a new release of Ubuntu when the Store does, without a change here.
- A new cloud-init on the runner that changes make-mime's output, but not the fragments, makes a release.
- commitizen bumps by the titles alone. A title whose type doesn't match the change, such as `feat` for a refactor, gives the wrong bump.
- The tag GitHub creates isn't signed by a maintainer's key.
- A newer run that's cancelled by hand, rather than replaced by a newer push, takes its release with it. Re-run it to release.
- A failed end-to-end test on `main` blocks the release. The next push that changes more than docs still builds a user-data that differs from the latest release, so it runs the tests again, and releases when they pass.
- The user-data's parts are base64, so a release's user-data can't be read or diffed as text.
- A change to the end-to-end scripts, or to the README's meta-data example, isn't tested on a first boot until the next release.
- The test always fills in a `username`, so nothing boots an instance with the `wsluser` default. Each fragment sets it on the same line, so it's checked by reading.
- The end-to-end tests run a command as root for the first boot, which skips Ubuntu's first-run setup. That setup writes the default user to `/etc/wsl.conf`, so it isn't tested.
- VS Code and the other Windows tools aren't on the runner, so their links are checked but the VS Code extension installs are skipped. Mirrored networking isn't tested.
- The end-to-end tests download Ubuntu and every package on each run, so they take a while and depend on those servers.

## Sources

- https://commitizen-tools.github.io/commitizen/commands/bump/
- https://commitizen-tools.github.io/commitizen/config/version_provider/
- https://cli.github.com/manual/gh_release_create
- https://cli.github.com/manual/gh_release_download
- https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases
- https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- https://cloudinit.readthedocs.io/en/latest/reference/cli.html#status
- https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md
