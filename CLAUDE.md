# WSL

A reusable cloud-init config that builds an Ubuntu WSL instance for development from scratch. The repository is public, and people copy from it, so it stays generic.

## Contents

1. [Layout](#layout)
1. [Conventions](#conventions)
1. [Contributing](#contributing)

## Layout

| Path | Holds |
| --- | --- |
| `README.md` | The entry point for people who use the config |
| `CONTRIBUTING.md` | Who can open issues and pull requests, and how changes land |
| `.editorconfig`, `.gitattributes` | Editor settings, and LF line endings for every file |

## Conventions

- **Never commit identifying data.** No real names, emails, usernames, signing keys, hostnames or `/mnt/c/Users/<name>/` paths in any file. Use placeholders such as `<you>` or `jdoe` in examples.
- Write in British English.

## Contributing

| Repository | Path | GitHub | Visibility | Default branch | Kind |
| --- | --- | --- | --- | --- | --- |
| Source | `.` | `froazin/wsl` | Public | `main` | Code: PRs, squash-merged |

- **Commit scopes:** `cloud-init`, `wslconfig`, `ci`, `docs`, `claude`, `deps`.
- **Feature flags:** none.
- **Releases:** none. `main` is what people copy.
- **CI:** none yet.
- User docs live in `README.md`. The repository has no wiki.
- Issues and pull requests are limited to collaborators, because the config runs as root on their machines.
