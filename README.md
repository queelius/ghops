# `ghops` - GitHub Operations

**A Python CLI tool for cloning, updating, and managing multiple GitHub repositories at once.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## Overview

`ghops` is a command-line utility that wraps Git and GitHub CLI (`gh`) commands to automate common repo-management tasks. It can:

- **Clone** repositories from one or more GitHub users or organizations.
- **Update** local repositories (commit changes, pull, handle merge conflicts, and optionally push).
- **Display status** for a batch of repos, with optional JSON output.

It's designed to help you automate your daily Git operations in bulk, especially if you juggle many repositories at once.

## Features

- **Bulk repository cloning** from multiple users or organizations.
- **Selective ignoring** of repositories you don't want to touch.
- **Dry-run mode** to preview actions before actually running them.
- **Auto-commit** local changes with a custom commit message.
- **Auto-resolve** merge conflicts with simple strategies (`ours`, `theirs`, or `abort`).
- **Optional interactive prompts** before pushing.
- **Rich** command-line output with optional JSON for machine parsing.

## Installation

> **Prerequisite**: You must have the [`gh` CLI](https://github.com/cli/cli) and [Git](https://git-scm.com/) installed.  
> **Python**: Version 3.7 or later is recommended.

Once published to PyPI, you can install with:

```bash
pip install ghops
```

(If you’re not planning to publish on PyPI yet, you can still install locally:)

```bash
git clone https://github.com/<username>/ghops.git
cd ghops
pip install .
```

## Usage

`ghops` has three main subcommands: `get`, `update`, and `status`.

```bash
ghops [GLOBAL_OPTIONS] <subcommand> [SUBCOMMAND_OPTIONS]
```

### 1. `get`
Clone repositories from GitHub users or organizations:
```bash
ghops get [user1 user2 ...] [--ignore repo1 repo2 ...] [--limit N] [--dry-run] [--dir /path/to/clone]
```

- **`users`**: GitHub usernames or orgs to clone from. If none is provided, it defaults to the authenticated user.
- **`--ignore`**: Space-separated list of repo names to skip.
- **`--limit`**: Maximum number of repos to fetch per user/org (default `1000`).
- **`--dry-run`**: Print out what would happen but do not perform any actions.
- **`--dir`**: Directory to clone into (default is the current directory).

### 2. `update`
Update all Git repositories within a directory:
```bash
ghops update [--auto-commit] [--commit-message "Your message"] [--auto-resolve-conflicts abort|ours|theirs]
             [--prompt] [--ignore repo1 repo2 ...] [--dry-run] [--dir /path/to/repos] [--recursive]
```

- **`--auto-commit`**: Automatically commit local changes before pulling.
- **`--commit-message`**: Set a custom commit message for auto-commits.
- **`--auto-resolve-conflicts`**: Merge-conflict strategy: `abort`, `ours`, or `theirs`.
- **`--prompt`**: Prompt interactively before pushing changes.
- **`--ignore`**: Space-separated list of repo names to skip.
- **`--dry-run`**: Show what would happen without changing anything.
- **`--dir`**: Directory to look for Git repositories (default `.`).
- **`--recursive`**: Recursively search for repositories in all subdirectories.

### 3. `status`
Display the Git status of each repository within a directory:
```bash
ghops status [--json] [--recursive] [--dir /path/to/repos]
```

- **`--json`**: Output the repo statuses in JSON instead of a table.
- **`--recursive`**: Recursively find repos within subdirectories.
- **`--dir`**: Base directory to search (default `.`).

## Examples

1. **Clone repos** from user `octocat`, ignoring two specific repos, into a new folder:
   ```bash
   ghops get octocat --ignore some-repo another-repo --dir my-github-repos
   ```
2. **Recursively update** all repos in `my-github-repos`, auto-committing any local changes:
   ```bash
   ghops update --auto-commit --commit-message "update from ghops" --dir my-github-repos --recursive
   ```
3. **Check status** of all repos (top-level only) in a directory:
   ```bash
   ghops status --dir my-github-repos
   ```

## Contributing

1. Fork this repository and clone your fork.
2. Create a new branch for your feature or bugfix.
3. Make your changes and test thoroughly.
4. Submit a pull request!

## License

This project is [MIT Licensed](./LICENSE). Feel free to fork, modify, and use it in your own projects.
