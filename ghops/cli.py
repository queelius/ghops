#!/usr/bin/env python3

import click
from pathlib import Path
import sys

from ghops.config import load_config
from ghops.commands.list import list_repos_handler
from ghops.commands.status import status_handler
from ghops.commands.clone import clone_handler
from ghops.commands.update import update_repos_handler
from ghops.commands.social import social_cmd
from ghops.commands.config import config_cmd
from ghops.commands.catalog import catalog_cmd
from ghops.commands.tag import tag_cmd
from ghops.commands.query import query_handler
from ghops.commands.metadata import metadata_cmd
from ghops.commands.docs import docs_group
from ghops.commands.export import export_cmd
from ghops.commands.top import top_handler
from ghops.commands.shell import shell_handler
from ghops.commands.publish import publish_handler
from ghops.commands.generate_post import generate_post_handler

# New command groups
from ghops.commands.analysis import analysis_cmd
from ghops.commands.fs import fs_cmd
from ghops.commands.git import git_cmd

# Individual commands for backward compat
from ghops.commands.audit import audit_cmd
from ghops.commands.network import network_cmd
from ghops.commands.ai import ai_cmd
from ghops.commands.analytics import analytics_cmd
from ghops.commands.templates import templates_cmd
from ghops.commands.poll import poll_handler, events_handler


@click.group()
@click.version_option()
def cli():
    """GitHub Operations CLI Tool."""
    pass


# Core commands (flat, top-level)
cli.add_command(clone_handler, name='clone')
cli.add_command(list_repos_handler)
cli.add_command(status_handler)
cli.add_command(update_repos_handler)
cli.add_command(query_handler, name='query')
cli.add_command(top_handler, name='top')
cli.add_command(shell_handler, name='shell')
cli.add_command(poll_handler, name='poll')
cli.add_command(events_handler, name='events')
cli.add_command(metadata_cmd)
cli.add_command(export_cmd)
cli.add_command(publish_handler, name='publish')
cli.add_command(generate_post_handler)

# Command groups
cli.add_command(tag_cmd)
cli.add_command(docs_group)
cli.add_command(analysis_cmd)
cli.add_command(fs_cmd)
cli.add_command(git_cmd)
cli.add_command(social_cmd)
cli.add_command(config_cmd)
cli.add_command(analytics_cmd)
cli.add_command(templates_cmd)

# Deprecated commands (backward compatibility)
cli.add_command(catalog_cmd)

# Note: audit, network-cmd, and ai-cmd are now under 'analysis' group
# They're kept as hidden top-level commands for backward compatibility but will show deprecation warnings when used


# Deprecated aliases
def create_deprecated_alias(original_cmd, old_name, new_name):
    """Create a deprecated alias that forwards to the new command."""
    import copy

    if hasattr(original_cmd, 'callback'):
        # It's a single command
        original_callback = original_cmd.callback

        def wrapper(*args, **kwargs):
            click.echo(f"⚠️  Warning: 'ghops {old_name}' is deprecated, use 'ghops {new_name}' instead", err=True)
            return original_callback(*args, **kwargs)

        deprecated_cmd = copy.deepcopy(original_cmd)
        deprecated_cmd.name = old_name
        deprecated_cmd.hidden = True
        deprecated_cmd.callback = wrapper
        deprecated_cmd.help = f"[DEPRECATED] Use 'ghops {new_name}' instead.\n\n" + (original_cmd.help or "")
        return deprecated_cmd
    else:
        # It's a command group - just rename it and mark deprecated
        deprecated_cmd = copy.deepcopy(original_cmd)
        deprecated_cmd.name = old_name
        deprecated_cmd.hidden = True
        if hasattr(deprecated_cmd, 'help'):
            deprecated_cmd.help = f"[DEPRECATED] Use 'ghops {new_name}' instead.\n\n" + (deprecated_cmd.help or "")
        return deprecated_cmd


# get → clone
cli.add_command(create_deprecated_alias(clone_handler, 'get', 'clone'))

# social-cmd → social
cli.add_command(create_deprecated_alias(social_cmd, 'social-cmd', 'social'))


def main():
    cli()

if __name__ == "__main__":
    main()
