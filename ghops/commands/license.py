"""
Handles the 'license' command for managing LICENSE files.
"""
import json
from datetime import datetime
from rich.console import Console
from rich.json import JSON
from rich.table import Table
from ..utils import run_command
from ..config import logger, stats
from pathlib import Path

console = Console()

def list_licenses(json_output):
    """
    Lists available licenses from the GitHub API.

    Args:
        json_output (bool): If True, output in JSON format.
    """
    licenses_json = run_command("gh api /licenses", capture_output=True)
    if not licenses_json:
        logger.error("Could not fetch licenses from GitHub API.")
        return

    licenses = json.loads(licenses_json)
    if json_output:
        console.print(JSON(licenses_json))
    else:
        table = Table(title="Available Licenses")
        table.add_column("Key", style="cyan")
        table.add_column("Name", style="magenta")
        for license in licenses:
            table.add_row(license["key"], license["name"])
        console.print(table)

def show_license_template(license_key, json_output):
    """
    Shows the template for a specific license.

    Args:
        license_key (str): The key of the license to show (e.g., 'mit').
        json_output (bool): If True, output in JSON format.
    """
    template_json = run_command(f"gh api /licenses/{license_key}", capture_output=True)
    if not template_json:
        logger.error(f"Could not fetch license template for '{license_key}'.")
        return

    template = json.loads(template_json)
    if json_output:
        console.print(JSON(template_json))
    else:
        console.print(f"[bold]License Template: {template['name']}[/bold]")
        console.print(template['body'])

def add_license_to_repo(repo_path, license_key, author_name, author_email, year, dry_run, force):
    """
    Adds a LICENSE file to a repository.

    Args:
        repo_path (str): Path to the repository.
        license_key (str): License key (e.g., 'mit').
        author_name (str): Author's name.
        author_email (str): Author's email.
        year (str): Copyright year.
        dry_run (bool): If True, simulate actions.
        force (bool): If True, overwrite existing LICENSE file.
    """
    license_file = Path(repo_path) / "LICENSE"
    if license_file.exists() and not force:
        logger.info(f"LICENSE file already exists in {repo_path}, skipping.")
        stats["licenses_skipped"] += 1
        return

    template_json = run_command(f"gh api /licenses/{license_key}", capture_output=True)
    if not template_json:
        logger.error(f"Could not fetch license template for '{license_key}'.")
        return

    template = json.loads(template_json)['body']

    # Customize the template
    if not year:
        year = str(datetime.now().year)
    if author_name:
        template = template.replace("[year]", year).replace("[fullname]", author_name)
    if author_email:
        template = template.replace("[email]", author_email)

    if dry_run:
        logger.info(f"[Dry Run] Would create LICENSE file in {repo_path} with {license_key} license.")
    else:
        with open(license_file, "w") as f:
            f.write(template)
        logger.info(f"Added {license_key} LICENSE to {repo_path}")
        stats["licenses_added"] += 1
