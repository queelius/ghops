"""
CLI commands for repository clustering and consolidation.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn

from .analyzer import ClusterAnalyzer
from .consolidator import ConsolidationAdvisor
from ...core import get_repository_status
from ...metadata import MetadataStore
from ...cli_utils import handle_errors, validate_paths

logger = logging.getLogger(__name__)
console = Console()


@click.group(name='cluster')
def cluster_group():
    """Repository clustering and consolidation analysis."""
    pass


@cluster_group.command(name='analyze')
@click.option('--path', '-p', multiple=True, help='Repository paths to analyze')
@click.option('--method', '-m',
              type=click.Choice(['hierarchical', 'dbscan', 'network']),
              default='hierarchical',
              help='Clustering method to use')
@click.option('--min-size', type=int, default=2,
              help='Minimum cluster size')
@click.option('--similarity', type=float, default=0.7,
              help='Similarity threshold (0.0-1.0)')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for results (JSONL format)')
@click.option('--pretty', is_flag=True,
              help='Display results in pretty format')
@click.option('--show-duplicates', is_flag=True,
              help='Show potential duplicate repositories')
@click.option('--show-families', is_flag=True,
              help='Show project families')
@click.option('--show-consolidation', is_flag=True,
              help='Show consolidation opportunities')
@handle_errors
def analyze_clusters(path: tuple, method: str, min_size: int, similarity: float,
                    output: Optional[str], pretty: bool, show_duplicates: bool,
                    show_families: bool, show_consolidation: bool):
    """Analyze repository relationships and identify clusters.

    This command performs advanced clustering analysis to:
    - Identify duplicate or near-duplicate repositories
    - Find project families that should be organized together
    - Detect candidates for monorepo consolidation
    - Identify large repositories that should be split

    Examples:
        # Analyze all repositories in current directory
        ghops cluster analyze

        # Use network-based clustering with custom threshold
        ghops cluster analyze --method network --similarity 0.8

        # Show only duplicate repositories
        ghops cluster analyze --show-duplicates

        # Export results to file
        ghops cluster analyze -o clusters.jsonl
    """
    # Get repositories to analyze
    if path:
        repo_paths = list(path)
    else:
        # Use metadata store to get all repositories
        store = MetadataStore()
        repo_paths = list(store.list_repositories())

    if not repo_paths:
        console.print("[yellow]No repositories found to analyze[/yellow]")
        return

    # Initialize analyzer
    config = {
        'min_cluster_size': min_size,
        'similarity_threshold': similarity,
        'clustering_method': method,
    }
    analyzer = ClusterAnalyzer(config)

    # Load repository data with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading repository data...", total=len(repo_paths))

        for repo_path in repo_paths:
            # Get repository metadata
            repo_data = get_repository_status(repo_path)
            if repo_data:
                analyzer.add_repository(repo_data)
            progress.update(task, advance=1)

        # Perform clustering
        progress.add_task("Performing clustering analysis...", total=None)
        clusters = analyzer.perform_clustering(method)

    # Filter results based on options
    results_to_show = []

    if show_duplicates or not (show_families or show_consolidation):
        # Show duplicates by default if no specific filter
        duplicate_clusters = [
            (cid, meta) for cid, meta in analyzer.cluster_metadata.items()
            if meta['cluster_type'] == 'duplicates'
        ]
        results_to_show.extend(duplicate_clusters)

    if show_families:
        family_clusters = [
            (cid, meta) for cid, meta in analyzer.cluster_metadata.items()
            if meta['cluster_type'] == 'project_family'
        ]
        results_to_show.extend(family_clusters)

    if show_consolidation:
        consolidation_clusters = [
            (cid, meta) for cid, meta in analyzer.cluster_metadata.items()
            if meta['cluster_type'] in ['monorepo_candidate', 'split_candidate']
        ]
        results_to_show.extend(consolidation_clusters)

    # If no filters, show all clusters
    if not (show_duplicates or show_families or show_consolidation):
        results_to_show = list(analyzer.cluster_metadata.items())

    # Output results
    if output:
        # Write JSONL output
        with open(output, 'w') as f:
            for line in analyzer.export_clusters_jsonl():
                f.write(line + '\n')
        console.print(f"[green]Results saved to {output}[/green]")

    elif pretty or sys.stdout.isatty():
        # Display pretty output
        _display_cluster_results(results_to_show, analyzer)

    else:
        # Stream JSONL to stdout
        for line in analyzer.export_clusters_jsonl():
            print(line, flush=True)


@cluster_group.command(name='consolidate')
@click.option('--cluster-file', '-f', type=click.Path(exists=True),
              help='Cluster analysis results file')
@click.option('--cluster-id', '-c',
              help='Specific cluster ID to consolidate')
@click.option('--dry-run', is_flag=True,
              help='Show consolidation plan without executing')
@click.option('--generate-scripts', is_flag=True,
              help='Generate automation scripts')
@click.option('--output-dir', '-o', type=click.Path(),
              help='Directory for generated scripts')
@click.option('--pretty', is_flag=True,
              help='Display results in pretty format')
@handle_errors
def consolidate_repos(cluster_file: Optional[str], cluster_id: Optional[str],
                     dry_run: bool, generate_scripts: bool,
                     output_dir: Optional[str], pretty: bool):
    """Generate and execute repository consolidation plans.

    This command creates detailed consolidation plans including:
    - Step-by-step migration instructions
    - Automation scripts for common operations
    - Risk assessment and rollback procedures
    - Migration checklists with validation steps

    Examples:
        # Generate consolidation plan from analysis
        ghops cluster consolidate -f clusters.jsonl

        # Dry run for specific cluster
        ghops cluster consolidate -c cluster_0 --dry-run

        # Generate automation scripts
        ghops cluster consolidate -f clusters.jsonl --generate-scripts -o ./scripts
    """
    if not cluster_file:
        # Run analysis first
        console.print("[yellow]No cluster file provided, running analysis first...[/yellow]")
        # TODO: Run analysis inline
        return

    # Load cluster analysis results
    clusters = {}
    metadata = {}
    repositories = {}

    with open(cluster_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            if data['type'] == 'cluster':
                cluster_id_from_file = data['id']
                clusters[cluster_id_from_file] = data['repositories']
                metadata[cluster_id_from_file] = data
                for repo in data['repositories']:
                    repositories[repo['path']] = repo

    if not clusters:
        console.print("[red]No clusters found in file[/red]")
        return

    # Filter to specific cluster if requested
    if cluster_id:
        if cluster_id not in clusters:
            console.print(f"[red]Cluster {cluster_id} not found[/red]")
            return
        clusters = {cluster_id: clusters[cluster_id]}
        metadata = {cluster_id: metadata[cluster_id]}

    # Initialize consolidation advisor
    advisor = ConsolidationAdvisor({
        'clusters': clusters,
        'metadata': metadata,
        'repositories': repositories,
    })

    # Generate consolidation plans
    plans = advisor.generate_consolidation_plan()

    if not plans:
        console.print("[yellow]No consolidation opportunities found[/yellow]")
        return

    # Generate scripts if requested
    if generate_scripts:
        script_dir = Path(output_dir or './consolidation_scripts')
        script_dir.mkdir(exist_ok=True)

        for plan in plans:
            cluster_dir = script_dir / f"cluster_{plan['cluster_id']}"
            cluster_dir.mkdir(exist_ok=True)

            for script in plan['scripts']:
                script_path = cluster_dir / script['name']
                script_path.write_text(script['content'])
                script_path.chmod(0o755)  # Make executable

            console.print(f"[green]Scripts saved to {cluster_dir}[/green]")

    # Display or output results
    if pretty or sys.stdout.isatty():
        _display_consolidation_plans(plans, dry_run)
    else:
        # Stream JSONL output
        for line in advisor.export_consolidation_jsonl():
            print(line, flush=True)


@cluster_group.command(name='duplicates')
@click.option('--path', '-p', multiple=True, help='Repository paths to analyze')
@click.option('--threshold', type=float, default=0.85,
              help='Similarity threshold for duplicates (0.0-1.0)')
@click.option('--check-content', is_flag=True,
              help='Compare file contents for exact duplicates')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for results')
@click.option('--pretty', is_flag=True,
              help='Display results in pretty format')
@handle_errors
def find_duplicates(path: tuple, threshold: float, check_content: bool,
                   output: Optional[str], pretty: bool):
    """Find potential duplicate repositories.

    Identifies repositories that may be duplicates based on:
    - Name similarity
    - README content comparison
    - File structure similarity
    - Identical file detection (with --check-content)

    Examples:
        # Find duplicates with high confidence
        ghops cluster duplicates --threshold 0.9

        # Check for exact file duplicates
        ghops cluster duplicates --check-content

        # Export results
        ghops cluster duplicates -o duplicates.jsonl
    """
    # Get repositories
    if path:
        repo_paths = list(path)
    else:
        store = MetadataStore()
        repo_paths = list(store.list_repositories())

    # Initialize analyzer
    config = {
        'similarity_threshold': threshold,
        'detection_modes': {'duplicates': True},
    }
    analyzer = ClusterAnalyzer(config)

    # Load repositories
    with console.status("Analyzing repositories for duplicates..."):
        for repo_path in repo_paths:
            repo_data = get_repository_status(repo_path)
            if repo_data:
                analyzer.add_repository(repo_data)

        # Perform clustering
        analyzer.perform_clustering('hierarchical')

        # Find duplicate code if requested
        code_duplicates = []
        if check_content:
            code_duplicates = analyzer.find_duplicate_code()

    # Filter for duplicate clusters
    duplicate_clusters = [
        (cid, meta) for cid, meta in analyzer.cluster_metadata.items()
        if meta['cluster_type'] == 'duplicates'
    ]

    # Output results
    if output:
        with open(output, 'w') as f:
            # Write duplicate clusters
            for cid, meta in duplicate_clusters:
                output_data = {
                    'type': 'duplicate_cluster',
                    'id': cid,
                    'repositories': meta['repositories'],
                    'consolidation': meta['consolidation_potential'],
                }
                f.write(json.dumps(output_data) + '\n')

            # Write code duplicates if found
            for dup in code_duplicates:
                f.write(json.dumps(dup) + '\n')

        console.print(f"[green]Results saved to {output}[/green]")

    elif pretty or sys.stdout.isatty():
        _display_duplicate_results(duplicate_clusters, code_duplicates)

    else:
        # Stream JSONL
        for cid, meta in duplicate_clusters:
            output_data = {
                'type': 'duplicate_cluster',
                'id': cid,
                'repositories': meta['repositories'],
            }
            print(json.dumps(output_data), flush=True)


@cluster_group.command(name='suggest')
@click.option('--path', '-p', multiple=True, help='Repository paths to analyze')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for suggestions')
@click.option('--pretty', is_flag=True,
              help='Display results in pretty format')
@handle_errors
def suggest_structure(path: tuple, output: Optional[str], pretty: bool):
    """Suggest optimal repository structure.

    Analyzes your repositories and suggests:
    - Which repositories to merge
    - Which could become monorepos
    - Which should be split
    - How to organize project families

    Examples:
        # Get structure suggestions
        ghops cluster suggest

        # Export suggestions
        ghops cluster suggest -o structure.json
    """
    # Get repositories
    if path:
        repo_paths = list(path)
    else:
        store = MetadataStore()
        repo_paths = list(store.list_repositories())

    # Initialize analyzer
    analyzer = ClusterAnalyzer()

    # Load and analyze
    with console.status("Analyzing repository structure..."):
        for repo_path in repo_paths:
            repo_data = get_repository_status(repo_path)
            if repo_data:
                analyzer.add_repository(repo_data)

        # Perform clustering
        analyzer.perform_clustering()

        # Get structure suggestions
        suggestions = analyzer.suggest_project_structure()

    # Output results
    if output:
        with open(output, 'w') as f:
            json.dump(suggestions, f, indent=2)
        console.print(f"[green]Suggestions saved to {output}[/green]")

    elif pretty or sys.stdout.isatty():
        _display_structure_suggestions(suggestions)

    else:
        print(json.dumps(suggestions), flush=True)


def _display_cluster_results(results: List[tuple], analyzer: ClusterAnalyzer):
    """Display cluster analysis results in a pretty format."""
    if not results:
        console.print("[yellow]No clusters found[/yellow]")
        return

    console.print(f"\n[bold]Found {len(results)} clusters[/bold]\n")

    for cluster_id, metadata in results:
        # Create panel for each cluster
        panel_content = []

        # Cluster type badge
        cluster_type = metadata['cluster_type']
        type_colors = {
            'duplicates': 'red',
            'project_family': 'blue',
            'monorepo_candidate': 'green',
            'split_candidate': 'yellow',
            'related': 'white',
        }
        color = type_colors.get(cluster_type, 'white')
        panel_content.append(f"[{color}]Type: {cluster_type}[/{color}]")

        # Repository list
        panel_content.append("\nRepositories:")
        for repo_path in metadata['repositories'][:5]:  # Show first 5
            repo_name = Path(repo_path).name
            panel_content.append(f"  • {repo_name}")
        if len(metadata['repositories']) > 5:
            panel_content.append(f"  ... and {len(metadata['repositories']) - 5} more")

        # Common attributes
        if metadata['common_languages']:
            panel_content.append(f"\nLanguages: {', '.join(metadata['common_languages'])}")
        if metadata['common_topics']:
            panel_content.append(f"Topics: {', '.join(metadata['common_topics'][:5])}")

        # Consolidation score
        consolidation = metadata['consolidation_potential']
        if consolidation['score'] > 0.5:
            panel_content.append(f"\n[bold]Consolidation Score: {consolidation['score']:.2f}[/bold]")
            panel_content.append(f"Recommendation: {consolidation['recommendation']}")

        # Insights
        if metadata['insights']:
            panel_content.append("\nInsights:")
            for insight in metadata['insights'][:3]:
                panel_content.append(f"  • {insight}")

        # Create panel
        panel = Panel(
            '\n'.join(panel_content),
            title=f"[bold]{metadata['suggested_name']}[/bold]",
            border_style=color,
        )
        console.print(panel)


def _display_consolidation_plans(plans: List[Dict[str, Any]], dry_run: bool):
    """Display consolidation plans in a pretty format."""
    console.print(f"\n[bold]Consolidation Plans[/bold]\n")

    for plan in plans:
        # Create tree structure for plan
        tree = Tree(f"[bold]{plan['cluster_id']}[/bold] - {plan['action']}")

        # Add metadata
        meta_branch = tree.add("Metadata")
        meta_branch.add(f"Priority Score: {plan['priority_score']:.2f}")
        meta_branch.add(f"Effort: {plan['effort']}")
        meta_branch.add(f"Estimated Time: {plan['estimated_time']}")

        # Add repositories
        repo_branch = tree.add("Affected Repositories")
        for repo in plan['repositories'][:5]:
            repo_branch.add(Path(repo).name)
        if len(plan['repositories']) > 5:
            repo_branch.add(f"... and {len(plan['repositories']) - 5} more")

        # Add benefits
        if plan['benefits']:
            benefit_branch = tree.add("[green]Benefits[/green]")
            for benefit in plan['benefits']:
                benefit_branch.add(benefit)

        # Add risks
        if plan['risks']:
            risk_branch = tree.add("[yellow]Risks[/yellow]")
            for risk in plan['risks']:
                risk_branch.add(risk)

        # Add steps (first 3)
        if plan['steps']:
            step_branch = tree.add("Migration Steps")
            for step in plan['steps'][:3]:
                step_branch.add(f"{step['order']}. {step['description']}")
            if len(plan['steps']) > 3:
                step_branch.add(f"... and {len(plan['steps']) - 3} more steps")

        console.print(tree)
        console.print()

    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be made[/yellow]")


def _display_duplicate_results(duplicate_clusters: List[tuple],
                              code_duplicates: List[Dict]):
    """Display duplicate detection results."""
    if not duplicate_clusters and not code_duplicates:
        console.print("[green]No duplicates found![/green]")
        return

    # Display duplicate repository clusters
    if duplicate_clusters:
        console.print(f"\n[bold]Duplicate Repository Clusters[/bold]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Cluster", style="cyan")
        table.add_column("Repositories", style="white")
        table.add_column("Consolidation Score", justify="center")
        table.add_column("Recommendation", style="yellow")

        for cluster_id, metadata in duplicate_clusters:
            repos = ', '.join(Path(r).name for r in metadata['repositories'][:3])
            if len(metadata['repositories']) > 3:
                repos += f" +{len(metadata['repositories']) - 3}"

            consolidation = metadata['consolidation_potential']
            score = f"{consolidation['score']:.2f}"
            recommendation = consolidation['recommendation'].replace('_', ' ').title()

            table.add_row(cluster_id, repos, score, recommendation)

        console.print(table)

    # Display code duplicates
    if code_duplicates:
        console.print(f"\n[bold]Duplicate Code Files[/bold]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File Hash", style="dim")
        table.add_column("Occurrences", justify="center")
        table.add_column("Repositories", style="white")

        for dup in code_duplicates[:10]:  # Show first 10
            repos = ', '.join(Path(r).name for r in list(dup['repositories'].keys())[:3])
            if len(dup['repositories']) > 3:
                repos += f" +{len(dup['repositories']) - 3}"

            table.add_row(
                dup['hash'][:8] + '...',
                str(dup['file_count']),
                repos
            )

        console.print(table)


def _display_structure_suggestions(suggestions: Dict[str, Any]):
    """Display repository structure suggestions."""
    console.print(f"\n[bold]Repository Structure Analysis[/bold]\n")

    # Statistics
    stats = suggestions['statistics']
    console.print(f"Total Repositories: {suggestions['total_repositories']}")
    console.print(f"Clusters Found: {suggestions['clusters_found']}")
    console.print(f"Duplicate Clusters: {stats['duplicate_clusters']}")
    console.print(f"Monorepo Opportunities: {stats['monorepo_opportunities']}")
    console.print(f"Project Families: {stats['project_families']}")

    # Recommendations
    if suggestions['recommendations']:
        console.print(f"\n[bold]Top Recommendations[/bold]\n")

        for i, rec in enumerate(suggestions['recommendations'][:5], 1):
            priority_colors = {'high': 'red', 'medium': 'yellow', 'low': 'green'}
            color = priority_colors.get(rec['priority'], 'white')

            console.print(f"{i}. [{color}]{rec['action'].replace('_', ' ').title()}[/{color}]")
            console.print(f"   Affects: {len(rec['affected_repos'])} repositories")
            console.print(f"   Effort: {rec['effort']}")
            if rec['benefits']:
                console.print(f"   Benefits: {rec['benefits'][0]}")
            console.print()

    # Proposed structure
    structure = suggestions['proposed_structure']
    if structure.get('monorepos'):
        console.print(f"\n[bold]Suggested Monorepos[/bold]")
        for name in structure['monorepos']:
            console.print(f"  • {name}")

    if structure.get('families'):
        console.print(f"\n[bold]Project Families[/bold]")
        for family in structure['families']:
            console.print(f"  • {family['name']} ({len(family['members'])} members)")


def register_clustering_commands(cli):
    """Register clustering commands with the main CLI.

    Args:
        cli: Main CLI group to add commands to.
    """
    cli.add_command(cluster_group)