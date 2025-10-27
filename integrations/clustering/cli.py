"""
CLI commands for repository clustering integration.
"""

import json
import sys
from pathlib import Path
from typing import Optional, List
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core import RepositoryClusterer, ClusteringMethod
from .analyzer import DuplicationAnalyzer, ConsolidationAdvisor

console = Console()


@click.group()
def cluster():
    """Repository clustering and analysis commands."""
    pass


@cluster.command()
@click.option(
    '--method', '-m',
    type=click.Choice(['kmeans', 'dbscan', 'hierarchical', 'network', 'auto']),
    default='auto',
    help='Clustering method to use'
)
@click.option(
    '--n-clusters', '-n',
    type=int,
    default=None,
    help='Number of clusters (for methods that require it)'
)
@click.option(
    '--path', '-p',
    multiple=True,
    help='Repository paths to analyze'
)
@click.option(
    '--recursive', '-r',
    is_flag=True,
    help='Recursively find repositories in directories'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file for results (JSONL format)'
)
@click.option(
    '--pretty',
    is_flag=True,
    help='Display results in pretty table format'
)
def analyze(method, n_clusters, path, recursive, output, pretty):
    """Analyze and cluster repositories based on similarity."""

    # Collect repository paths
    repo_paths = []

    if not path:
        # Use current directory
        path = ['.']

    for p in path:
        p = Path(p)
        if recursive:
            # Find all git repositories
            repo_paths.extend(str(d) for d in p.rglob('.git') if d.is_dir())
            repo_paths = [str(Path(r).parent) for r in repo_paths]
        else:
            if (p / '.git').exists():
                repo_paths.append(str(p))

    if not repo_paths:
        console.print("[red]No repositories found[/red]")
        sys.exit(1)

    console.print(f"[green]Found {len(repo_paths)} repositories[/green]")

    # Initialize clusterer
    clusterer = RepositoryClusterer()

    # Load repositories with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading repositories...", total=len(repo_paths))

        for update in clusterer.load_repositories(repo_paths):
            if not pretty and not output:
                # Stream JSONL to stdout
                print(json.dumps(update), flush=True)
            progress.advance(task)

    # Perform clustering
    method_enum = ClusteringMethod[method.upper()]

    results = []
    for update in clusterer.cluster(method_enum, n_clusters):
        if output:
            results.append(update)
        elif pretty:
            if update.get('action') == 'cluster_result':
                _display_cluster_result(update['cluster'])
        else:
            # Stream JSONL
            print(json.dumps(update), flush=True)

    # Save results if output specified
    if output:
        with open(output, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')
        console.print(f"[green]Results saved to {output}[/green]")


@cluster.command()
@click.option(
    '--path', '-p',
    multiple=True,
    help='Repository paths to analyze'
)
@click.option(
    '--recursive', '-r',
    is_flag=True,
    help='Recursively find repositories'
)
@click.option(
    '--min-similarity', '-s',
    type=float,
    default=0.5,
    help='Minimum similarity threshold for reporting duplicates'
)
@click.option(
    '--pretty',
    is_flag=True,
    help='Display results in pretty format'
)
def find_duplicates(path, recursive, min_similarity, pretty):
    """Find duplicate code across repositories."""

    # Collect repository paths
    repo_paths = []
    if not path:
        path = ['.']

    for p in path:
        p = Path(p)
        if recursive:
            repo_paths.extend(str(d.parent) for d in p.rglob('.git') if d.is_dir())
        else:
            if (p / '.git').exists():
                repo_paths.append(str(p))

    if not repo_paths:
        console.print("[red]No repositories found[/red]")
        sys.exit(1)

    # Initialize analyzer
    analyzer = DuplicationAnalyzer()

    # Analyze repositories
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for repo in repo_paths:
            task = progress.add_task(f"Analyzing {Path(repo).name}...", total=None)

            for update in analyzer.analyze_repository(repo):
                if not pretty:
                    print(json.dumps(update), flush=True)

            progress.remove_task(task)

    # Find duplications
    duplications = list(analyzer.find_duplications())

    if pretty:
        _display_duplication_results(duplications, min_similarity)
    else:
        for dup in duplications:
            if dup.similarity_score >= min_similarity:
                print(json.dumps({
                    "repo1": dup.repo1,
                    "repo2": dup.repo2,
                    "similarity": dup.similarity_score,
                    "shared_lines": dup.total_shared_lines,
                    "recommendation": dup.recommendation
                }), flush=True)


@cluster.command()
@click.option(
    '--path', '-p',
    multiple=True,
    help='Repository paths to analyze'
)
@click.option(
    '--confidence', '-c',
    type=float,
    default=0.7,
    help='Minimum confidence for suggestions'
)
@click.option(
    '--pretty',
    is_flag=True,
    help='Display results in pretty format'
)
def suggest_consolidation(path, confidence, pretty):
    """Suggest repository consolidation opportunities."""

    # Collect repository paths
    repo_paths = []
    if not path:
        path = ['.']

    for p in path:
        p = Path(p)
        if (p / '.git').exists():
            repo_paths.append(str(p))
        else:
            # Find git repos
            repo_paths.extend(str(d.parent) for d in p.rglob('.git') if d.is_dir())

    if len(repo_paths) < 2:
        console.print("[yellow]Need at least 2 repositories for consolidation analysis[/yellow]")
        sys.exit(1)

    # Initialize components
    clusterer = RepositoryClusterer()
    analyzer = DuplicationAnalyzer()

    # Load and cluster repositories
    console.print("[cyan]Analyzing repositories...[/cyan]")

    for _ in clusterer.load_repositories(repo_paths):
        pass

    for _ in clusterer.cluster(ClusteringMethod.AUTO):
        pass

    # Analyze duplications
    for repo in repo_paths:
        for _ in analyzer.analyze_repository(repo):
            pass

    # Generate consolidation suggestions
    advisor = ConsolidationAdvisor(clusterer, analyzer)

    suggestions = []
    for update in advisor.generate_suggestions():
        if update['action'] == 'consolidation_suggestion':
            suggestion = update['suggestion']
            if suggestion['confidence'] >= confidence:
                suggestions.append(suggestion)

                if pretty:
                    _display_consolidation_suggestion(suggestion)
                else:
                    print(json.dumps(suggestion), flush=True)

    if pretty and not suggestions:
        console.print("[green]No consolidation opportunities found above confidence threshold[/green]")


@cluster.command()
@click.option(
    '--input', '-i',
    type=click.Path(exists=True),
    help='Input file with repository list (one per line)'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['json', 'html', 'graphml']),
    default='json',
    help='Export format'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    required=True,
    help='Output file path'
)
def export(input, format, output):
    """Export clustering results in various formats."""

    # Load repository list
    repo_paths = []

    if input:
        with open(input) as f:
            repo_paths = [line.strip() for line in f if line.strip()]
    else:
        # Find repos in current directory
        repo_paths = [str(d.parent) for d in Path('.').rglob('.git') if d.is_dir()]

    if not repo_paths:
        console.print("[red]No repositories found[/red]")
        sys.exit(1)

    # Perform clustering
    clusterer = RepositoryClusterer()

    for _ in clusterer.load_repositories(repo_paths):
        pass

    for _ in clusterer.cluster(ClusteringMethod.AUTO):
        pass

    # Export based on format
    if format == 'json':
        # Export as JSON
        export_data = {
            'repositories': clusterer.repositories,
            'clusters': clusterer.clusters,
            'metadata': {
                'total_repos': len(repo_paths),
                'total_clusters': len(clusterer.clusters),
                'method': 'auto'
            }
        }

        with open(output, 'w') as f:
            json.dump(export_data, f, indent=2)

    elif format == 'html':
        # Use network visualization from network_analysis
        from ghops.integrations.network_analysis import RepositoryNetwork

        network = RepositoryNetwork()
        for repo_path, repo_data in clusterer.repositories.items():
            network.add_repository(repo_data)

        network.build_network()
        network.export_to_html(output)

    elif format == 'graphml':
        # Export as GraphML for use in graph visualization tools
        _export_graphml(clusterer, output)

    console.print(f"[green]Exported to {output}[/green]")


