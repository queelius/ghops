"""
CLI commands for workflow orchestration.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from .parser import WorkflowParser
from .executor import WorkflowExecutor
from ...cli_utils import handle_errors

logger = logging.getLogger(__name__)
console = Console()


@click.group(name='workflow')
def workflow_group():
    """Repository workflow orchestration."""
    pass


@workflow_group.command(name='run')
@click.argument('workflow_file', type=click.Path(exists=True))
@click.option('--context', '-c', multiple=True,
              help='Context variables (key=value)')
@click.option('--dry-run', is_flag=True,
              help='Simulate execution without running tasks')
@click.option('--visualize', is_flag=True,
              help='Show workflow visualization')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for results')
@handle_errors
def run_workflow(workflow_file: str, context: tuple, dry_run: bool,
                visualize: bool, output: Optional[str]):
    """Execute a workflow from YAML definition.

    Examples:
        # Run a workflow
        ghops workflow run morning-routine.yaml

        # Dry run with visualization
        ghops workflow run release.yaml --dry-run --visualize

        # Pass context variables
        ghops workflow run deploy.yaml -c VERSION=1.2.3 -c ENV=prod
    """
    # Parse context variables
    context_dict = {}
    for item in context:
        if '=' in item:
            key, value = item.split('=', 1)
            context_dict[key] = value

    # Initialize executor
    executor = WorkflowExecutor()

    # Show visualization if requested
    if visualize:
        workflow_def = executor.load_workflow(workflow_file)
        engine = WorkflowEngine(workflow_def, context_dict)
        console.print(Panel(engine.visualize(), title="Workflow Visualization"))
        if not dry_run:
            console.print()

    # Run workflow
    with console.status(f"{'Simulating' if dry_run else 'Executing'} workflow..."):
        # Run async workflow
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            executor.execute_workflow(workflow_file, context_dict, dry_run)
        )

    # Output results
    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        console.print(f"[green]Results saved to {output}[/green]")
    else:
        _display_workflow_results(result, dry_run)


@workflow_group.command(name='validate')
@click.argument('workflow_file', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True,
              help='Show detailed validation')
@handle_errors
def validate_workflow(workflow_file: str, verbose: bool):
    """Validate workflow definition.

    Examples:
        # Validate workflow syntax
        ghops workflow validate release.yaml

        # Verbose validation
        ghops workflow validate complex-workflow.yaml -v
    """
    try:
        # Load and validate
        workflow_def = WorkflowParser.load_workflow(workflow_file)

        # Additional validation with engine
        engine = WorkflowEngine(workflow_def)
        is_valid, errors = engine.validate()

        if is_valid:
            console.print(f"[green]✓[/green] Workflow is valid")

            if verbose:
                console.print(f"\nWorkflow: {workflow_def.get('name')}")
                console.print(f"Description: {workflow_def.get('description', 'None')}")
                console.print(f"Tasks: {len(workflow_def.get('tasks', []))}")

                # Show execution order
                execution_order = engine.get_execution_order()
                console.print(f"\nExecution order ({len(execution_order)} stages):")
                for i, stage in enumerate(execution_order, 1):
                    console.print(f"  Stage {i}: {', '.join(stage)}")
        else:
            console.print(f"[red]✗[/red] Workflow validation failed")
            for error in errors:
                console.print(f"  • {error}")

    except Exception as e:
        console.print(f"[red]Failed to load workflow: {e}[/red]")


@workflow_group.command(name='list')
@click.option('--directory', '-d', type=click.Path(),
              help='Directory containing workflows')
@handle_errors
def list_workflows(directory: Optional[str]):
    """List available workflows.

    Examples:
        # List workflows in default directory
        ghops workflow list

        # List workflows in specific directory
        ghops workflow list -d ./my-workflows
    """
    executor = WorkflowExecutor(directory)
    workflows = executor.list_available_workflows()

    if not workflows:
        console.print("[yellow]No workflows found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Description")
    table.add_column("Tasks", justify="center")
    table.add_column("Scheduled", justify="center")

    for workflow in workflows:
        table.add_row(
            workflow['file'],
            workflow.get('name', '-'),
            workflow.get('description', '-')[:50],
            str(workflow.get('task_count', 0)),
            '✓' if workflow.get('has_schedule') else '-',
        )

    console.print(table)


@workflow_group.command(name='create')
@click.argument('workflow_type',
              type=click.Choice(['basic', 'morning', 'release', 'dependency']))
@click.option('--output', '-o', type=click.Path(),
              help='Output file for workflow')
@handle_errors
def create_workflow(workflow_type: str, output: Optional[str]):
    """Create example workflow definition.

    Examples:
        # Create basic workflow
        ghops workflow create basic -o my-workflow.yaml

        # Create release pipeline
        ghops workflow create release -o release-pipeline.yaml
    """
    # Generate example
    yaml_content = WorkflowParser.create_example_workflow(workflow_type)

    if output:
        with open(output, 'w') as f:
            f.write(yaml_content)
        console.print(f"[green]Workflow created: {output}[/green]")
    else:
        # Display with syntax highlighting
        syntax = Syntax(yaml_content, "yaml", theme="monokai")
        console.print(syntax)


@workflow_group.command(name='schedule')
@click.argument('workflow_file', type=click.Path(exists=True))
@click.option('--schedule', '-s', required=True,
              help='Schedule (cron or "every N minutes/hours/days")')
@click.option('--context', '-c', multiple=True,
              help='Context variables (key=value)')
@handle_errors
def schedule_workflow(workflow_file: str, schedule: str, context: tuple):
    """Schedule workflow to run periodically.

    Examples:
        # Run every morning at 9 AM
        ghops workflow schedule morning.yaml -s "09:00"

        # Run every 2 hours
        ghops workflow schedule update.yaml -s "every 2 hours"

        # Schedule with context
        ghops workflow schedule backup.yaml -s "every 1 days" -c TARGET=/backups
    """
    # Parse context
    context_dict = {}
    for item in context:
        if '=' in item:
            key, value = item.split('=', 1)
            context_dict[key] = value

    # Initialize executor
    executor = WorkflowExecutor()

    # Schedule workflow
    executor.schedule_workflow(workflow_file, schedule, context_dict)

    # Start scheduler
    executor.start_scheduler()

    console.print(f"[green]Workflow scheduled: {schedule}[/green]")
    console.print("Scheduler running in background...")
    console.print("Press Ctrl+C to stop")

    try:
        # Keep running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        executor.stop_scheduler()
        console.print("\n[yellow]Scheduler stopped[/yellow]")


@workflow_group.command(name='history')
@click.option('--limit', '-n', type=int, default=10,
              help='Number of entries to show')
@click.option('--output', '-o', type=click.Path(),
              help='Export history to file')
@handle_errors
def workflow_history(limit: int, output: Optional[str]):
    """Show workflow execution history.

    Examples:
        # Show last 10 executions
        ghops workflow history

        # Show last 50 executions
        ghops workflow history -n 50

        # Export history
        ghops workflow history -o history.json
    """
    executor = WorkflowExecutor()
    history = executor.get_workflow_history(limit)

    if not history:
        console.print("[yellow]No workflow history[/yellow]")
        return

    if output:
        with open(output, 'w') as f:
            json.dump(history, f, indent=2)
        console.print(f"[green]History exported to {output}[/green]")
    else:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("Workflow", style="cyan")
        table.add_column("Start Time")
        table.add_column("Duration", justify="right")
        table.add_column("Status", justify="center")

        for entry in history:
            status = '✓' if entry.get('success') else '✗'
            if entry.get('dry_run'):
                status = '◊'

            table.add_row(
                entry['id'][:20] + '...',
                entry.get('workflow', '-'),
                entry.get('start_time', '-')[:19],
                f"{entry.get('duration', 0):.1f}s",
                status,
            )

        console.print(table)


@workflow_group.command(name='export')
@click.argument('workflow_file', type=click.Path(exists=True))
@click.option('--format', '-f',
              type=click.Choice(['mermaid', 'dot', 'ascii']),
              default='ascii',
              help='Export format')
@click.option('--output', '-o', type=click.Path(),
              help='Output file')
@handle_errors
def export_workflow(workflow_file: str, format: str, output: Optional[str]):
    """Export workflow visualization.

    Examples:
        # Export as Mermaid diagram
        ghops workflow export release.yaml -f mermaid -o release.mmd

        # Export as ASCII art
        ghops workflow export complex.yaml -f ascii
    """
    # Load workflow
    workflow_def = WorkflowParser.load_workflow(workflow_file)
    engine = WorkflowEngine(workflow_def)

    # Generate export
    if format == 'mermaid':
        content = engine.export_mermaid()
    elif format == 'ascii':
        content = engine.visualize()
    else:  # dot
        content = _generate_dot_graph(engine)

    # Output
    if output:
        with open(output, 'w') as f:
            f.write(content)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        if format == 'mermaid':
            syntax = Syntax(content, "text", theme="monokai")
            console.print(syntax)
        else:
            console.print(content)


def _display_workflow_results(result: Dict, dry_run: bool):
    """Display workflow execution results."""
    if 'errors' in result:
        console.print("[red]Workflow validation failed:[/red]")
        for error in result['errors']:
            console.print(f"  • {error}")
        return

    # Create summary panel
    summary = []
    summary.append(f"Workflow: {result.get('workflow', 'unknown')}")
    summary.append(f"Start: {result.get('start_time', '-')[:19]}")
    summary.append(f"Duration: {result.get('duration', 0):.2f}s")
    summary.append(f"Tasks: {result.get('tasks_executed', 0)}")
    summary.append(f"Succeeded: {result.get('tasks_succeeded', 0)}")
    summary.append(f"Failed: {result.get('tasks_failed', 0)}")

    if dry_run:
        summary.append("\n[yellow]DRY RUN - No tasks were actually executed[/yellow]")

    panel = Panel(
        '\n'.join(summary),
        title="Workflow Results",
        border_style="green" if result.get('tasks_failed', 0) == 0 else "red"
    )
    console.print(panel)

    # Show task details if there were failures
    if result.get('tasks_failed', 0) > 0:
        console.print("\n[red]Failed Tasks:[/red]")
        for task_id, task_result in result.get('task_results', {}).items():
            if 'error' in task_result:
                console.print(f"  • {task_id}: {task_result['error']}")


def _generate_dot_graph(engine: WorkflowEngine) -> str:
    """Generate Graphviz DOT format graph."""
    lines = ['digraph workflow {']
    lines.append('    rankdir=TB;')
    lines.append('    node [shape=box];')

    # Add nodes
    for task in engine.tasks:
        task_id = task['id']
        task_name = task.get('name', task_id)
        lines.append(f'    "{task_id}" [label="{task_name}"];')

    # Add edges
    for task_id, deps in engine.dependencies.items():
        for dep in deps:
            lines.append(f'    "{dep}" -> "{task_id}";')

    lines.append('}')
    return '\n'.join(lines)


def register_workflow_commands(cli):
    """Register workflow commands with the main CLI.

    Args:
        cli: Main CLI group to add commands to.
    """
    cli.add_command(workflow_group)