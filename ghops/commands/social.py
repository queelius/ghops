"""
Handles the 'social' command for creating and posting social media updates.
"""
import click
from ghops.config import load_config
from ghops.core import create_social_media_posts, execute_social_media_posts
from ghops.render import render_social_media_posts
from ghops.utils import find_git_repos

@click.group()
def social_cmd():
    """Manage social media posts for repositories."""
    pass

@social_cmd.command("create")
@click.option("--dir", "repo_dir", default=".", help="Directory to search for repositories.")
@click.option("--recursive", is_flag=True, help="Recursively search for repositories.")
@click.option("--sample-size", default=3, help="Number of repositories to sample.")
@click.option("--as-json", is_flag=True, help="Output as JSON.")
def create(repo_dir, recursive, sample_size, as_json):
    """Create social media posts for a sample of repositories."""
    config = load_config()
    repo_paths = find_git_repos(repo_dir, recursive)
    posts = create_social_media_posts(repo_paths, sample_size=sample_size)
    render_social_media_posts(posts, as_json)

@social_cmd.command("post")
@click.option("--dry-run", is_flag=True, help="Show what would be posted without actually posting.")
@click.option("--dir", "repo_dir", default=".", help="Directory to search for repositories.")
@click.option("--recursive", is_flag=True, help="Recursively search for repositories.")
@click.option("--sample-size", default=3, help="Number of repositories to sample.")
def post(dry_run, repo_dir, recursive, sample_size):
    """Create and execute social media posts."""
    import sys
    config = load_config()
    repo_paths = find_git_repos(repo_dir, recursive)
    posts = create_social_media_posts(repo_paths, sample_size=sample_size)

    if not posts:
        click.echo("No posts to execute.")
        sys.exit(0)

    render_social_media_posts(posts, as_json=False)
    execute_social_media_posts(posts, dry_run)
    if dry_run:
        sys.exit(0)
    sys.exit(0)
