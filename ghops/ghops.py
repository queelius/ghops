#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.json import JSON
from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table

# Initialize Rich Console
console = Console()

# Configure logging to use RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger("rich")

# Summary statistics
stats = {
    "cloned": 0,
    "skipped": 0,
    "updated": 0,
    "committed": 0,
    "pulled": 0,
    "pushed": 0,
    "conflicts": 0,
    "conflicts_resolved": 0
}


def run_command(cmd, repo_path=None, dry_run=False, capture_output=False):
    """
    Runs a shell command, optionally in a specific directory.

    Args:
        cmd (str): The command to execute.
        repo_path (str, optional): The directory to execute the command in.
        dry_run (bool, optional): If True, only prints the command without executing.
        capture_output (bool, optional): If True, captures and returns the command's output.

    Returns:
        str or None: The captured output if capture_output is True, else None.
    """
    full_cmd = f'(cd "{repo_path}" && {cmd})' if repo_path else cmd
    if dry_run:
        logger.info(f"[Dry Run] {full_cmd}")
        return None
    else:
        logger.debug(f"Running command: {full_cmd}")
        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                shell=True,
                capture_output=capture_output,
                text=True,
                check=True
            )
            if capture_output:
                output = result.stdout.strip()
                logger.debug(f"Command output: {output}")
                return output
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing command: {cmd}\n{e.stderr}")
            return None


def is_git_repo(repo_path):
    """
    Checks if a directory is a Git repository.

    Args:
        repo_path (str): The directory path to check.

    Returns:
        bool: True if the directory is a Git repository, False otherwise.
    """
    return (Path(repo_path) / ".git").is_dir()


def get_github_repos(users, ignore_list, limit, dry_run, base_dir, visibility="all"):
    """
    Fetches repositories from GitHub users/orgs and clones them.

    Args:
        users (list): List of GitHub users or organizations.
        ignore_list (list): List of repository names to ignore.
        limit (int): Maximum number of repositories to fetch per user/org.
        dry_run (bool): If True, simulate actions without making changes.
        base_dir (str): Base directory to clone repositories into.
        visibility (str): Repository visibility ('all', 'public', 'private').
    """
    # Ensure the base directory exists
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(base_dir)

    with Progress() as progress:
        user_task = progress.add_task(f"[cyan]Fetching user repositories...", total=len(users))
        for user in users:
            user_display = user if user else "authenticated user"
            logger.debug(f"Fetching repositories for {user_display}...")
            user_query = user if user else ""
            repos_output = run_command(
                f'gh repo list {user_query} --limit {limit} --visibility {visibility} --json nameWithOwner --jq ".[].nameWithOwner"',
                capture_output=True,
                dry_run=dry_run)

            if not repos_output:
                logger.warning(f"No repositories found for {user_display}.")
                user_task.update(repo_task, advance=1)
                continue

            repos = repos_output.split("\n")
            repo_task = progress.add_task(f"[cyan]Fetching repositories for {user_display}...", total=len(repos))
            for repo in repos:
                repo_name = repo.split("/")[-1]
                if repo_name in ignore_list:
                    logger.info(f"Skipping ignored repo: {repo_name}")
                    stats["skipped"] += 1
                    continue

                repo_url = f"https://github.com/{repo}.git"
                clone_out = run_command(f'git clone "{repo_url}"', dry_run=dry_run, capture_output=True)
                if clone_out is not None:
                    stats["cloned"] += 1
                else:
                    logger.error(f"Failed to clone repository: {repo}")
                    stats["skipped"] += 1
                progress.update(repo_task, advance=1)

            progress.update(user_task, advance=1)


def get_git_status(repo_path):
    """
    Returns the current status of the git repo.

    Args:
        repo_path (str): Path to the Git repository.

    Returns:
        str or None: The output of 'git status --porcelain' or None if an error occurs.
    """
    return run_command("git status --porcelain", repo_path, capture_output=True)


