"""
Handles the 'status' command for displaying repository status.

This command follows our design principles:
- Default output is JSONL streaming
- --pretty flag for human-readable table output
- Thin CLI layer that connects core logic to output
"""

import json
import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core import get_repository_status
from ..render import render_status_table, console
from ..config import load_config


@click.command(name='status')
@click.option('-d', '--dir', default='.', help='Directory to search for repositories')
@click.option('-r', '--recursive', is_flag=True, help='Search recursively for repositories')
@click.option('--pretty', is_flag=True, help='Display as formatted table instead of JSONL')
@click.option('--no-pages', is_flag=True, help='Skip GitHub Pages check for faster results')
@click.option('--no-pypi', is_flag=True, help='Skip PyPI package detection')
@click.option('--no-dedup', is_flag=True, help='Show all instances including duplicates and soft links')
@click.option('-t', '--tag', 'tag_filters', multiple=True, help='Filter by tags (e.g., org:torvalds, lang:python)')
@click.option('--all-tags', is_flag=True, help='Match all tags (default: match any)')
def status_handler(dir, recursive, pretty, no_pages, no_pypi, no_dedup, tag_filters, all_tags):
    """Show repository status.
    
    By default, outputs JSONL (one JSON object per line) for each repository.
    Use --pretty for a human-readable table with progress indication.
    """
    # Override config if flags are provided
    if no_pypi:
        config = load_config()
        config['pypi'] = config.get('pypi', {})
        config['pypi']['check_by_default'] = False
    
    # Get repository status as a generator
    repos_generator = get_repository_status(
        base_dir=dir,
        recursive=recursive,
        skip_pages_check=no_pages,
        deduplicate=not no_dedup,
        tag_filters=tag_filters,
        all_tags=all_tags
    )
    
    if pretty:
        # For pretty output, we need to collect all repos to show progress
        repos = []
        
        # Count total repos first (quick scan)
        from ..utils import find_git_repos, find_git_repos_from_config
        config = load_config()
        
        if dir == '.':
            repo_paths = find_git_repos_from_config(
                config.get('general', {}).get('repository_directories', []),
                recursive
            )
            if not repo_paths:
                repo_paths = find_git_repos(dir, recursive)
        else:
            repo_paths = find_git_repos(dir, recursive)
        
        total_repos = len(repo_paths)
        
        if total_repos == 0:
            console.print("[yellow]No repositories found.[/yellow]")
            return
        
        # Show progress while collecting
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console
        ) as progress:
            task = progress.add_task("Checking repository status...", total=total_repos)
            
            for repo in repos_generator:
                repos.append(repo)
                progress.update(task, advance=1)
                
                # Update description for GitHub Pages batch check
                if not no_pages and len(repos) == total_repos:
                    progress.update(task, description="Finalizing GitHub Pages status...")
        
        # Render as table
        render_status_table(repos)
    else:
        # Stream JSONL output (default behavior)
        for repo in repos_generator:
            print(json.dumps(repo, ensure_ascii=False), flush=True)