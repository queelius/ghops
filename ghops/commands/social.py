"""
Handles the 'social' command for creating and posting social media updates.

This command follows our design principles:
- Default output is JSONL streaming
- --pretty flag for human-readable output
- Core logic returns generators for streaming
- No side effects in core functions
"""
import click
import json
from ghops.config import load_config
from ghops.core import create_social_media_posts, execute_social_media_posts
from ghops.render import render_social_media_posts
from ghops.repo_filter import get_filtered_repos, add_common_repo_options

@click.group()
def social_cmd():
    """Manage social media posts for repositories."""
    pass

@social_cmd.command("create")
@add_common_repo_options
@click.option("--sample-size", default=3, help="Number of repositories to sample.")
@click.option("--pretty", is_flag=True, help="Display as formatted output instead of JSONL")
def create(dir, recursive, tag_filters, all_tags, query, sample_size, pretty):
    """Create social media posts for a sample of repositories."""
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        click.echo(error_msg)
        return
    
    posts = create_social_media_posts(repos, sample_size=sample_size)
    
    if pretty:
        render_social_media_posts(posts, as_json=False)
    else:
        # Stream JSONL output
        for post in posts:
            print(json.dumps(post, ensure_ascii=False), flush=True)

@social_cmd.command("post")
@add_common_repo_options
@click.option("--dry-run", is_flag=True, help="Show what would be posted without actually posting.")
@click.option("--sample-size", default=3, help="Number of repositories to sample.")
@click.option("--pretty", is_flag=True, help="Display as formatted output instead of JSONL")
def post(dir, recursive, tag_filters, all_tags, query, dry_run, sample_size, pretty):
    """Create and execute social media posts."""
    import sys
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        click.echo(error_msg)
        sys.exit(0)
    
    posts = create_social_media_posts(repos, sample_size=sample_size)

    if not posts:
        click.echo("No posts to execute.")
        sys.exit(0)

    if pretty:
        render_social_media_posts(posts, as_json=False)
    else:
        # Stream JSONL output
        for post in posts:
            print(json.dumps(post, ensure_ascii=False), flush=True)
    
    # Execute posts
    execute_social_media_posts(posts, dry_run)
    sys.exit(0)
