"""
Handles the 'update' command for updating Git repositories.
"""
import click
import os

from ghops.config import load_config, logger, stats
from ghops.core import update_repo
from ghops.utils import find_git_repos, run_command, get_git_status
import json

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

    if "everything up-to-date" in output.lower() or "everything up to date" in output.lower():
        logger.debug(f"Nothing to push for {repo_path}.")
        stats["skipped"] += 1
    else:
        stats["pushed"] += 1

def handle_merge_conflicts(repo_path, strategy, dry_run):
    """
    Attempts to resolve merge or rebase conflicts if any.

    Args:
        repo_path (str): Path to the Git repository.
        strategy (str): Conflict resolution strategy ('abort', 'ours', 'theirs').
        dry_run (bool): If True, simulate actions without making changes.
    """
    conflicts = run_command("git ls-files -u", repo_path, capture_output=True)
    if conflicts:
        # Determine if it's a merge or rebase conflict
        is_rebase = os.path.isdir(os.path.join(repo_path, ".git", "rebase-merge"))
        conflict_type = "Rebase" if is_rebase else "Merge"
        abort_command = "git rebase --abort" if is_rebase else "git merge --abort"

        logger.warning(f"{conflict_type} conflicts detected in {repo_path}.")
        stats["conflicts"] += 1
        
        if strategy == "abort":
            logger.info(f"Aborting {conflict_type.lower()}...")
            run_command(abort_command, repo_path, dry_run)
        elif strategy == "ours":
            logger.info(f"Resolving conflicts using 'ours' strategy...")
            run_command("git checkout --ours . && git add -A", repo_path, dry_run)
            run_command(f'git commit -m "Auto-resolved conflicts using ours"', repo_path, dry_run)
            if is_rebase:
                run_command("git rebase --continue", repo_path, dry_run)
            stats["conflicts_resolved"] += 1
        elif strategy == "theirs":
            logger.info(f"Resolving conflicts using 'theirs' strategy...")
            run_command("git checkout --theirs . && git add -A", repo_path, dry_run)
            run_command(f'git commit -m "Auto-resolved conflicts using theirs"', repo_path, dry_run)
            if is_rebase:
                run_command("git rebase --continue", repo_path, dry_run)
            stats["conflicts_resolved"] += 1
        else:
            logger.warning("Leaving conflicts for manual resolution.")

@click.command("update")
@click.option("--dir", help="Directory to search for repositories (overrides config)")
@click.option("--recursive", is_flag=True, help="Search recursively for repositories")
@click.option("--auto-commit", is_flag=True, help="Automatically commit changes")
@click.option("--commit-message", default="Automated commit by ghops", help="Commit message to use")
@click.option("--dry-run", is_flag=True, help="Simulate actions without making changes")
def update_repos_handler(dir, recursive, auto_commit, commit_message, dry_run):
    """Update Git repositories."""
    config = load_config()
    results = []

    if dir:
        repo_paths = find_git_repos(dir, recursive)
    else:
        repo_dirs = config.get("general", {}).get("repository_directories", [])
        repo_paths = find_git_repos(repo_dirs, recursive=True)

    for repo_path in repo_paths:
        result = update_repo(repo_path, auto_commit, commit_message, dry_run)
        results.append({"repo": os.path.basename(repo_path), **result})

    print(json.dumps(results, indent=2))

def update_all_repos(repo_dirs, auto_commit, commit_message, auto_resolve_conflicts, prompt, ignore_list, dry_run,
                     add_license=False, license_type="mit", author_name=None, author_email=None, 
                     license_year=None, force_license=False):
    """
    Finds all git repositories in the specified directory and updates them.

    Args:
        repo_dirs (list): List of repository directories to update.
        auto_commit (bool): If True, automatically commit changes before pulling.
        commit_message (str): Commit message for auto-commits.
        auto_resolve_conflicts (str): Conflict resolution strategy.
        prompt (bool): If True, prompt before pushing changes.
        ignore_list (list): List of repository names to ignore.
        dry_run (bool): If True, simulate actions without making changes.
        add_license (bool): If True, add LICENSE files to repositories.
        license_type (str): Type of license to add (default: 'mit').
        author_name (str, optional): Author name for license customization.
        author_email (str, optional): Author email for license customization.
        license_year (str, optional): Copyright year for license customization.
        force_license (bool): If True, overwrite existing LICENSE files.
    """
    if ignore_list:
        repo_dirs = [d for d in repo_dirs if os.path.basename(d) not in ignore_list]

    if not repo_dirs:
        logger.warning("No Git repositories found matching the criteria.")
        return

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
        
        # Handle conflicts before updating
        if auto_resolve_conflicts:
            handle_merge_conflicts(repo, auto_resolve_conflicts, dry_run)

        # Prompt before pushing if enabled
        if prompt:
            click.confirm(f"Proceed with update for {os.path.basename(repo)}?", abort=True)

        update_repo(repo, auto_commit, commit_message, dry_run)
