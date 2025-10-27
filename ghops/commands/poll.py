"""
Poll repositories for events and trigger automated actions.

Checks repositories for events (git tags, releases, etc.) and dispatches
them to configured handlers for automated actions.
"""

import click
import logging
import time
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@click.command('poll')
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              multiple=True,
              help='Repository to poll (can specify multiple, default: all from config)')
@click.option('--watch', is_flag=True,
              help='Keep running and poll periodically')
@click.option('--interval',
              type=int,
              default=300,
              help='Polling interval in seconds (default: 300 = 5 minutes)')
@click.option('--dry-run', is_flag=True,
              help='Show what would happen without taking actions')
@click.option('--reset', is_flag=True,
              help='Reset event state before polling')
def poll_handler(repo, watch, interval, dry_run, reset):
    """
    Poll repositories for events and trigger automated actions.

    \b
    Detects events like:
      - New git tags
      - GitHub releases (future)
      - Star milestones (future)

    \b
    Then triggers configured handlers:
      - Post to social media
      - Publish to package registries
      - Send notifications

    \b
    Examples:
      # Poll once
      ghops poll

      # Poll specific repos
      ghops poll --repo /path/to/repo1 --repo /path/to/repo2

      # Watch mode (poll every 5 minutes)
      ghops poll --watch

      # Custom interval (poll every hour)
      ghops poll --watch --interval 3600

      # Dry run (show what would happen)
      ghops poll --dry-run

      # Reset state and poll
      ghops poll --reset

    \b
    Configuration:
      Add event handlers to ~/.ghops/config.json:
      \b
      {
        "events": {
          "enabled": true,
          "exclude_patterns": [
            "/_deps/",
            "/build/",
            "/node_modules/",
            "/vendor/"
          ],
          "handlers": [
            {
              "type": "social_media_post",
              "enabled": true,
              "trigger": "git_tag",
              "conditions": {
                "tag_pattern": "v*",
                "branches": ["main", "master"]
              },
              "actions": {
                "platforms": [
                  {"name": "devto", "draft": false, "human_review": true},
                  {"name": "twitter", "human_review": false}
                ]
              }
            }
          ]
        }
      }
    """
    from ..config import load_config
    from ..event_detector import get_event_detector
    from ..events import create_dispatcher_from_config
    from ..utils import find_git_repos_from_config

    try:
        config = load_config()

        # Check if events are enabled
        if not config.get('events', {}).get('enabled', True):
            click.echo("⚠️  Event system is disabled in config")
            click.echo("   Enable with: events.enabled = true in config")
            return 1

        # Get event detector
        detector = get_event_detector()

        # Reset state if requested
        if reset:
            click.echo("🔄 Resetting event state...")
            detector.reset_state()

        # Get repositories to poll
        if repo:
            repos = [str(Path(r).resolve()) for r in repo]
        else:
            # Get repos from config
            repo_dirs = config.get('general', {}).get('repository_directories', [])
            if not repo_dirs:
                click.echo("❌ No repositories configured")
                click.echo("   Add 'general.repository_directories' to config")
                return 1

            repos = find_git_repos_from_config(repo_dirs, recursive=True)

            # Filter out common build/dependency directories
            # Get exclude patterns from config, or use defaults
            events_config = config.get('events', {})
            exclude_patterns = events_config.get('exclude_patterns', [
                '/_deps/',
                '/build/',
                '/build_',
                '/build-',
                '/node_modules/',
                '/vendor/',
                '/.venv/',
                '/venv/',
            ])

            filtered_repos = []
            excluded_count = 0
            for repo in repos:
                if not any(pattern in repo for pattern in exclude_patterns):
                    filtered_repos.append(repo)
                else:
                    excluded_count += 1

            repos = filtered_repos

            if excluded_count > 0:
                logger.debug(f"Excluded {excluded_count} repositories matching exclude_patterns")

        if not repos:
            click.echo("ℹ️  No repositories found to poll")
            return 0

        # Create event dispatcher
        dispatcher = create_dispatcher_from_config(config)

        if dry_run:
            click.echo("🔍 DRY RUN MODE - No actions will be taken\n")

        # Poll loop
        iteration = 0
        while True:
            iteration += 1

            if watch:
                click.echo(f"\n{'='*60}")
                click.echo(f"Poll iteration #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo(f"{'='*60}")
            else:
                click.echo(f"\n📡 Polling {len(repos)} repositories for events...\n")

            total_events = 0
            total_actions = 0

            for repo_path in repos:
                repo_name = Path(repo_path).name

                # Detect events
                events = detector.detect_all(repo_path)

                if events:
                    click.echo(f"📍 {repo_name}: {len(events)} event(s) detected")

                    for event in events:
                        total_events += 1

                        click.echo(f"   🎯 Event: {event.type}")
                        for key, value in event.context.items():
                            click.echo(f"      {key}: {value}")

                        if dry_run:
                            click.echo(f"      [DRY RUN] Would dispatch to handlers")
                        else:
                            # Dispatch event
                            results = dispatcher.dispatch_and_record(event)

                            for result in results:
                                total_actions += 1
                                status = result.get('status', 'unknown')
                                action = result.get('action', 'unknown')
                                platform = result.get('platform', '')

                                if status == 'success' or status == 'published':
                                    click.echo(f"      ✅ {action} ({platform}): {status}")
                                    if result.get('url'):
                                        click.echo(f"         URL: {result['url']}")
                                elif status == 'failed':
                                    click.echo(f"      ❌ {action} ({platform}): {status}")
                                    if result.get('error'):
                                        click.echo(f"         Error: {result['error']}")
                                elif status == 'cancelled':
                                    click.echo(f"      ⚠️  {action} ({platform}): {status}")
                                else:
                                    click.echo(f"      ℹ️  {action} ({platform}): {status}")

            # Summary
            click.echo(f"\n{'='*60}")
            click.echo(f"Summary:")
            click.echo(f"  Events detected: {total_events}")
            click.echo(f"  Actions executed: {total_actions}")
            click.echo(f"{'='*60}")

            # Break if not watching
            if not watch:
                break

            # Sleep until next poll
            click.echo(f"\n💤 Sleeping for {interval} seconds...")
            click.echo(f"   Next poll at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + interval))}")
            click.echo(f"   Press Ctrl+C to stop")

            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                click.echo("\n\n⚠️  Interrupted by user")
                break

        return 0

    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Polling failed: {e}", exc_info=True)
        click.echo(f"\n❌ Error: {e}")
        click.echo("\n💡 Troubleshooting:")
        click.echo("   1. Check your config at ~/.ghops/config.json")
        click.echo("   2. Verify event handlers are configured")
        click.echo("   3. Check LLM provider is accessible")
        click.echo("   4. Run with --dry-run to test without actions")
        return 1


@click.command('events')
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              help='Filter by repository')
@click.option('--type',
              help='Filter by event type (git_tag, release_published, etc.)')