def pull_repo(repo_path, dry_run):
    """
    Pulls the latest changes from the remote repository.

    Args:
        repo_path (str): Path to the Git repository.
        dry_run (bool): If True, simulate actions without making changes.
    """
    output = run_command("git pull --rebase --autostash", repo_path, dry_run, capture_output=True)
    if not output:
        logger.debug(f"No changes to pull in {repo_path}.")
        stats["skipped"] += 1
        return
    
    if "already up to date." not in output.lower() and "fast-forward" in output.lower():
        stats["pulled"] += 1
    else:
        logger.debug(f"No changes to pull in {repo_path}.")
        stats["skipped"] += 1        

def commit_changes(repo_path, message, dry_run):
    """
    Commits any uncommitted changes.

    Args:
        repo_path (str): Path to the Git repository.
        message (str): Commit message.
        dry_run (bool): If True, simulate actions without making changes.
    """
    status = get_git_status(repo_path)
    if not status:
        logger.debug(f"No changes to commit in {repo_path}.")
        stats["skipped"] += 1
        return
    
    add_output = run_command("git add -A", repo_path, dry_run, capture_output=True)
    if add_output:
        logger.debug(f"Added changes to staging area in {repo_path}.")
    output = run_command(f'git commit -m "{message}"', repo_path, dry_run, capture_output=True)
    if not output:
        logger.debug(f"No changes to commit in {repo_path}.")
        return

    if "nothing to commit" in output.lower():
        logger.debug(f"No changes were committed in {repo_path}.")
        stats["skipped"] += 1
    else:
        # Usually git commit shows something like:
        #   "[main abcd123] Auto-commit from update script
        #    1 file changed, 2 insertions(+), 0 deletions(-)"
        # so we can assume it's a real commit
        stats["committed"] += 1

def push_repo(repo_path, dry_run):
    """
    Pushes committed changes to the remote repository, only incrementing stats
    if there's actually something to push.
    """
    output = run_command("git push", repo_path, dry_run, capture_output=True)

    if not output:
        logger.debug(f"No changes to push in {repo_path}.")
        return

    # If "Everything up-to-date" or similar text is present, skip
    if "everything up-to-date" in output.lower() or "everything up to date" in output.lower():
        logger.debug(f"Nothing to push for {repo_path}.")
        stats["skipped"] += 1
    else:
        stats["pushed"] += 1

def handle_merge_conflicts(repo_path, strategy, dry_run):
    """
    Attempts to resolve merge conflicts if any.

    Args:
        repo_path (str): Path to the Git repository.
        strategy (str): Conflict resolution strategy ('abort', 'ours', 'theirs').
        dry_run (bool): If True, simulate actions without making changes.
    """
    conflicts = run_command("git ls-files -u", repo_path, capture_output=True)
    if conflicts:
        logger.warning(f"Merge conflicts detected in {repo_path}.")
        stats["conflicts"] += 1
        if strategy == "abort":
            logger.info("Aborting merge...")
            run_command("git merge --abort", repo_path, dry_run)
        elif strategy == "ours":
            logger.info("Resolving conflicts using 'ours' strategy...")
            run_command("git merge --strategy=ours", repo_path, dry_run)
            stats["conflicts_resolved"] += 1
        elif strategy == "theirs":
            logger.info("Resolving conflicts using 'theirs' strategy...")
            run_command("git checkout --theirs . && git add -A", repo_path, dry_run)
            run_command('git commit -m "Auto-resolved merge conflicts using theirs"', repo_path, dry_run)
            stats["conflicts_resolved"] += 1
        else:
            logger.warning("Leaving conflicts for manual resolution.")


