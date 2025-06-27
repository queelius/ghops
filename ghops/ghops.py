#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
from pathlib import Path
from datetime import datetime

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
    "conflicts_resolved": 0,
    "licenses_added": 0,
    "licenses_skipped": 0
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


def get_github_repos(users, ignore_list, limit, dry_run, base_dir, visibility="all", 
                     add_license=False, license_type="mit", author_name=None, author_email=None, 
                     license_year=None, force_license=False):
    """
    Fetches repositories from GitHub users/orgs and clones them.

    Args:
        users (list): List of GitHub users or organizations.
        ignore_list (list): List of repository names to ignore.
        limit (int): Maximum number of repositories to fetch per user/org.
        dry_run (bool): If True, simulate actions without making changes.
        base_dir (str): Base directory to clone repositories into.
        visibility (str): Repository visibility ('all', 'public', 'private').
        add_license (bool): If True, add LICENSE files to cloned repositories.
        license_type (str): Type of license to add (default: 'mit').
        author_name (str, optional): Author name for license customization.
        author_email (str, optional): Author email for license customization.
        license_year (str, optional): Copyright year for license customization.
        force_license (bool): If True, overwrite existing LICENSE files.
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
                f'gh repo list {user_query} --limit {limit} --json nameWithOwner --jq ".[].nameWithOwner"',
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
                    
                    # Add LICENSE file if requested
                    if add_license:
                        repo_dir = Path(base_dir) / repo_name
                        if repo_dir.exists():
                            add_license_to_repo(
                                str(repo_dir),
                                license_key=license_type,
                                author_name=author_name,
                                author_email=author_email,
                                year=license_year,
                                dry_run=dry_run,
                                force=force_license
                            )
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


def update_all_repos(auto_commit, commit_message, auto_resolve_conflicts, prompt, ignore_list, dry_run, base_dir, recursive,
                     add_license=False, license_type="mit", author_name=None, author_email=None, 
                     license_year=None, force_license=False):
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
        add_license (bool): If True, add LICENSE files to repositories.
        license_type (str): Type of license to add (default: 'mit').
        author_name (str, optional): Author name for license customization.
        author_email (str, optional): Author email for license customization.
        license_year (str, optional): Copyright year for license customization.
        force_license (bool): If True, overwrite existing LICENSE files.
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
            # Add LICENSE file if requested
            if add_license:
                add_license_to_repo(
                    repo,
                    license_key=license_type,
                    author_name=author_name,
                    author_email=author_email,
                    year=license_year,
                    dry_run=dry_run,
                    force=force_license
                )
            
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
        "conflicts_resolved": 0,
        "licenses_added": 0,
        "licenses_skipped": 0
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


def display_repo_status_table(repo_dirs, json_output, base_dir="."):
    """
    Gathers and displays the status of all repositories.

    Args:
        repo_dirs (list): List of repository directories.
        json_output (bool): If True, output in JSON format.
        base_dir (str): Base directory for display purposes.
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

def get_available_licenses():
    """
    Fetches the list of available license templates from GitHub API.
    
    Returns:
        list: List of available license keys, or empty list if failed.
    """
    try:
        output = run_command('gh api /licenses', capture_output=True)
        if output:
            licenses_data = json.loads(output)
            return [license_info['key'] for license_info in licenses_data]
        return []
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse licenses from GitHub API: {e}")
        return []


def get_license_template(license_key):
    """
    Fetches a specific license template from GitHub API.
    
    Args:
        license_key (str): The license key (e.g., 'mit', 'apache-2.0', 'gpl-3.0').
    
    Returns:
        dict: License template data with 'body' and 'name' keys, or None if failed.
    """
    try:
        output = run_command(f'gh api /licenses/{license_key}', capture_output=True)
        if output:
            return json.loads(output)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to fetch license template for '{license_key}': {e}")
        return None


