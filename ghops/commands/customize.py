"""
Customize command for managing component customizations.

Helps users create and manage custom component renderers.
"""

import click
import os
from pathlib import Path
from typing import List

from ..component_hooks import (
    get_user_components_path,
    create_component_template,
    init_user_components,
    load_user_renderers
)
from ..export_components import default_registry
# Ensure components are registered
try:
    from ..export_components_impl import (
        HeaderComponent, SummaryStatisticsComponent,
        TagCloudComponent, RepositoryCardsComponent,
        ReadmeContentComponent
    )
except ImportError:
    pass
from ..config import logger


@click.group()
def customize():
    """Customize export component rendering."""
    pass


@customize.command()
def init():
    """Initialize user components directory with examples."""
    components_dir = get_user_components_path()
    
    if init_user_components():
        click.echo(f"✓ Created components directory at: {components_dir}")
        click.echo(f"✓ Created example renders.py file")
        click.echo("")
        click.echo("To customize a component:")
        click.echo("  1. Edit ~/.ghops/export_components/renders.py")
        click.echo("  2. Uncomment and modify the example functions")
        click.echo("  3. Or run: ghops customize create <component_name>")
    else:
        click.echo(f"Components directory already exists at: {components_dir}")
        click.echo("Run 'ghops customize list' to see available components")


@customize.command()
@click.argument('component_name')
def create(component_name: str):
    """Create a template for customizing a component.
    
    Examples:
        ghops customize create summary_stats
        ghops customize create repository_cards
    """
    # Check if component exists
    available = default_registry.list_components()
    if component_name not in available:
        click.echo(f"Error: Component '{component_name}' not found.")
        click.echo(f"Available components: {', '.join(available)}")
        return
    
    # Create components directory if needed
    components_dir = get_user_components_path()
    components_dir.mkdir(parents=True, exist_ok=True)
    
    # Create component file
    component_file = components_dir / f"{component_name}.py"
    
    if component_file.exists():
        if not click.confirm(f"File {component_file} already exists. Overwrite?"):
            return
    
    # Generate template
    template_code = create_component_template(component_name)
    component_file.write_text(template_code)
    
    click.echo(f"✓ Created customization template at: {component_file}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {component_file}")
    click.echo(f"  2. Modify the render_{component_name} function")
    click.echo("  3. Add to ~/.ghops/export_components/renders.py:")
    click.echo(f"     from .{component_name} import render_{component_name}")
    click.echo(f"     RENDERERS['{component_name}'] = render_{component_name}")


@customize.command()
def list():
    """List available components and their customization status."""
    available = default_registry.list_components()
    custom_renderers = load_user_renderers()
    
    click.echo("Available Export Components:")
    click.echo("")
    
    for comp_name in sorted(available):
        component = default_registry.get(comp_name)
        status = "✓ customized" if comp_name in custom_renderers else "  default"
        desc = component.description if component else ""
        click.echo(f"  [{status}] {comp_name:20} - {desc}")
    
    if custom_renderers:
        click.echo("")
        click.echo(f"Custom renderers active: {', '.join(custom_renderers.keys())}")
    
    click.echo("")
    click.echo("To customize a component, run:")
    click.echo("  ghops customize create <component_name>")


@customize.command()
def show():
    """Show active custom renderers."""
    components_dir = get_user_components_path()
    renders_file = components_dir / 'renders.py'
    
    if not renders_file.exists():
        click.echo("No custom renderers found.")
        click.echo("Run 'ghops customize init' to get started.")
        return
    
    custom_renderers = load_user_renderers()
    
    if not custom_renderers:
        click.echo(f"Renders file exists at {renders_file}")
        click.echo("But no active renderers found.")
        click.echo("Make sure RENDERERS dict is defined and populated.")
        return
    
    click.echo("Active Custom Renderers:")
    for name, func in custom_renderers.items():
        click.echo(f"  - {name}: {func.__module__}.{func.__name__}")
    
    click.echo("")
    click.echo(f"Edit {renders_file} to modify.")


@customize.command()
@click.argument('component_name')
def disable(component_name: str):
    """Disable a custom renderer (revert to default)."""
    components_dir = get_user_components_path()
    renders_file = components_dir / 'renders.py'
    
    if not renders_file.exists():
        click.echo("No custom renderers found.")
        return
    
    # This is a simple implementation - in production you'd want
    # to actually parse and modify the Python file properly
    click.echo(f"To disable {component_name}, edit {renders_file}")
    click.echo(f"and comment out or remove it from the RENDERERS dict.")


# Register with main CLI
def register_commands(cli):
    """Register customize commands with the main CLI."""
    cli.add_command(customize)