def update_repo(repo_path, auto_commit, commit_message, auto_resolve_conflicts, prompt, dry_run):
    """
    Updates a single repo: commits, pulls, handles conflicts, and pushes.

    Args:
        repo_path (str): Path to the Git repository.
        auto_commit (bool): If True, automatically commit changes before pulling.
        commit_message (str): Commit message for auto-commits.
        auto_resolve_conflicts (str): Conflict resolution strategy.
        prompt (bool): If True, prompt before pushing changes.
        dry_run (bool): If True, simulate actions without making changes.
    """
    if auto_commit:
        commit_changes(repo_path, commit_message, dry_run)

    pull_repo(repo_path, dry_run)

    if auto_resolve_conflicts:
        handle_merge_conflicts(repo_path, auto_resolve_conflicts, dry_run)

    if prompt and not dry_run:
        confirm = input(f"Push changes for {repo_path}? [y/N]: ").strip().lower()
        if confirm != "y":
            logger.info(f"Skipping push for {repo_path}.")
            return

    push_repo(repo_path, dry_run)


def find_git_repos(base_dir, recursive):
    """
    Finds all git repositories in the given directory.

    Args:
        base_dir (str): Base directory to search.
        recursive (bool): If True, search recursively.

    Returns:
        list: List of paths to Git repositories.
    """
    git_repos = []
    if recursive:
        for root, dirs, files in os.walk(base_dir):
            if ".git" in dirs:
                git_repos.append(root)
                # Prevent descending into subdirectories of a git repo
                dirs[:] = [d for d in dirs if d != ".git"]
    else:
        for entry in os.scandir(base_dir):
            if entry.is_dir() and is_git_repo(entry.path):
                git_repos.append(entry.path)
    return git_repos


def update_all_repos(auto_commit, commit_message, auto_resolve_conflicts, prompt, ignore_list, dry_run, base_dir, recursive):
    """
    Finds all git repositories in the specified directory and updates them.

    Args:
        auto_commit (bool): If True, automatically commit changes before pulling.
        commit_message (str): Commit message for auto-commits.
        auto_resolve_conflicts (str): Conflict resolution strategy.
        prompt (bool): If True, prompt before pushing changes.
        ignore_list (list): List of repository names to ignore.
        dry_run (bool): If True, simulate actions without making changes.
        base_dir (str): Base directory to search for Git repositories.
        recursive (bool): If True, search recursively.
    """
    repo_dirs = find_git_repos(base_dir, recursive)

    if ignore_list:
        repo_dirs = [d for d in repo_dirs if os.path.basename(d) not in ignore_list]

    if not repo_dirs:
        logger.warning(f"No Git repositories found in '{base_dir}' with the given parameters.")
        return

    with Progress() as progress:
        task = progress.add_task("[cyan]Updating repos...", total=len(repo_dirs))
        for repo in repo_dirs:
            update_repo(repo, auto_commit, commit_message, auto_resolve_conflicts, prompt, dry_run)
            progress.update(task, advance=1)


def get_github_repos_into_dir(users, ignore_list, limit, dry_run, base_dir):
    """
    Fetches repositories from GitHub users/orgs and clones them into the specified directory.

    Args:
        users (list): List of GitHub users or organizations.
        ignore_list (list): List of repository names to ignore.
        limit (int): Maximum number of repositories to fetch per user/org.
        dry_run (bool): If True, simulate actions without making changes.
        base_dir (str): Base directory to clone repositories into.
    """
    # This function is identical to get_github_repos and can be removed or merged
    # For the sake of completeness, we'll keep it
    get_github_repos(users, ignore_list, limit, dry_run, base_dir)


def reset_stats():
    """
    Resets the summary statistics.
    """
    global stats
    stats = {
        "cloned": 0,
        "skipped": 0,
        "updated": 0,
        "committed": 0,
        "pulled": 0,
        "pushed": 0,
        "conflicts": 0,
        "conflicts_resolved": 0
    }


def display_summary():
    """
    Displays the operation summary using a Rich table.
    """
    table = Table(title="Operation Summary")
    table.add_column("Action", style="cyan", justify="right")
    table.add_column("Count", style="magenta", justify="right")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").capitalize(), str(value))

    console.print(table)


