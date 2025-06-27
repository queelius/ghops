"""
Handles the 'get' command for cloning GitHub repositories.
"""
import os
from pathlib import Path
from rich.progress import Progress
from ..utils import run_command
from ..config import logger, stats
from .license import add_license_to_repo

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
                progress.update(user_task, advance=1)
                continue

            repos = repos_output.split("\n")
            repo_task = progress.add_task(f"[cyan]Cloning repositories for {user_display}...", total=len(repos))
            for repo in repos:
                repo_name = repo.split("/")[-1]
                if repo_name in ignore_list:
                    logger.info(f"Skipping ignored repo: {repo_name}")
                    stats["skipped"] += 1
                    progress.update(repo_task, advance=1)
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
