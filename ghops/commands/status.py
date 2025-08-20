"""
Handles the 'status' command for displaying repository status.

This command follows our design principles:
- Default output is JSONL streaming
- --verbose/-v for progress output
- --quiet/-q to suppress JSON output
- Thin CLI layer that connects core logic to output
"""

import json
import click

from ..core import get_repository_status
from ..render import render_status_table, console
from ..config import load_config
from ..cli_utils import standard_command, add_common_options
from ..exit_codes import NoReposFoundError


@click.command(name='status')
@click.option('-d', '--dir', default=None, help='Directory to search for repositories (default: use config)')
@click.option('-r', '--recursive', is_flag=True, help='Search recursively for repositories')
@click.option('--no-pages', is_flag=True, help='Skip GitHub Pages check for faster results')
@click.option('--no-pypi', is_flag=True, help='Skip PyPI package detection')
@click.option('--no-dedup', is_flag=True, help='Show all instances including duplicates and soft links')
@click.option('-t', '--tag', 'tag_filters', multiple=True, help='Filter by tags (e.g., org:torvalds, lang:python)')
@click.option('--all-tags', is_flag=True, help='Match all tags (default: match any)')
@click.option('--table/--no-table', default=None, help='Display as formatted table (auto-detected by default)')
@add_common_options('verbose', 'quiet')
@standard_command(streaming=True)
def status_handler(dir, recursive, no_pages, no_pypi, no_dedup, tag_filters, all_tags, table, progress, quiet, **kwargs):
    """Show repository status.
    
    \b
    By default, shows status for all repositories configured in ~/.ghops/config.json.
    Use -d/--dir to check a specific directory instead of using config.
    
    Output format:
    - Interactive terminal: Table format by default
    - Piped/redirected: JSONL streaming by default
    - Use --table to force table output
    - Use --no-table to force JSONL output
    - Use -v/--verbose to show progress
    - Use -q/--quiet to suppress data output
    
    Examples:
    
    \b
        ghops status                    # Table format (if terminal)
        ghops status | jq .             # JSONL format (piped)
        ghops status --no-table         # Force JSONL output
        ghops status -d .               # Show only current directory
        ghops status -d . -r            # Show all repos under current
        ghops status -d ~/projects      # Show repos in ~/projects
        ghops status -t org:torvalds    # Filter by tag
    """
    # Auto-detect table mode if not specified
    if table is None:
        import sys
        table = sys.stdout.isatty()  # Use table format for interactive terminals
    
    # Override config if flags are provided
    if no_pypi:
        config = load_config()
        config['pypi'] = config.get('pypi', {})
        config['pypi']['check_by_default'] = False
    
    # Count total repos first for progress
    from ..utils import find_git_repos, find_git_repos_from_config, is_git_repo
    import os
    config = load_config()
    
    progress("Discovering repositories...")
    
    # If no directory specified (None), use config
    # If directory specified (including '.'), use that directory only
    if dir is None:
        # Use config directories
        repo_paths = find_git_repos_from_config(
            config.get('general', {}).get('repository_directories', []),
            recursive
        )
        if not repo_paths:
            # Fallback to current directory if config has no repos
            repo_paths = find_git_repos('.', recursive)
    else:
        # Use specified directory only (ignores config)
        expanded_dir = os.path.expanduser(dir)
        expanded_dir = os.path.abspath(expanded_dir)
        
        # Check if the directory itself is a repo
        if is_git_repo(expanded_dir):
            # If not recursive, only check this directory
            if not recursive:
                repo_paths = [expanded_dir]
            else:
                # Recursive: include this repo and search for more inside
                repo_paths = [expanded_dir]
                # Also search subdirectories
                repo_paths.extend(find_git_repos(expanded_dir, recursive=True))
                # Remove duplicates (the directory itself might be found again)
                repo_paths = list(set(repo_paths))
        else:
            # Directory is not a repo, search inside it
            repo_paths = find_git_repos(expanded_dir, recursive)
    
    total_repos = len(repo_paths)
    
    if total_repos == 0:
        raise NoReposFoundError("No repositories found in specified directories")
    
    progress(f"Found {total_repos} repositories")
    
    # Get repository status as a generator
    # Pass None as base_dir to use config, or the specified directory
    repos_generator = get_repository_status(
        base_dir=dir if dir else None,
        recursive=recursive,
        skip_pages_check=no_pages,
        deduplicate=not no_dedup,
        tag_filters=tag_filters,
        all_tags=all_tags
    )
    
    if table:
        # For table output, we need to collect all repos
        repos = []
        with progress.task("Checking repository status", total=total_repos) as update:
            for i, repo in enumerate(repos_generator, 1):
                repos.append(repo)
                update(i, repo.get('name', ''))
                
                # Update description for GitHub Pages batch check
                if not no_pages and i == total_repos:
                    progress("Finalizing GitHub Pages status...")
        
        # Render as table (table display is not suppressed by quiet)
        render_status_table(repos)
    else:
        # Stream JSONL output (default behavior)
        repo_count = 0
        with progress.task("Checking repository status", total=total_repos) as update:
            for repo in repos_generator:
                repo_count += 1
                update(repo_count, repo.get('name', ''))
                if not quiet:
                    yield repo
        
        # Show summary
        if tag_filters:
            filtered_count = repo_count
            if filtered_count < total_repos:
                progress(f"Filtered: {filtered_count}/{total_repos} repositories matched")