def display_repo_status(repo_stats, summary_stats, keys, json_output):
    """
    Displays the repository status either in JSON or table format.

    Args:
        repo_stats (dict): Detailed statistics of each repository.
        summary_stats (dict): Aggregated summary statistics.
        keys (list): List of keys for the table columns.
        json_output (bool): If True, output in JSON format.
    """
    if json_output:
        summary_key = "summary"
        while summary_key in repo_stats:
            # use a different name to avoid collision
            summary_key = f"_{summary_key}_"

        repo_stats[summary_key] = summary_stats
        console.print(JSON(json.dumps(repo_stats, indent=2)))
    else:
        table = Table(title="Repo Status")
        table.add_column("Repo", style="cyan", justify="right")
        for key in keys:
            if key == "remote_url":
                table.add_column("URL", style="cyan", justify="left")
            else:
                table.add_column(key.replace("_", " ").capitalize(), justify="left")

        for repo, data in repo_stats.items():
            for key in keys:
                if key == "remote_url" and data[key]:
                    data[key] = f"[link={data[key]}]Link[/link]"
                elif key == "path" and data[key]:
                    data[key] = f"[link=file://{data[key]}]{data[key]}[/link]"
                else:
                    data[key] = str(data[key]) if data[key] else ""

            row = [repo] + [data.get(key, "") for key in keys]
            table.add_row(*row)

        console.print(table)
        console.print("\n")
        console.print(f"[bold]Summary:[/bold]")
        summary_table = Table(show_header=False)
        for key, value in summary_stats.items():
            summary_table.add_row(key.replace("_", " ").capitalize(), str(value))
        console.print(summary_table)


def display_repo_status_table(repo_dirs, json_output):
    """
    Gathers and displays the status of all repositories.

    Args:
        repo_dirs (list): List of repository directories.
        json_output (bool): If True, output in JSON format.
    """
    if not repo_dirs:
        logger.warning(f"No Git repositories found in '{base_dir}'.")
        return

    repo_stats = {}
    summary_stats = {}
    keys = None
    for repo in repo_dirs:
        repo_name = os.path.basename(repo)
        status = get_git_status(repo)
        repo_status = status or ""
        has_conflicts = "CONFLICT" in repo_status
        has_uncommitted = " M " in repo_status
        has_untracked = "?? " in repo_status
        has_staged = "A  " in repo_status
        ahead = "ahead" in run_command("git status", repo, capture_output=True)
        behind = "behind" in run_command("git status", repo, capture_output=True)
        remote_url = run_command("git remote get-url origin", repo, capture_output=True)
        branch = run_command("git branch --show-current", repo, capture_output=True)
        last_commit = run_command("git log -1 --pretty=format:'%h - %s (%cr)'", repo, capture_output=True)

        repo_stats[repo_name] = {
            "status": repo_status,
            "path": repo,
            "has_conflicts": has_conflicts,
            "has_uncommitted": has_uncommitted,
            "has_untracked": has_untracked,
            "has_staged": has_staged,
            "has_ahead": ahead,
            "has_behind": behind,
            "remote_url": remote_url,
            "branch": branch,
            "last_commit": last_commit
        }

        summary_stats["total_repos"] = summary_stats.get("total_repos", 0) + 1
        summary_stats["has_conflicts"] = summary_stats.get("has_conflicts", 0) + int(has_conflicts)
        summary_stats["has_uncommitted"] = summary_stats.get("has_uncommitted", 0) + int(has_uncommitted)
        summary_stats["has_untracked"] = summary_stats.get("has_untracked", 0) + int(has_untracked)
        summary_stats["has_staged"] = summary_stats.get("has_staged", 0) + int(has_staged)
        summary_stats["has_ahead"] = summary_stats.get("has_ahead", 0) + int(ahead)
        summary_stats["has_behind"] = summary_stats.get("has_behind", 0) + int(behind)
        summary_stats["has_remote"] = summary_stats.get("has_remote", 0) + int(bool(remote_url))
        summary_stats["has_branch"] = summary_stats.get("has_branch", 0) + int(bool(branch))
        summary_stats["has_last_commit"] = summary_stats.get("has_last_commit", 0) + int(bool(last_commit))

        if not keys:
            keys = repo_stats[repo_name].keys()

    display_summary()  # Optionally display individual repo stats if needed
    # To display the status table, you can call display_repo_status
    # display_repo_status(repo_stats, summary_stats, keys, json_output)