def customize_license_content(license_body, author_name=None, author_email=None, year=None):
    """
    Customizes a license template with user-specific information.
    
    Args:
        license_body (str): The raw license template content.
        author_name (str, optional): Author's name. If None, tries to get from git config.
        author_email (str, optional): Author's email. If None, tries to get from git config.
        year (str, optional): Copyright year. If None, uses current year.
    
    Returns:
        str: Customized license content.
    """
    # Get current year if not provided
    if not year:
        year = str(datetime.now().year)
    
    # Try to get author info from git config if not provided
    if not author_name:
        author_name = run_command('git config --global user.name', capture_output=True) or "[fullname]"
    
    if not author_email:
        author_email = run_command('git config --global user.email', capture_output=True) or "[email]"
    
    # Common license template placeholders and their replacements
    replacements = {
        '[year]': year,
        '[fullname]': author_name,
        '[email]': author_email,
        '<year>': year,
        '<name of author>': author_name,
        '<copyright holders>': author_name,
        'Copyright (c) [year] [fullname]': f'Copyright (c) {year} {author_name}',
        'Copyright [yyyy] [name of copyright owner]': f'Copyright {year} {author_name}',
    }
    
    customized_content = license_body
    for placeholder, replacement in replacements.items():
        customized_content = customized_content.replace(placeholder, replacement)
    
    return customized_content


def add_license_to_repo(repo_path, license_key="mit", author_name=None, author_email=None, year=None, dry_run=False, force=False):
    """
    Adds a LICENSE file to a repository using GitHub's license templates.
    
    Args:
        repo_path (str): Path to the repository.
        license_key (str): License template key (default: 'mit').
        author_name (str, optional): Author's name for customization.
        author_email (str, optional): Author's email for customization.
        year (str, optional): Copyright year for customization.
        dry_run (bool): If True, simulate actions without making changes.
        force (bool): If True, overwrite existing LICENSE file.
    
    Returns:
        bool: True if license was added successfully, False otherwise.
    """
    license_path = Path(repo_path) / "LICENSE"
    
    # Check if LICENSE file already exists
    if license_path.exists() and not force:
        logger.debug(f"LICENSE file already exists in {repo_path}, skipping.")
        stats["licenses_skipped"] += 1
        return False
    
    # Get license template
    license_template = get_license_template(license_key)
    if not license_template:
        logger.error(f"Failed to fetch license template '{license_key}' for {repo_path}")
        stats["licenses_skipped"] += 1
        return False
    
    # Customize license content
    license_content = customize_license_content(
        license_template['body'],
        author_name=author_name,
        author_email=author_email,
        year=year
    )
    
    if dry_run:
        logger.info(f"[Dry Run] Would add {license_template['name']} LICENSE to {repo_path}")
        return True
    
    try:
        # Write LICENSE file
        with open(license_path, 'w', encoding='utf-8') as f:
            f.write(license_content)
        
        logger.info(f"Added {license_template['name']} LICENSE to {repo_path}")
        stats["licenses_added"] += 1
        return True
        
    except IOError as e:
        logger.error(f"Failed to write LICENSE file to {repo_path}: {e}")
        stats["licenses_skipped"] += 1
        return False


def list_available_licenses():
    """
    Lists all available GitHub license templates.
    
    Returns:
        list: List of tuples (key, name) for available licenses.
    """
    licenses = []
    try:
        output = run_command('gh api /licenses', capture_output=True)
        if output:
            licenses_data = json.loads(output)
            for license_info in licenses_data:
                licenses.append((license_info['key'], license_info['name']))
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to fetch available licenses: {e}")
    
    return licenses

