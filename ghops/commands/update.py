"""
Handles the 'update' command for updating Git repositories.

This command follows our design principles:
- Default output is JSONL streaming
- --pretty flag for human-readable table output
- Core logic returns generators for streaming
- No side effects in core functions
"""

import click
import json
import os
from pathlib import Path
from typing import Generator, Dict, Any

from ..core import get_repositories_from_path
from ..render import render_update_table
from ..utils import run_command, get_git_status, get_remote_url, parse_repo_url
from ..config import logger


def update_repository(repo_path: str, auto_commit: bool = False, 
                     commit_message: str = "Auto commit", 
                     dry_run: bool = False) -> Dict[str, Any]:
    """
    Update a single repository.
    
    Returns a dictionary with update results following standard schema.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "actions": {
            "committed": False,
            "pulled": False,
            "pushed": False,
            "conflicts": False,
            "error": None
        },
        "details": {}
    }
    
    try:
        # Check for uncommitted changes
        status_output = run_command("git status --porcelain", cwd=repo_path, capture_output=True)
        has_changes = bool(status_output and status_output.strip())
        
        if has_changes and auto_commit:
            # Commit changes
            if not dry_run:
                run_command("git add -A", cwd=repo_path)
                commit_output = run_command(
                    f'git commit -m "{commit_message}"', 
                    cwd=repo_path, 
                    capture_output=True
                )
                if commit_output and "nothing to commit" not in commit_output.lower():
                    result["actions"]["committed"] = True
                    result["details"]["commit_message"] = commit_message
            else:
                result["actions"]["committed"] = True
                result["details"]["commit_message"] = f"[DRY RUN] {commit_message}"
        
        # Pull latest changes
        if not dry_run:
            pull_output = run_command(
                "git pull --rebase --autostash", 
                cwd=repo_path, 
                capture_output=True,
                check=False
            )
            
            if pull_output:
                if "already up to date" not in pull_output.lower():
                    result["actions"]["pulled"] = True
                    result["details"]["pull_output"] = pull_output.strip()
                
                # Check for conflicts
                if "conflict" in pull_output.lower():
                    result["actions"]["conflicts"] = True
                    result["details"]["conflict_type"] = "rebase"
        else:
            result["details"]["pull_output"] = "[DRY RUN] Would pull latest changes"
        
        # Push if we committed
        if result["actions"]["committed"] and not dry_run:
            push_output = run_command("git push", cwd=repo_path, capture_output=True)
            if push_output and "everything up-to-date" not in push_output.lower():
                result["actions"]["pushed"] = True
                result["details"]["push_output"] = push_output.strip()
        elif result["actions"]["committed"] and dry_run:
            result["details"]["push_output"] = "[DRY RUN] Would push changes"
        
        # Add remote info
        remote_url = get_remote_url(repo_path)
        if remote_url:
            result["remote"] = {
                "url": remote_url,
                "owner": parse_repo_url(remote_url)[0],
                "name": parse_repo_url(remote_url)[1]
            }
            
    except Exception as e:
        result["actions"]["error"] = str(e)
        result["error"] = str(e)
        result["type"] = "update_error"
        result["context"] = {
            "path": repo_path,
            "operation": "update"
        }
    
    return result


def update_repositories(base_dir: str = None, recursive: bool = False,
                       auto_commit: bool = False, commit_message: str = "Auto commit",
                       dry_run: bool = False, tag_filters: list = None, 
                       all_tags: bool = False) -> Generator[Dict[str, Any], None, None]:
    """
    Generator that yields update results for repositories.
    
    This is a pure function that returns a generator of update result dictionaries.
    It does not print, format, or interact with the terminal.
    """
    from ..config import load_config
    from ..utils import find_git_repos_from_config
    
    # Get repositories based on base_dir or config
    if base_dir and base_dir != ".":
        repos = list(get_repositories_from_path(base_dir, recursive))
    else:
        config = load_config()
        repo_dirs = config.get("general", {}).get("repository_directories", [])
        repos = list(find_git_repos_from_config(repo_dirs))
    
    # Apply tag filtering if specified
    if tag_filters:
        from ..commands.catalog import get_repositories_by_tags
        config = load_config()
        
        # Get filtered repos
        filtered_repos = list(get_repositories_by_tags(tag_filters, config, all_tags))
        filtered_paths = {r["path"] for r in filtered_repos}
        
        # Filter the discovered repos
        repos = [r for r in repos if os.path.abspath(r) in filtered_paths]
    
    for repo_path in repos:
        yield update_repository(repo_path, auto_commit, commit_message, dry_run)


@click.command("update")
@click.option("-d", "--dir", default=".", help="Directory to search for repositories")
@click.option("-r", "--recursive", is_flag=True, help="Search recursively for repositories")
@click.option("--auto-commit", is_flag=True, help="Automatically commit changes before pulling")
@click.option("--commit-message", default="Auto commit", help="Commit message for auto-commits")
@click.option("--dry-run", is_flag=True, help="Simulate actions without making changes")
@click.option("-t", "--tag", "tag_filters", multiple=True, help="Filter by tags (e.g., org:torvalds, lang:python)")
@click.option("--all-tags", is_flag=True, help="Match all tags (default: match any)")
@click.option("--pretty", is_flag=True, help="Display as formatted table instead of JSONL")
def update_repos_handler(dir, recursive, auto_commit, commit_message, dry_run, tag_filters, all_tags, pretty):
    """
    Update Git repositories by pulling latest changes.
    
    By default, outputs JSONL (one JSON object per line) for each repository.
    Use --pretty for a human-readable table format.
    """
    # Get repository updates as a generator
    updates_generator = update_repositories(
        base_dir=dir,
        recursive=recursive,
        auto_commit=auto_commit,
        commit_message=commit_message,
        dry_run=dry_run,
        tag_filters=tag_filters,
        all_tags=all_tags
    )
    
    if pretty:
        # Collect all updates and render as table
        updates = list(updates_generator)
        render_update_table(updates)
    else:
        # Stream JSONL output (default)
        for update in updates_generator:
            print(json.dumps(update, ensure_ascii=False), flush=True)