def _display_cluster_result(cluster):
    """Display cluster result in a pretty table."""
    table = Table(title=f"Cluster {cluster['cluster_id']}")
    table.add_column("Repository", style="cyan")
    table.add_column("Language", style="green")
    table.add_column("Topics", style="yellow")

    for repo in cluster['repositories']:
        # Get repo name from path
        name = Path(repo).name
        lang = cluster.get('primary_language', 'Unknown')
        topics = ', '.join(cluster.get('common_topics', []))
        table.add_row(name, lang, topics)

    console.print(table)
    console.print(f"Coherence Score: {cluster['coherence_score']:.2f}")
    console.print(f"Description: {cluster['description']}\n")


def _display_duplication_results(duplications, min_similarity):
    """Display duplication results in a pretty format."""
    table = Table(title="Code Duplication Analysis")
    table.add_column("Repository 1", style="cyan")
    table.add_column("Repository 2", style="cyan")
    table.add_column("Similarity", style="yellow")
    table.add_column("Shared Lines", style="green")
    table.add_column("Recommendation", style="white")

    for dup in duplications:
        if dup.similarity_score >= min_similarity:
            repo1_name = Path(dup.repo1).name
            repo2_name = Path(dup.repo2).name
            similarity = f"{dup.similarity_score:.1%}"

            table.add_row(
                repo1_name,
                repo2_name,
                similarity,
                str(dup.total_shared_lines),
                dup.recommendation
            )

    console.print(table)


