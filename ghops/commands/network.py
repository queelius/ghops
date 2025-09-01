"""
Network analysis commands for repository relationship graphs.

This command analyzes relationships between repositories based on:
- Keyword similarity
- README content similarity  
- Direct repository links
- Shared dependencies
- Common topics/tags
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..cli_utils import add_common_options, standard_command
from ..core import get_repository_status, get_repositories_from_path
from ..metadata import MetadataStore
from ..integrations.network_analysis import RepositoryNetwork

logger = logging.getLogger(__name__)
console = Console()


@click.group()
def network_cmd():
    """Analyze and visualize repository relationship networks."""
    pass


@network_cmd.command("analyze")
@click.option('--dir', default='.', help='Directory to search for repositories')
@click.option('-r', '--recursive', is_flag=True, help='Search recursively')
@click.option('-t', '--tag', multiple=True, help='Filter by tags')
@click.option('--all-tags', is_flag=True, help='Match all tags (default: match any)')
@click.option('--query', help='Filter with query language')
@click.option('--config', type=click.Path(exists=True),
              help='Network configuration file (JSON) with weight settings')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for network data (JSON or HTML)')
@click.option('--format', type=click.Choice(['json', 'html']),
              default='json', help='Output format')
@click.option('--min-strength', type=float, default=0.1,
              help='Minimum link strength to include in network')
@click.option('--include-readme', is_flag=True,
              help='Include README content for similarity analysis')
@add_common_options('verbose', 'quiet')
@standard_command
def analyze(dir, recursive, tag, all_tags, query, config, output, format, 
            min_strength, include_readme, verbose, quiet, progress):
    """Build and analyze repository relationship network.
    
    Examples:
        ghops network analyze -o network.json
        ghops network analyze --format html -o network.html
        ghops network analyze --config weights.json --min-strength 0.2
        ghops network analyze -t lang:python --include-readme
    """
    # Load configuration if provided
    network_config = None
    if config:
        with open(config) as f:
            network_config = json.load(f)
    else:
        network_config = RepositoryNetwork.get_default_config()
    
    network_config['min_link_strength'] = min_strength
    
    # Initialize network
    network = RepositoryNetwork(network_config)
    
    # Get repositories
    repos = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=quiet
    ) as progress:
        task = progress.add_task("Finding repositories...", total=None)
        
        # Use metadata store if available
        metadata_store = MetadataStore()
        
        if tag or query:
            # Use metadata store for filtered repos
            for repo_data in metadata_store.query_repositories(tags=tag, query=query):
                repos.append(repo_data)
        else:
            # Find repos in directory
            repo_paths = get_repositories_from_path(dir, recursive=recursive)
            for path in repo_paths:
                # Get full status including metadata
                status = get_repository_status(path)
                
                # Enhance with metadata if available
                metadata = metadata_store.get(path)
                if metadata:
                    status.update(metadata)
                
                # Include README if requested
                if include_readme:
                    readme_path = Path(path) / 'README.md'
                    if readme_path.exists():
                        try:
                            status['readme_content'] = readme_path.read_text()[:10000]  # Limit size
                        except Exception as e:
                            logger.debug(f"Could not read README for {path}: {e}")
                
                repos.append(status)
        
        progress.update(task, description=f"Found {len(repos)} repositories")
    
    if not repos:
        console.print("[yellow]No repositories found[/yellow]")
        return
    
    # Add repositories to network
    for repo in repos:
        network.add_repository(repo)
    
    # Build network with progress
    def progress_callback(current, total, message):
        if not quiet:
            console.print(f"[dim]{message}[/dim] ({current}/{total})", end='\r')
    
    with console.status("[bold green]Building repository network...", spinner="dots") if not quiet else nullcontext():
        network.build_network(progress_callback if verbose else None)
    
    if not quiet:
        console.print()  # New line after progress
    
    # Analyze network
    hubs = network.find_hubs(top_n=5)
    bridges = network.find_bridges()[:5]
    clusters = network.find_clusters()
    
    # Display results
    if not quiet:
        # Hub repositories
        if hubs:
            table = Table(title="🎯 Hub Repositories (Most Connected)")
            table.add_column("Repository", style="cyan")
            table.add_column("Connections", style="green")
            
            for repo_path, score in hubs:
                repo_name = network.nodes[repo_path].get('name', repo_path)
                table.add_row(repo_name, f"{score:.2f}")
            
            console.print(table)
        
        # Bridge connections
        if bridges:
            table = Table(title="🌉 Bridge Connections")
            table.add_column("Repository 1", style="cyan")
            table.add_column("Repository 2", style="cyan")
            table.add_column("Importance", style="yellow")
            
            for repo1, repo2, importance in bridges:
                name1 = network.nodes[repo1].get('name', repo1)
                name2 = network.nodes[repo2].get('name', repo2)
                table.add_row(name1, name2, f"{importance:.2f}")
            
            console.print(table)
        
        # Clusters
        if clusters:
            console.print(f"\n📊 Found {len(clusters)} repository clusters:")
            for cluster_id, members in clusters.items():
                names = [network.nodes[m].get('name', m) for m in members[:5]]
                if len(members) > 5:
                    names.append(f"... and {len(members) - 5} more")
                console.print(f"  • {cluster_id}: {', '.join(names)}")
    
    # Export if requested
    if output:
        if format == 'html':
            network.export_to_html(output)
            console.print(f"[green]✓[/green] Network visualization saved to {output}")
        else:
            network_data = network.export_to_json()
            with open(output, 'w') as f:
                json.dump(network_data, f, indent=2)
            console.print(f"[green]✓[/green] Network data saved to {output}")
    
    # Return data for piping
    return network.export_to_json()


@network_cmd.command("config")
@click.option('--output', '-o', type=click.Path(),
              default='network-config.json',
              help='Output file for configuration template')
def config(output):
    """Generate a network configuration template.
    
    Creates a JSON file with weight settings for different link types.
    """
    config = {
        "keyword_weight": 0.3,
        "readme_weight": 0.25,
        "link_weight": 0.2,
        "dependency_weight": 0.15,
        "topic_weight": 0.1,
        "min_link_strength": 0.1,
        "_comment": "Weights should sum to 1.0 for normalized scores"
    }
    
    with open(output, 'w') as f:
        json.dump(config, f, indent=2)
    
    console.print(f"[green]✓[/green] Configuration template saved to {output}")
    console.print("\nEdit the weights to customize network analysis:")
    console.print("  • keyword_weight: Similarity based on repo names and descriptions")
    console.print("  • readme_weight: README content similarity")
    console.print("  • link_weight: Direct links between repositories")
    console.print("  • dependency_weight: Shared package dependencies")
    console.print("  • topic_weight: Common topics and tags")


# Import guard for nullcontext
from contextlib import nullcontext


# Register command with main CLI
def register_command(cli):
    """Register the network command with the main CLI."""
    cli.add_command(network_cmd, name='network')