# Usage

`ghops` is a command-line tool with several subcommands. You can get help for any command by running `ghops <command> --help`.

## `get`

Clone repositories from GitHub users or organizations.

```bash
ghops get [users ...] [options]
```

### Options

| Option | Description |
| --- | --- |
| `users` | GitHub users or organizations to fetch from. Defaults to the authenticated user. |
| `-d`, `--dir` | Directory to clone into. Defaults to the current directory. |
| `-l`, `--limit` | Max number of repos to fetch. Defaults to 100. |
| `-i`, `--ignore` | Repositories to ignore. |
| `--dry-run` | Simulate actions without making changes. |
| `--add-license` | Add a LICENSE file to cloned repos. |
| `--license` | License to use (e.g., `mit`, `gpl-3.0`). Defaults to `mit`. |
| `--author` | Author name for the license. |
| `--email` | Author email for the license. |
| `--year` | Year for the license. |
| `-f`, `--force` | Force overwrite of existing LICENSE file. |

## `update`

Update local repositories.

```bash
ghops update [options]
```

### Options

| Option | Description |
| --- | --- |
| `-d`, `--dir` | Directory to search for repos. Defaults to the current directory. |
| `-r`, `--recursive` | Search for repos recursively. |
| `-i`, `--ignore` | Repositories to ignore. |
| `--auto-commit` | Automatically commit changes before pulling. |
| `--commit-message` | Commit message for auto-commits. |
| `--auto-resolve-conflicts` | How to resolve merge conflicts (`ours`, `theirs`, `abort`). |
| `--prompt` | Prompt before pushing changes. |
| `--dry-run` | Simulate actions without making changes. |
| `--add-license` | Add a LICENSE file to cloned repos. |
| `--license` | License to use (e.g., `mit`, `gpl-3.0`). Defaults to `mit`. |
| `--author` | Author name for the license. |
| `--email` | Author email for the license. |
| `--year` | Year for the license. |
| `-f`, `--force` | Force overwrite of existing LICENSE file. |

## `status`

Show status of local repositories.

```bash
ghops status [options]
```

### Options

| Option | Description |
| --- | --- |
| `-d`, `--dir` | Directory to search for repos. Defaults to the current directory. |
| `-r`, `--recursive` | Search for repos recursively. |
| `--json` | Output in JSON format. |
| `--license-details` | Show detailed license information. |

## `license`

Manage LICENSE files.

```bash
ghops license [options]
```

### Options

| Option | Description |
| --- | --- |
| `--list` | List available licenses. |
| `--show` | Show a specific license template. |
| `--json` | Output in JSON format. |

