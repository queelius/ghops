"""
Handles the 'update' command for updating Git repositories.
"""
import os
from rich.progress import Progress

from ..utils import run_command, find_git_repos, get_git_status
from ..config import logger, stats
from .license import add_license_to_repo

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
