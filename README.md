# ghops

![PyPI](https://img.shields.io/pypi/v/ghops)
![License](https://img.shields.io/pypi/l/ghops)
![Python Version](https://img.shields.io/pypi/pyversions/ghops)

ghops is a powerful command-line tool to streamline the management of your GitHub repositories. Whether you need to clone multiple repositories, keep them updated, or check their statuses, ghops provides an intuitive interface with rich, informative outputs.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Clone Repositories (`get`)](#clone-repositories-get)
  - [Update Repositories (`update`)](#update-repositories-update)
  - [Check Status (`status`)](#check-status-status)
- [Examples](#examples)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Clone Multiple Repositories**: Easily clone repositories from multiple GitHub users or organizations.
- **Update Repositories**: Automatically commit, pull, handle merge conflicts, and push changes across all your repositories.
- **Check Status**: Get a comprehensive overview of the status of all your repositories in either table or JSON format.
- **Rich Console Output**: Utilizes the `rich` library for enhanced, readable console outputs.
- **Dry Run Mode**: Simulate actions without making any changes, perfect for testing.
- **Conflict Resolution**: Automatically resolve merge conflicts using predefined strategies.
- **Progress Indicators**: Visual progress bars to track operations in real-time.

## Prerequisites

Before installing ghops, ensure you have the following installed:

- **Python 3.7 or higher**
- **Git**: [Download Git](https://git-scm.com/downloads)
- **GitHub CLI (`gh`)**: [Install GitHub CLI](https://cli.github.com/)

> **Note**: ghops relies on the GitHub CLI (`gh`) for interacting with GitHub APIs. Make sure you are authenticated using `gh auth login` before using the tool.

## Installation

You can install ghops via `pip`:

```bash
pip install ghops
```

Alternatively, you can install it from the source:

```bash
git clone https://github.com/queelius/ghops.git
cd ghops
pip install .
```

## Usage

ghops provides three main subcommands:

1. [`get`](#clone-repositories-get): Clone repositories from specified GitHub users or organizations.
2. [`update`](#update-repositories-update): Update all cloned repositories by committing, pulling, and pushing changes.
3. [`status`](#check-status-status): Display the current status of all repositories.

### Clone Repositories (`get`)

Clone repositories from GitHub users or organizations.

#### Syntax

```bash
ghops get [users ...] [options]
```

#### Options

- `users`: List of GitHub usernames or organization names to clone repositories from. If omitted, defaults to the authenticated user.
- `--ignore`: List of repository names to ignore.
- `--limit`: Maximum number of repositories to fetch per user/org (default: `1000`).
- `--dry-run`: Simulate actions without making any changes.
- `--dir`: Directory to clone repositories into (default: current directory).
- `--visibility`: Repository visibility (`all`, `public`, `private`; default: `all`).

### Update Repositories (`update`)

Update all cloned Git repositories by committing changes, pulling the latest updates, handling conflicts, and pushing changes.

#### Syntax

```bash
ghops update [options]
```

#### Options

- `--auto-commit`: Automatically commit changes before pulling.
- `--commit-message`: Custom commit message for auto-commits (default: `"Auto-commit from update script"`).
- `--auto-resolve-conflicts`: Automatically resolve merge conflicts (`abort`, `ours`, `theirs`).
- `--prompt`: Prompt before pushing changes.
- `--ignore`: List of repositories to ignore.
- `--dry-run`: Simulate actions without making any changes.
- `--dir`: Base directory to search for Git repositories (default: current directory).
- `--recursive`: Recursively search for Git repositories.

### Check Status (`status`)

Display the current status of all Git repositories in a specified directory.

#### Syntax

```bash
ghops status [options]
```

#### Options

- `--json`: Output statistics in JSON format (default: table format).
- `--recursive`: Recursively search for Git repositories.
- `--dir`: Directory to search for Git repositories (default: current directory).

## Examples

### Clone Repositories from Multiple Users

```bash
ghops get user1 user2 org1 --dir ~/projects/github --ignore repo-to-ignore --limit 50
```

### Update All Repositories with Automatic Commits and Conflict Resolution

```bash
ghops update --auto-commit --commit-message "Sync changes" --auto-resolve-conflicts theirs --dir ~/projects/github --recursive
```

### Check the Status of All Repositories in JSON Format

```bash
ghops status --json --dir ~/projects/github --recursive
```

### Perform a Dry Run of Cloning Repositories

```bash
ghops get user1 --dry-run --dir ~/projects/github
```

## Configuration

### Authentication

Ensure you are authenticated with GitHub CLI before using ghops:

```bash
gh auth login
```

### Environment Variables

- `GITHUB_TOKEN`: You can set a GitHub personal access token via the `GITHUB_TOKEN` environment variable for authentication if needed.

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. **Fork the repository**: [https://github.com/queelius/ghops/fork](https://github.com/queelius/ghops/fork)
2. **Create a feature branch**:

    ```bash
    git checkout -b feature/YourFeature
    ```

3. **Commit your changes**:

    ```bash
    git commit -m "Add your feature"
    ```

4. **Push to the branch**:

    ```bash
    git push origin feature/YourFeature
    ```

5. **Open a Pull Request**: Describe your changes and submit.

### Reporting Issues

If you encounter any issues or have suggestions, please [open an issue](https://github.com/queelius/ghops/issues).

## License

This project is licensed under the [MIT License](LICENSE).

---

© 2025 [Alex Towell](https://github.com/queelius)