import click
from ghops.config import load_config
import json
import os

@click.group("config")
def config_cmd():
    """Configuration management commands."""
    pass

@config_cmd.command("generate")
def generate_config():
    """Generate an example configuration file."""
    example = {
        "general": {
            "repository_directories": ["~/github", "~/projects/*/repos", "~/work/code"],
            "github_username": "your_username"
        },
        "service": {"enabled": True, "interval_minutes": 120},
        "social_media": {"platforms": {"twitter": {"enabled": False}}}
    }
    config_path = os.path.expanduser("~/.ghopsrc")
    if os.path.exists(config_path):
        click.echo(f"Example configuration already exists at {config_path}. Example configuration:\n{json.dumps(example, indent=2)}")
        return
    with open(config_path, "w") as f:
        json.dump(example, f, indent=2)
    click.echo(f"Example configuration written to {config_path}. Example configuration:\n{json.dumps(example, indent=2)}")

@config_cmd.command("show")
@click.option("--json", "as_json", is_flag=True, help="Output in JSON format.")
def show_config(as_json):
    """Show the current configuration with all merges applied."""
    import sys
    config = load_config()
    # Always output valid JSON if not a TTY or if --json is set
    if as_json or not sys.stdout.isatty():
        click.echo(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        click.echo(json.dumps(config, indent=2, ensure_ascii=False))
