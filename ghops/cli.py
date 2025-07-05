#!/usr/bin/env python3

import click
from pathlib import Path

from ghops.config import load_config
from ghops.commands.list import list_repos_handler
from ghops.commands.status import status_handler
from ghops.commands.get import get_repo_handler
from ghops.commands.update import update_repos_handler
from ghops.commands.license import license_cmd
from ghops.commands.social import social_cmd
from ghops.commands.service import service_cmd
from ghops.commands.config import config_cmd


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
cli.add_command(license_cmd)
cli.add_command(social_cmd)
cli.add_command(service_cmd)
cli.add_command(config_cmd)


def main():
    cli()


if __name__ == "__main__":
    main()