def _display_consolidation_suggestion(suggestion):
    """Display consolidation suggestion in a pretty format."""
    console.print("\n[bold cyan]Consolidation Opportunity Found[/bold cyan]")
    console.print(f"[yellow]Confidence: {suggestion['confidence']:.1%}[/yellow]")
    console.print(f"[green]Suggested Name: {suggestion['suggested_name']}[/green]")
    console.print(f"[blue]Estimated Effort: {suggestion['estimated_effort']}[/blue]")

    console.print("\n[bold]Repositories to consolidate:[/bold]")
    for repo in suggestion['repositories']:
        console.print(f"  • {Path(repo).name}")

    console.print(f"\n[bold]Rationale:[/bold] {suggestion['rationale']}")

    if suggestion['common_code_blocks']:
        console.print("\n[bold]Common code blocks:[/bold]")
        for block in suggestion['common_code_blocks'][:5]:
            console.print(f"  • {block}")

    console.print("\n[bold]Benefits:[/bold]")
    for benefit in suggestion['benefits']:
        console.print(f"  ✓ {benefit}")

    console.print("-" * 50)


def _export_graphml(clusterer, output_path):
    """Export clustering results as GraphML."""
    import xml.etree.ElementTree as ET

    # Create GraphML structure
    graphml = ET.Element('graphml')
    graphml.set('xmlns', 'http://graphml.graphdrawing.org/xmlns')

    # Add key definitions
    key_cluster = ET.SubElement(graphml, 'key')
    key_cluster.set('id', 'cluster')
    key_cluster.set('for', 'node')
    key_cluster.set('attr.name', 'cluster')
    key_cluster.set('attr.type', 'int')

    key_name = ET.SubElement(graphml, 'key')
    key_name.set('id', 'name')
    key_name.set('for', 'node')
    key_name.set('attr.name', 'name')
    key_name.set('attr.type', 'string')

    # Create graph
    graph = ET.SubElement(graphml, 'graph')
    graph.set('id', 'G')
    graph.set('edgedefault', 'undirected')

    # Add nodes
    for repo_path in clusterer.repositories:
        node = ET.SubElement(graph, 'node')
        node.set('id', repo_path)

        # Add name
        data_name = ET.SubElement(node, 'data')
        data_name.set('key', 'name')
        data_name.text = Path(repo_path).name

        # Find cluster
        for cluster_id, repos in clusterer.clusters.items():
            if repo_path in repos:
                data_cluster = ET.SubElement(node, 'data')
                data_cluster.set('key', 'cluster')
                data_cluster.text = str(cluster_id)
                break

    # Add edges based on similarity
    if clusterer.similarity_matrix is not None:
        repo_list = list(clusterer.repositories.keys())
        for i in range(len(repo_list)):
            for j in range(i + 1, len(repo_list)):
                similarity = clusterer.similarity_matrix[i, j]
                if similarity > 0.3:  # Only add significant edges
                    edge = ET.SubElement(graph, 'edge')
                    edge.set('source', repo_list[i])
                    edge.set('target', repo_list[j])
                    edge.set('weight', str(similarity))

    # Write to file
    tree = ET.ElementTree(graphml)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)


if __name__ == '__main__':
    cluster()