def license_command(list_licenses=False, license_key=None):
    """
    Handles the 'license' subcommand for listing or showing license templates.
    
    Args:
        list_licenses (bool): If True, list all available licenses.
        license_key (str, optional): Show details for a specific license.
    """
    if list_licenses:
        licenses = list_available_licenses()
        if licenses:
            table = Table(title="Available GitHub License Templates")
            table.add_column("Key", style="cyan", justify="left")
            table.add_column("Name", style="magenta", justify="left")
            
            for key, name in sorted(licenses):
                table.add_row(key, name)
            
            console.print(table)
        else:
            logger.error("Failed to fetch available licenses. Make sure 'gh' CLI is installed and authenticated.")
    
    elif license_key:
        license_template = get_license_template(license_key)
        if license_template:
            console.print(f"[bold cyan]License:[/bold cyan] {license_template['name']}")
            console.print(f"[bold cyan]Key:[/bold cyan] {license_template['key']}")
            console.print(f"[bold cyan]URL:[/bold cyan] {license_template.get('url', 'N/A')}")
            console.print("\n[bold cyan]Template Preview:[/bold cyan]")
            # Show first 20 lines of the license template
            lines = license_template['body'].split('\n')
            preview_lines = lines[:20]
            if len(lines) > 20:
                preview_lines.append("... (truncated)")
            console.print('\n'.join(preview_lines))
        else:
            logger.error(f"Failed to fetch license template for '{license_key}'")
    else:
        logger.error("Please specify either --list or --show <license-key>")

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
    
    # LICENSE arguments for get command
    parser_get.add_argument("--add-license", action="store_true", help="Add LICENSE files to cloned repositories.")
    parser_get.add_argument("--license-type", type=str, default="mit", help="License template to use (default: mit). Use 'ghops license --list' to see available options.")
    parser_get.add_argument("--license-author", type=str, help="Author name for license customization. Defaults to git config user.name.")
    parser_get.add_argument("--license-email", type=str, help="Author email for license customization. Defaults to git config user.email.")
    parser_get.add_argument("--license-year", type=str, help="Copyright year for license customization. Defaults to current year.")
    parser_get.add_argument("--force-license", action="store_true", help="Overwrite existing LICENSE files.")

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
    
    # LICENSE arguments for update command
    parser_update.add_argument("--add-license", action="store_true", help="Add LICENSE files to repositories.")
    parser_update.add_argument("--license-type", type=str, default="mit", help="License template to use (default: mit). Use 'ghops license --list' to see available options.")
    parser_update.add_argument("--license-author", type=str, help="Author name for license customization. Defaults to git config user.name.")
    parser_update.add_argument("--license-email", type=str, help="Author email for license customization. Defaults to git config user.email.")
    parser_update.add_argument("--license-year", type=str, help="Copyright year for license customization. Defaults to current year.")
    parser_update.add_argument("--force-license", action="store_true", help="Overwrite existing LICENSE files.")

    # Subcommand: status
    parser_status = subparsers.add_parser("status", help="Display status of Git repositories.")
    parser_status.add_argument("--json", action="store_true", help="Output statistics in JSON format. Defaults to table format.")
    parser_status.add_argument("--recursive", action="store_true", help="Recursively search for Git repositories.")
    parser_status.add_argument("--dir", type=str, default=".", help="Directory to search for Git repositories.")

    # Subcommand: license
    parser_license = subparsers.add_parser("license", help="Manage license templates.")
    parser_license.add_argument("--list", action="store_true", help="List all available license templates.")
    parser_license.add_argument("--show", type=str, help="Show details for a specific license template.")

    args = parser.parse_args()

    # Set logging level based on verbose flag
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # Reset stats for each run
    reset_stats()

    # Determine base directory (only for commands that use it)
    if hasattr(args, 'dir'):
        base_dir = os.path.abspath(args.dir)
    else:
        base_dir = os.getcwd()

    if args.command == "get":
        # If no users are provided, default to the authenticated user
        users = args.users if args.users else [""]
        get_github_repos(
            users=users,
            ignore_list=args.ignore,
            limit=args.limit,
            dry_run=args.dry_run,
            base_dir=base_dir,
            visibility=args.visibility,
            add_license=args.add_license,
            license_type=args.license_type,
            author_name=args.license_author,
            author_email=args.license_email,
            license_year=args.license_year,
            force_license=args.force_license
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
            recursive=args.recursive,
            add_license=args.add_license,
            license_type=args.license_type,
            author_name=args.license_author,
            author_email=args.license_email,
            license_year=args.license_year,
            force_license=args.force_license
        )
    elif args.command == "status":
        base_dir = os.path.abspath(args.dir)
        status_command(
            base_dir=base_dir,
            json_output=args.json,
            recursive=args.recursive
        )
    elif args.command == "license":
        license_command(
            list_licenses=args.list,
            license_key=args.show
        )

    # Print summary table after 'get' or 'update' operations
    if args.command in ["get", "update"]:
        display_summary()


if __name__ == "__main__":
    main()