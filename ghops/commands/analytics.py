"""
Analytics commands for tracking and analyzing post engagement.

Provides commands to collect metrics, view trends, compare performance,
and export analytics data.
"""

import click
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@click.group('analytics')
def analytics_cmd():
    """Track and analyze social media post engagement."""
    pass


@analytics_cmd.command('collect')
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              help='Repository path (default: all repos with posts)')
@click.option('--platform',
              type=click.Choice(['devto', 'twitter', 'mastodon', 'bluesky']),
              help='Collect metrics for specific platform only')
@click.option('--post-id',
              help='Collect metrics for specific post ID')
def collect_handler(repo, platform, post_id):
    """
    Collect latest metrics from platforms.

    Fetches current view counts, likes, comments, etc. from each platform's API
    and records them in the analytics database.

    Examples:

        # Collect metrics for all posts
        ghops analytics collect

        # Collect for specific repo
        ghops analytics collect --repo /path/to/repo

        # Collect for specific platform
        ghops analytics collect --platform devto

        # Collect for specific post
        ghops analytics collect --post-id 123
    """
    from ..analytics_store import get_analytics_store
    from ..llm.platforms import DevToPlatform, get_publishing_platform
    from ..config import load_config

    try:
        store = get_analytics_store()
        config = load_config()

        # Get posts to collect metrics for
        if post_id:
            posts = [store.get_post(int(post_id))]
            if not posts[0]:
                click.echo(f"❌ Post ID {post_id} not found")
                return 1
        elif repo:
            repo_path = str(Path(repo).resolve())
            posts = store.get_posts_by_repo(repo_path)
        elif platform:
            posts = store.get_posts_by_platform(platform)
        else:
            # Get all recent posts (last 30 days)
            cutoff = datetime.now() - timedelta(days=30)
            with store._connection() as conn:
                cursor = conn.execute("""
                    SELECT id, repo_path, version, platform, platform_post_id, url,
                           published_at, metadata
                    FROM posts
                    WHERE published_at >= ?
                    ORDER BY published_at DESC
                """, (cutoff,))
                posts = [store._row_to_dict(row, parse_json=['metadata'])
                        for row in cursor.fetchall()]

        if not posts:
            click.echo("ℹ️  No posts found to collect metrics for")
            return 0

        click.echo(f"📊 Collecting metrics for {len(posts)} posts...")
        collected = 0
        errors = 0

        for post in posts:
            try:
                # Get platform-specific collector
                if post['platform'] == 'devto':
                    metrics = _collect_devto_metrics(post, config)
                elif post['platform'] == 'twitter':
                    click.echo(f"   ⚠️  Twitter metrics collection not yet implemented")
                    continue
                elif post['platform'] == 'mastodon':
                    click.echo(f"   ⚠️  Mastodon metrics collection not yet implemented")
                    continue
                elif post['platform'] == 'bluesky':
                    click.echo(f"   ⚠️  Bluesky metrics collection not yet implemented")
                    continue
                else:
                    click.echo(f"   ⚠️  Unknown platform: {post['platform']}")
                    continue

                if metrics:
                    store.record_metrics(
                        post_id=post['id'],
                        views=metrics.get('views', 0),
                        likes=metrics.get('likes', 0),
                        comments=metrics.get('comments', 0),
                        shares=metrics.get('shares', 0),
                        bookmarks=metrics.get('bookmarks', 0)
                    )
                    collected += 1
                    click.echo(f"   ✅ {post['platform']}: {post['url']} "
                             f"(views: {metrics.get('views', 0)}, "
                             f"likes: {metrics.get('likes', 0)})")

            except Exception as e:
                errors += 1
                logger.error(f"Failed to collect metrics for post {post['id']}: {e}")
                click.echo(f"   ❌ Error collecting metrics: {e}")

        click.echo(f"\n✅ Collected metrics for {collected} posts ({errors} errors)")
        return 0

    except Exception as e:
        logger.error(f"Analytics collection failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


def _collect_devto_metrics(post: dict, config: dict) -> Optional[dict]:
    """Collect metrics from dev.to API."""
    import requests

    api_key = config.get('llm', {}).get('publishing', {}).get('platforms', {}).get('devto', {}).get('api_key')
    if not api_key:
        import os
        api_key = os.getenv('DEVTO_API_KEY')

    if not api_key:
        logger.warning("dev.to API key not configured")
        return None

    try:
        article_id = post['platform_post_id']
        response = requests.get(
            f"https://dev.to/api/articles/{article_id}",
            headers={"api-key": api_key},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        return {
            'views': data.get('page_views_count', 0),
            'likes': data.get('public_reactions_count', 0),
            'comments': data.get('comments_count', 0),
            'shares': 0,  # dev.to doesn't provide share count
            'bookmarks': 0  # dev.to doesn't provide bookmark count
        }

    except Exception as e:
        logger.error(f"Failed to fetch dev.to metrics: {e}")
        return None


@analytics_cmd.command('show')
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              help='Repository path')
@click.option('--platform',
              type=click.Choice(['devto', 'twitter', 'mastodon', 'bluesky']),
              help='Filter by platform')
@click.option('--format', 'output_format',
              type=click.Choice(['table', 'json', 'csv']),
              default='table',
              help='Output format')
@click.option('--limit',
              type=int,
              default=20,
              help='Maximum number of posts to show')
def show_handler(repo, platform, output_format, limit):
    """
    Show analytics for posts.

    Displays published posts with their latest metrics in various formats.

    Examples:

        # Show all posts
        ghops analytics show

        # Show posts for specific repo
        ghops analytics show --repo /path/to/repo

        # Show dev.to posts only
        ghops analytics show --platform devto

        # Export as JSON
        ghops analytics show --format json

        # Export as CSV
        ghops analytics show --format csv > analytics.csv
    """
    from ..analytics_store import get_analytics_store
    from ..render import render_table

    try:
        store = get_analytics_store()

        # Get posts
        if repo:
            repo_path = str(Path(repo).resolve())
            posts = store.get_posts_by_repo(repo_path, limit=limit)
        elif platform:
            posts = store.get_posts_by_platform(platform, limit=limit)
        else:
            # Get all posts
            with store._connection() as conn:
                cursor = conn.execute("""
                    SELECT id, repo_path, version, platform, platform_post_id, url,
                           published_at, metadata
                    FROM posts
                    ORDER BY published_at DESC
                    LIMIT ?
                """, (limit,))
                posts = [store._row_to_dict(row, parse_json=['metadata'])
                        for row in cursor.fetchall()]

        if not posts:
            click.echo("ℹ️  No posts found")
            return 0

        # Enrich with latest metrics
        enriched_posts = []
        for post in posts:
            metrics = store.get_latest_metrics(post['id'])
            enriched_posts.append({
                'id': post['id'],
                'repo': Path(post['repo_path']).name,
                'version': post['version'],
                'platform': post['platform'],
                'url': post['url'] or 'N/A',
                'published_at': post['published_at'],
                'views': metrics['views'] if metrics else 0,
                'likes': metrics['likes'] if metrics else 0,
                'comments': metrics['comments'] if metrics else 0,
                'metrics_updated': metrics['collected_at'] if metrics else 'Never'
            })

        # Output
        if output_format == 'json':
            click.echo(json.dumps(enriched_posts, indent=2))
        elif output_format == 'csv':
            import csv
            import sys
            writer = csv.DictWriter(sys.stdout, fieldnames=enriched_posts[0].keys())
            writer.writeheader()
            writer.writerows(enriched_posts)
        else:  # table
            render_table(enriched_posts, columns=[
                'id', 'repo', 'version', 'platform', 'views', 'likes', 'comments'
            ])

        return 0

    except Exception as e:
        logger.error(f"Analytics show failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


@analytics_cmd.command('top')
@click.option('--metric',
              type=click.Choice(['views', 'likes', 'comments', 'shares']),
              default='views',
              help='Metric to rank by')
@click.option('--platform',
              type=click.Choice(['devto', 'twitter', 'mastodon', 'bluesky']),
              help='Filter by platform')
@click.option('--limit',
              type=int,
              default=10,
              help='Number of top posts to show')
@click.option('--format', 'output_format',
              type=click.Choice(['table', 'json']),
              default='table',
              help='Output format')
def top_handler(metric, platform, limit, output_format):
    """
    Show top performing posts.

    Ranks posts by engagement metrics like views, likes, or comments.

    Examples:

        # Top 10 posts by views
        ghops analytics top

        # Top 5 by likes
        ghops analytics top --metric likes --limit 5

        # Top dev.to posts
        ghops analytics top --platform devto
    """
    from ..analytics_store import get_analytics_store
    from ..render import render_table

    try:
        store = get_analytics_store()
        posts = store.get_top_posts(metric=metric, platform=platform, limit=limit)

        if not posts:
            click.echo("ℹ️  No posts found")
            return 0

        # Format for display
        display_posts = []
        for post in posts:
            display_posts.append({
                'repo': Path(post['repo_path']).name,
                'version': post['version'],
                'platform': post['platform'],
                metric: post['metric_value'],
                'views': post['views'],
                'likes': post['likes'],
                'comments': post['comments'],
                'url': post['url'] or 'N/A'
            })

        if output_format == 'json':
            click.echo(json.dumps(display_posts, indent=2))
        else:
            click.echo(f"\n🏆 Top {limit} posts by {metric}:")
            render_table(display_posts, columns=[
                'repo', 'version', 'platform', metric, 'views', 'likes', 'comments'
            ])

        return 0

    except Exception as e:
        logger.error(f"Analytics top failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


@analytics_cmd.command('summary')
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              help='Repository path')
def summary_handler(repo):
    """
    Show overall engagement summary.

    Displays aggregate statistics across all posts.

    Examples:

        # Overall summary
        ghops analytics summary

        # Summary for specific repo
        ghops analytics summary --repo /path/to/repo
    """
    from ..analytics_store import get_analytics_store

    try:
        store = get_analytics_store()

        repo_path = str(Path(repo).resolve()) if repo else None
        summary = store.get_engagement_summary(repo_path=repo_path)

        click.echo("\n📊 Engagement Summary")
        click.echo("=" * 60)
        click.echo(f"Total Posts:    {summary.get('total_posts', 0):,}")
        click.echo(f"Total Views:    {summary.get('total_views', 0):,}")
        click.echo(f"Total Likes:    {summary.get('total_likes', 0):,}")
        click.echo(f"Total Comments: {summary.get('total_comments', 0):,}")
        click.echo(f"Total Shares:   {summary.get('total_shares', 0):,}")

        # Calculate engagement rate
        views = summary.get('total_views', 0)
        engagements = (summary.get('total_likes', 0) +
                      summary.get('total_comments', 0) +
                      summary.get('total_shares', 0))

        if views > 0:
            engagement_rate = (engagements / views) * 100
            click.echo(f"Engagement Rate: {engagement_rate:.2f}%")

        click.echo("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Analytics summary failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


@analytics_cmd.command('stats')
def stats_handler():
    """Show database statistics."""
    from ..analytics_store import get_analytics_store

    try:
        store = get_analytics_store()
        stats = store.get_stats()

        click.echo("\n📊 Analytics Database Statistics")
        click.echo("=" * 60)
        click.echo(f"Posts:         {stats.get('posts_count', 0):,}")
        click.echo(f"Metrics:       {stats.get('metrics_count', 0):,}")
        click.echo(f"Events:        {stats.get('events_count', 0):,}")
        click.echo(f"Event Actions: {stats.get('event_actions_count', 0):,}")
        click.echo(f"Database Size: {stats.get('db_size_bytes', 0) / 1024:.2f} KB")
        click.echo(f"Location:      {store.db_path}")
        click.echo("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Stats failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1