@click.option('--limit',
              type=int,
              default=20,
              help='Maximum number of events to show')
def events_handler(repo, type, limit):
    """
    Show event history.

    Displays events that have been detected and processed.

    Examples:

        # Show all events
        ghops events

        # Show events for specific repo
        ghops events --repo /path/to/repo

        # Show only git_tag events
        ghops events --type git_tag
    """
    from ..analytics_store import get_analytics_store
    from ..render import render_table

    try:
        store = get_analytics_store()

        repo_path = str(Path(repo).resolve()) if repo else None
        events = store.get_events(repo_path=repo_path, event_type=type, limit=limit)

        if not events:
            click.echo("ℹ️  No events found")
            return 0

        # Format for display
        display_events = []
        for event in events:
            # Get actions for this event
            actions = store.get_event_actions(event['id'])
            action_summary = f"{len(actions)} action(s)"

            display_events.append({
                'type': event['event_type'],
                'repo': Path(event['repo_path']).name,
                'triggered_at': event['triggered_at'],
                'status': event['status'],
                'actions': action_summary
            })

        click.echo(f"\n📋 Event History (showing {len(events)}):\n")
        render_table(display_events, columns=['type', 'repo', 'triggered_at', 'status', 'actions'])

        return 0

    except Exception as e:
        logger.error(f"Events list failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1
