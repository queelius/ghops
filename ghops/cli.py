#!/usr/bin/env python3

import click
from pathlib import Path

from ghops.config import load_config
from ghops.commands.list import list_repos_handler
from ghops.commands.status import status_handler
from ghops.commands.get import get_repo_handler
from ghops.commands.update import update_repos_handler
from ghops.commands.audit import audit_cmd
from ghops.commands.social import social_cmd
from ghops.commands.service import service_cmd
from ghops.commands.config import config_cmd
from ghops.commands.catalog import catalog_cmd
from ghops.commands.query import query_handler
from ghops.commands.metadata import metadata_cmd
from ghops.commands.docs import docs_group
from ghops.commands.export import export_cmd


@click.group()
@click.version_option()
def cli():
    """GitHub Operations CLI Tool."""
    pass


# Add command handlers to the CLI
cli.add_command(list_repos_handler)
cli.add_command(status_handler)
cli.add_command(get_repo_handler)
cli.add_command(update_repos_handler)
cli.add_command(audit_cmd)
cli.add_command(social_cmd)
cli.add_command(service_cmd)
cli.add_command(config_cmd)
cli.add_command(catalog_cmd)
cli.add_command(query_handler, name='query')
cli.add_command(metadata_cmd)
cli.add_command(docs_group)
cli.add_command(export_cmd)


def main():
    cli()

if __name__ == "__main__":
    main()