def status_command(base_dir, json_output, recursive):
    """
    Handles the 'status' subcommand to display the status of Git repositories.

    Args:
        base_dir (str): Directory to search for Git repositories.
        json_output (bool): If True, output in JSON format.
        recursive (bool): If True, search recursively.
    """
    repo_dirs = find_git_repos(base_dir, recursive)

    if not repo_dirs:
        logger.warning(f"No Git repositories found in '{base_dir}'.")
        return

    repo_stats = {}
    summary_stats = {}
    keys = None
    for repo in repo_dirs:
        repo_name = os.path.basename(repo)
        status = get_git_status(repo)
        repo_status = status or ""
        has_conflicts = "CONFLICT" in repo_status
        has_uncommitted = " M " in repo_status
        has_untracked = "?? " in repo_status
        has_staged = "A  " in repo_status
        ahead = "ahead" in run_command("git status", repo, capture_output=True)
        behind = "behind" in run_command("git status", repo, capture_output=True)
        remote_url = run_command("git remote get-url origin", repo, capture_output=True)
        branch = run_command("git branch --show-current", repo, capture_output=True)
        last_commit = run_command("git log -1 --pretty=format:'%h - %s (%cr)'", repo, capture_output=True)

        repo_stats[repo_name] = {
            "status": repo_status,
            "path": repo,
            "has_conflicts": has_conflicts,
            "has_uncommitted": has_uncommitted,
            "has_untracked": has_untracked,
            "has_staged": has_staged,
            "has_ahead": ahead,
            "has_behind": behind,
            "remote_url": remote_url,
            "branch": branch,
            "last_commit": last_commit
        }

        summary_stats["total_repos"] = summary_stats.get("total_repos", 0) + 1
        summary_stats["has_conflicts"] = summary_stats.get("has_conflicts", 0) + int(has_conflicts)
        summary_stats["has_uncommitted"] = summary_stats.get("has_uncommitted", 0) + int(has_uncommitted)
        summary_stats["has_untracked"] = summary_stats.get("has_untracked", 0) + int(has_untracked)
        summary_stats["has_staged"] = summary_stats.get("has_staged", 0) + int(has_staged)
        summary_stats["has_ahead"] = summary_stats.get("has_ahead", 0) + int(ahead)
        summary_stats["has_behind"] = summary_stats.get("has_behind", 0) + int(behind)
        summary_stats["has_remote"] = summary_stats.get("has_remote", 0) + int(bool(remote_url))
        summary_stats["has_branch"] = summary_stats.get("has_branch", 0) + int(bool(branch))
        summary_stats["has_last_commit"] = summary_stats.get("has_last_commit", 0) + int(bool(last_commit))

        if not keys:
            keys = repo_stats[repo_name].keys()

    if json_output:
        summary_key = "summary"
        while summary_key in repo_stats:
            summary_key = f"_{summary_key}_"

        repo_stats[summary_key] = summary_stats
        print(json.dumps(repo_stats, ensure_ascii=False, indent=2))        
    else:
        table = Table(title="Repo Status")
        table.add_column("Repo", style="cyan", justify="right")
        for key in keys:
            if key == "remote_url":
                table.add_column("URL", style="cyan", justify="left")
            else:
                table.add_column(key.replace("_", " ").capitalize(), justify="left")

        for repo, data in repo_stats.items():
            for key in keys:
                if key == "remote_url" and data[key]:
                    data[key] = f"[link={data[key]}]Link[/link]"
                elif key == "path" and data[key]:
                    data[key] = f"[link=file://{data[key]}]{data[key]}[/link]"
                else:
                    data[key] = str(data[key]) if data[key] else ""

            row = [repo] + [data.get(key, "") for key in keys]
            table.add_row(*row)

        console.print(table)
        console.print("\n")
        console.print(f"[bold]Summary:[/bold]")
        summary_table = Table(show_header=False)
        for key, value in summary_stats.items():
            summary_table.add_row(key.replace("_", " ").capitalize(), str(value))
        console.print(summary_table)

