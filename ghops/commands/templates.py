"""
Template management commands for LLM prompts.

Allows users to list, initialize, and edit Jinja2 templates for customizing
LLM-generated content.
"""

import click
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@click.group('templates')
def templates_cmd():
    """Manage LLM prompt templates."""
    pass


@templates_cmd.command('init')
@click.option('--platform',
              type=click.Choice(['devto', 'twitter', 'linkedin', 'bluesky', 'mastodon']),
              help='Initialize templates for specific platform (default: all)')
@click.option('--force', is_flag=True,
              help='Overwrite existing templates')
def init_handler(platform, force):
    """
    Initialize user templates by copying built-in templates.

    Creates templates in ~/.ghops/templates/ that you can customize.

    Examples:

        # Initialize all templates
        ghops templates init

        # Initialize dev.to templates only
        ghops templates init --platform devto

        # Force overwrite existing templates
        ghops templates init --force
    """
    from ..llm.template_loader import get_template_loader

    try:
        loader = get_template_loader()

        click.echo(f"📝 Initializing templates...")
        if platform:
            click.echo(f"   Platform: {platform}")
        else:
            click.echo(f"   Platform: all")

        count = loader.init_user_templates(platform=platform, force=force)

        if count > 0:
            click.echo(f"\n✅ Initialized {count} template(s) in {loader.user_dir}")
            click.echo(f"\n💡 Edit templates with your preferred editor:")
            click.echo(f"   {loader.user_dir}/<platform>/<template>.j2")
        else:
            click.echo(f"\nℹ️  No templates initialized (already exist, use --force to overwrite)")

        return 0

    except Exception as e:
        logger.error(f"Template initialization failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


@templates_cmd.command('list')
@click.option('--platform',
              type=click.Choice(['devto', 'twitter', 'linkedin', 'bluesky', 'mastodon']),
              help='List templates for specific platform (default: all)')
def list_handler(platform):
    """
    List available templates.

    Shows both user templates (customized) and built-in templates (defaults).

    Examples:

        # List all templates
        ghops templates list

        # List dev.to templates
        ghops templates list --platform devto
    """
    from ..llm.template_loader import get_template_loader

    try:
        loader = get_template_loader()

        if platform:
            platforms = [platform]
        else:
            # Get all platforms
            platforms = ['devto', 'twitter', 'linkedin', 'bluesky', 'mastodon']

        click.echo("\n📝 Available Templates\n")

        for plat in platforms:
            templates = loader.list_templates(plat)

            click.echo(f"## {plat}")

            if templates['user']:
                click.echo(f"   User templates (customized):")
                for tmpl in templates['user']:
                    template_path = loader.user_dir / plat / f"{tmpl}.j2"
                    click.echo(f"     - {tmpl} ({template_path})")
            else:
                click.echo(f"   User templates: (none)")

            if templates['builtin']:
                click.echo(f"   Built-in templates:")
                for tmpl in templates['builtin']:
                    click.echo(f"     - {tmpl}")
            else:
                click.echo(f"   Built-in templates: (none)")

            click.echo("")

        return 0

    except Exception as e:
        logger.error(f"Template list failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}")
        return 1


@templates_cmd.command('path')
def path_handler():
    """Show path to template directory."""
    from ..llm.template_loader import get_template_loader

    loader = get_template_loader()
    click.echo(f"User templates:    {loader.user_dir}")
    click.echo(f"Built-in templates: {loader.builtin_dir}")
    return 0
