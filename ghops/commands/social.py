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

@click.group(name='social')
def social_cmd():
    """Manage social media posts for repositories.

    Create, schedule, and publish social media posts about your repositories.

    Examples:

    \b
        ghops social post --repo myproject
        ghops social create --sample-size 5
        ghops social status
    """
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


@social_cmd.command("configure")
@click.argument("platform", type=click.Choice(['twitter', 'linkedin', 'mastodon']))
@click.option("--pretty", is_flag=True, help="Display configuration in formatted output")
def configure(platform, pretty):
    """Configure social media platform credentials."""
    config = load_config()
    
    # Get or create social media configuration
    if 'social_media' not in config:
        config['social_media'] = {'platforms': {}}
    if 'platforms' not in config['social_media']:
        config['social_media']['platforms'] = {}
    
    platforms = config['social_media']['platforms']
    
    if platform == 'twitter':
        click.echo("Configuring Twitter/X credentials...")
        click.echo("\nTo get Twitter API credentials:")
        click.echo("1. Go to https://developer.twitter.com/")
        click.echo("2. Create a developer account and app")
        click.echo("3. Generate API keys and access tokens\n")
        
        api_key = click.prompt("API Key (Consumer Key)", hide_input=True, type=str)
        api_secret = click.prompt("API Secret (Consumer Secret)", hide_input=True, type=str)
        access_token = click.prompt("Access Token", hide_input=True, type=str)
        access_token_secret = click.prompt("Access Token Secret", hide_input=True, type=str)
        
        platforms['twitter'] = {
            'enabled': True,
            'api_key': api_key,
            'api_secret': api_secret,
            'access_token': access_token,
            'access_token_secret': access_token_secret
        }
        
    elif platform == 'linkedin':
        click.echo("Configuring LinkedIn credentials...")
        click.echo("\nTo get LinkedIn API credentials:")
        click.echo("1. Go to https://www.linkedin.com/developers/")
        click.echo("2. Create an app")
        click.echo("3. Get your access token")
        click.echo("4. Find your person URN (from your LinkedIn profile)\n")
        
        access_token = click.prompt("Access Token", hide_input=True, type=str)
        person_urn = click.prompt("Person URN (e.g., ABC123XYZ)", type=str)
        
        platforms['linkedin'] = {
            'enabled': True,
            'access_token': access_token,
            'person_urn': person_urn
        }
        
    elif platform == 'mastodon':
        click.echo("Configuring Mastodon credentials...")
        click.echo("\nTo get Mastodon API credentials:")
        click.echo("1. Go to your Mastodon instance settings")
        click.echo("2. Navigate to Development > Your applications")
        click.echo("3. Create a new application")
        click.echo("4. Copy the access token\n")
        
        instance_url = click.prompt("Instance URL", default="https://mastodon.social", type=str)
        access_token = click.prompt("Access Token", hide_input=True, type=str)
        visibility = click.prompt("Default visibility", 
                                type=click.Choice(['public', 'unlisted', 'private']), 
                                default='public')
        
        platforms['mastodon'] = {
            'enabled': True,
            'instance_url': instance_url,
            'access_token': access_token,
            'visibility': visibility
        }
    
    # Save configuration
    from ..config import save_config
    save_config(config)
    
    if pretty:
        click.echo(f"\n✅ {platform.title()} configuration saved successfully!")
        click.echo("\nYou can now use 'ghops social post' to share your repositories.")
    else:
        result = {
            'status': 'success',
            'platform': platform,
            'configured': True
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)


@social_cmd.command("status")
@click.option("--pretty", is_flag=True, help="Display status in formatted output")
def status(pretty):
    """Show social media configuration status."""
    config = load_config()
    platforms = config.get('social_media', {}).get('platforms', {})
    
    if pretty:
        from ..render import render_table
        
        headers = ["Platform", "Enabled", "Configured", "Missing"]
        rows = []
        
        for platform in ['twitter', 'linkedin', 'mastodon']:
            platform_config = platforms.get(platform, {})
            enabled = platform_config.get('enabled', False)
            
            # Check required fields
            missing = []
            if platform == 'twitter':
                required = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
            elif platform == 'linkedin':
                required = ['access_token', 'person_urn']
            elif platform == 'mastodon':
                required = ['access_token']
            else:
                required = []
            
            for field in required:
                if not platform_config.get(field):
                    missing.append(field)
            
            configured = len(missing) == 0 and platform in platforms
            
            rows.append([
                platform.title(),
                "✓" if enabled else "✗",
                "✓" if configured else "✗",
                ", ".join(missing) if missing else "-"
            ])
        
        render_table(headers, rows, title="Social Media Platform Status")
    else:
        # JSONL output
        for platform in ['twitter', 'linkedin', 'mastodon']:
            platform_config = platforms.get(platform, {})
            result = {
                'platform': platform,
                'enabled': platform_config.get('enabled', False),
                'configured': platform in platforms and bool(platform_config)
            }
            print(json.dumps(result, ensure_ascii=False), flush=True)