def main():
    parser = argparse.ArgumentParser(description="Clone or update GitHub repositories.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Global arguments
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")

    # Subcommand: get
    parser_get = subparsers.add_parser("get", help="Clone repositories from GitHub users or organizations.")
    parser_get.add_argument("users", nargs="*", default=[], help="GitHub users/orgs to clone from. Defaults to authenticated user.")
    parser_get.add_argument("--ignore", nargs="*", default=[], help="List of repositories to ignore.")
    parser_get.add_argument("--limit", type=int, default=1000, help="Limit number of repositories to fetch.")
    parser_get.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes.")
    parser_get.add_argument("--dir", type=str, help="Directory to clone repositories into. Defaults to the current directory.")
    parser_get.add_argument("--visibility", choices=["all", "public", "private"], default="all", help="Repository visibility.")

    # Subcommand: update
    parser_update = subparsers.add_parser("update", help="Update all Git repositories in the specified directory.")
    parser_update.add_argument("--auto-commit", action="store_true", help="Automatically commit changes before pulling.")
    parser_update.add_argument("--commit-message", type=str, default="Auto-commit from update script", help="Custom commit message for auto-commits.")
    parser_update.add_argument("--auto-resolve-conflicts", choices=["abort", "ours", "theirs"], help="Automatically resolve merge conflicts (abort, ours, theirs).")
    parser_update.add_argument("--prompt", action="store_true", help="Prompt before pushing changes.")
    parser_update.add_argument("--ignore", nargs="*", default=[], help="List of repositories to ignore.")
    parser_update.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes.")
    parser_update.add_argument("--dir", type=str, default=".", help="Base directory to search for Git repositories.")
    parser_update.add_argument("--recursive", action="store_true", help="Recursively search for Git repositories.")

    # Subcommand: status
    parser_status = subparsers.add_parser("status", help="Display status of Git repositories.")
    parser_status.add_argument("--json", action="store_true", help="Output statistics in JSON format. Defaults to table format.")
    parser_status.add_argument("--recursive", action="store_true", help="Recursively search for Git repositories.")
    parser_status.add_argument("--dir", type=str, default=".", help="Directory to search for Git repositories.")

    args = parser.parse_args()

    # Set logging level based on verbose flag
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # Reset stats for each run
    reset_stats()

    # Determine base directory
    base_dir = os.path.abspath(args.dir)

    if args.command == "get":
        # If no users are provided, default to the authenticated user
        users = args.users if args.users else [""]
        get_github_repos(
            users=users,
            ignore_list=args.ignore,
            limit=args.limit,
            dry_run=args.dry_run,
            base_dir=base_dir,
            visibility=args.visibility
        )
    elif args.command == "update":
        base_dir = os.path.abspath(args.dir)
        update_all_repos(
            auto_commit=args.auto_commit,
            commit_message=args.commit_message,
            auto_resolve_conflicts=args.auto_resolve_conflicts,
            prompt=args.prompt,
            ignore_list=args.ignore,
            dry_run=args.dry_run,
            base_dir=base_dir,
            recursive=args.recursive
        )
    elif args.command == "status":
        base_dir = os.path.abspath(args.dir)
        status_command(
            base_dir=base_dir,
            json_output=args.json,
            recursive=args.recursive
        )

    # Print summary table after 'get' or 'update' operations
    if args.command in ["get", "update"]:
        display_summary()


if __name__ == "__main__":
    main()