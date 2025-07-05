"""
Output rendering functions for ghops.
Handles formatting and displaying data in various formats.
"""
import json
import click


def render_social_media_posts(posts, as_json=False):
    """
    Render social media posts to stdout.
    
    Args:
        posts: List of post dictionaries
        as_json: If True, output as JSON, otherwise as formatted text
    """
    if as_json:
        click.echo(json.dumps(posts, indent=2, ensure_ascii=False))
    else:
        if not posts:
            click.echo("No posts generated.")
            return
            
        click.echo(f"\n📱 Generated {len(posts)} social media post(s):")
        for i, post in enumerate(posts, 1):
            click.echo(f"\n--- Post {i} ({post['platform']}) ---")
            click.echo(f"Repository: {post['repo_name']}")
            click.echo(f"Template: {post['template_used']}")
            click.echo(f"Content:")
            click.echo(post['content'])