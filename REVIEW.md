# Review instructions

What CI's Claude code review flags on pull requests (PRs) in this repository, at what severity and what it skips. Rules for all work are in `CLAUDE.md`, and a change that breaks one of them is a finding. This file adds only what's specific to reviews.

Judge the config in `src/` as what ships: people copy it onto their own machines, where it runs as root on an instance's first boot. Judge the validator, the end-to-end scripts and the CI workflow by whether they still check the config correctly, not by the standards of the config itself.

## What Important means here

Mark a finding Important only when the change would do one of these:

- Make the user-data fail to render, fail `cloud-init schema` or fail on a first boot. For example: a package name Ubuntu 26.04 doesn't have, which fails the whole package install; a Jinja tag that isn't at column 0; `{{`, `{%` or `{#` inside embedded shell; a `users` or non-deferred `write_files` entry that needs a package or a group a package creates; `power_state` or `package_reboot_if_required`; `systemctl --user` in `runcmd`; or a `[user]` or `[time]` section in `/etc/wsl.conf`. `.claude/rules/cloud-init.md` lists the facts behind these.
- Let a meta-data value reach a shell command without the validation `docs/meta-data.md` describes, write a value into `~/.gitconfig` without the `gitval` macro, or report a rejected value other than with `printf %s` and an ASCII-escaped `tojson`.
- Add a meta-data key or a conditional block without a case in `tests/validate-user-data.sh`, including the case where the key is unset.
- Put identifying data into the repository, such as a real name, email, username, signing key, hostname or `/mnt/c/Users/<name>/` path. The repository is public, and identifying values belong in the user's meta-data.
- Fetch something at boot over plain HTTP, run a downloaded script as root that could run as the user, or replace the embedded GitHub CLI apt key with one fetched at boot.
- Change the `packages` list without keeping it in step with the dotfiles modules' dependencies, as `CLAUDE.md` says.
- Make the README's install steps wrong, or make a design doc, the README, `CONTRIBUTING.md`, `CLAUDE.md` or this file say something about the code that's false after the change, so that someone following it would do the wrong thing.
- Make CI skip a check that the change needs, such as a path added to `paths-ignore` in `.github/workflows/ci.yml` that the checks read or that changes what an instance runs. Drop or narrow a check that the `checks` or `e2e` job runs, or let a job run when one it needs failed. `docs/ci.md` describes how CI should work.
- Widen what the Claude run in CI can do, such as its `permissions`, its `github_token`, its `--allowedTools` or its `--disallowedTools`, past what the "Security" section of `docs/ci.md` allows, even when the change updates that doc too. Give `CLAUDE_CODE_OAUTH_TOKEN`, or a token that can write, to a step that runs the PR's code.
- Use an action without pinning it to a full commit SHA with its version in a comment, pin one to a release less than 7 days old, or shorten the 7-day Dependabot cooldown.

Naming, structure, refactoring ideas, comments and doc wording are Nits at most.

## Pre-existing issues

Don't report an issue that was there before this PR, however serious. It's out of scope for the PR.

## Cap the Nits

Every comment must be resolved before the PR can merge, so report Nits sparingly: at most three per review, and only ones likely to mislead a maintainer or a Claude agent working from the docs. On a review after new commits, report Nits only on code those commits change. CI's code review posts none from the fourth review on a PR, as the "Code review" section of `docs/ci.md` says.

## Don't report

- Anything ShellCheck, shfmt or `tests/validate-user-data.sh` reports. CI runs them before the review.
- The PR's title and description.
- A limit that a design doc's Limits section records, unless the change makes it worse.
- An issue that a resolved review thread on the PR already raises, whatever its replies say. Resolving a thread settles it.

## Always check

These are the rules that no tool, test or check enforces.

### The config

- A new `runcmd` entry that installs something for the user runs with `runuser -l <user>`, so `HOME` is the user's, and uses the tool's official installer, so the tool can update itself.
- Each install in `runcmd` is its own entry, so one failure doesn't stop the rest.
- A new `write_files` entry in the user's home is deferred, because `write_files` runs before `users` creates the user.
- A new user-facing behaviour is in the README's "What it sets up" and in `docs/provisioning.md`.
- Something new the user-data sets up has a check in `.github/scripts/check-instance.sh`. A missing check is a Nit.

### CI

- A new job in `ci.yml` needs the jobs whose results it depends on, so it doesn't run after one of them failed.
- A new path that the checks read, or that changes what an instance runs, isn't covered by `paths-ignore` in `ci.yml`.
- A change to this file's severities, its Nit cap or what it says about pre-existing issues also changes the code review's prompt in `.github/workflows/ci.yml`, and the other way round.

## Evidence

- Cite a `file:line` in this repository for every claim about behaviour. Don't infer behaviour from a name.
- A review doesn't run cloud-init, WSL or the tests. Claim that something would fail on a first boot only when the code, a design doc or `.claude/rules/cloud-init.md` shows why.
