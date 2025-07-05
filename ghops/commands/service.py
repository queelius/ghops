import click
from .. import core
import json
from ..service import run_service_once

@click.group("service")
def service_cmd():
    """Automated services for reporting and social media."""
    pass

@service_cmd.command("start")
@click.option("--dry-run", is_flag=True, help="Run service in preview mode without posting or sending reports.")
def start(dry_run):
    """Start the automated ghops service (runs one cycle)."""
    result = run_service_once(dry_run)
    print(json.dumps(result, indent=2))


@service_cmd.command("run-once")
@click.option("--dry-run", is_flag=True, help="Run a single cycle in preview mode.")
def run_once(dry_run):
    """Execute a single cycle of the service."""
    result = run_service_once(dry_run)
    print(json.dumps(result, indent=2))
