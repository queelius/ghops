"""
Export command for generating structured content from repositories.

This command follows our design principles:
- Default output is JSONL streaming
- Multiple export formats supported
- Component-based for customization
- Tag-aware for hierarchical exports
"""

import click
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from datetime import datetime
# yaml import for Hugo export

from ..config import logger, load_config
from ..repo_filter import get_filtered_repos, add_common_repo_options
from ..metadata import get_metadata_store
from ..render import render_table
from ..commands.catalog import get_repositories_by_tags
from ..cli_utils import standard_command, add_common_options
from ..exit_codes import NoReposFoundError


def export_repositories(repos: List[str], format: str,
                       output_dir: str = None, single_file: bool = False,
                       include_metadata: bool = True, group_by: str = None,
                       include_readme: bool = False, readme_length: int = 500,
                       components: str = None, sort_by: str = 'stars',
                       progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """
    Export repositories in various formats.
    
    Args:
        repos: List of repository paths
        format: Output format (markdown, hugo, html, json, csv, pdf, latex)
        output_dir: Output directory
        single_file: Export to single file vs multiple files
        include_metadata: Include full metadata in export
        group_by: Group repositories by tag prefix (e.g., "dir", "lang")
        progress_callback: Optional callback for progress updates
        
    Yields:
        Export status dictionaries
    """
    store = get_metadata_store()
    config = load_config()
    
    # Collect metadata for all repos with progress
    repo_data = []
    if progress_callback:
        progress_callback("Collecting repository metadata...")
    
    # Get all catalog repos once and create a lookup
    catalog_lookup = {}
    try:
        if progress_callback:
            progress_callback("Loading repository tags...")
        catalog_repos = list(get_repositories_by_tags(["repo:*"], config))
        for catalog_repo in catalog_repos:
            catalog_lookup[catalog_repo['path']] = catalog_repo.get('tags', [])
    except Exception:
        # If catalog fails, just continue without tags
        pass
    
    if progress_callback:
        progress_callback(f"Processing {len(repos)} repositories...")
    
    for i, repo_path in enumerate(repos, 1):
        metadata = store.get(repo_path)
        if not metadata:
            # If no metadata in store, create basic metadata
            import os
            metadata = {
                'path': repo_path,
                'name': os.path.basename(repo_path),
                'description': '',
                'language': 'Unknown',
                'stargazers_count': 0,
                'license': None,
                'topics': [],
                'homepage': '',
                'html_url': ''
            }
        
        # Look up tags from pre-built lookup
        repo_tags = catalog_lookup.get(repo_path, [])
        metadata['_tags'] = repo_tags
        repo_data.append(metadata)
        
        # Show progress every 10 repos for large collections
        if progress_callback and i % 10 == 0:
            progress_callback(f"Processed {i}/{len(repos)} repositories...")
    
    # Group repositories if requested
    if group_by:
        if progress_callback:
            progress_callback(f"Grouping repositories by {group_by}...")
        grouped = group_repositories_by_tag(repo_data, group_by)
        if progress_callback:
            progress_callback(f"Created {len(grouped)} groups")
    else:
        grouped = {"all": repo_data}
    
    # Export based on format
    if format == "markdown":
        yield from export_markdown(grouped, output_dir, single_file, 
                                  include_readme, readme_length, components, sort_by,
                                  progress_callback)
    elif format == "hugo":
        from ..hugo_export import export_hugo
        yield from export_hugo(grouped, output_dir, single_file, include_readme, progress_callback)
    elif format == "html":
        yield from export_html(grouped, output_dir, single_file, progress_callback)
    elif format == "json":
        yield from export_json(grouped, output_dir, single_file, progress_callback)
    elif format == "csv":
        yield from export_csv(grouped, output_dir, single_file, progress_callback)
    elif format == "pdf":
        yield from export_pdf(grouped, output_dir, single_file, progress_callback)
    elif format == "latex":
        yield from export_latex(grouped, output_dir, single_file, progress_callback)
    else:
        yield {
            "status": "error",
            "message": f"Unknown format: {format}"
        }


def group_repositories_by_tag(repos: List[Dict], tag_prefix: str) -> Dict[str, List[Dict]]:
    """Group repositories by tag prefix."""
    grouped = {}
    
    for repo in repos:
        tags = repo.get('_tags', [])
        
        # Find matching tags
        group_name = "ungrouped"
        for tag in tags:
            if tag.startswith(f"{tag_prefix}:"):
                group_name = tag.split(':', 1)[1]
                break
        
        if group_name not in grouped:
            grouped[group_name] = []
        grouped[group_name].append(repo)
    
    return grouped


def export_markdown(grouped: Dict[str, List[Dict]], output_dir: str, 
                   single_file: bool, 
                   include_readme: bool = False, readme_length: int = 500,
                   components: str = None, sort_by: str = 'stars',
                   progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as Markdown files."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        # Single markdown file
        output_file = output_path / "repositories.md"
        content = generate_markdown_content(grouped, include_readme, readme_length, components, sort_by)
        
        output_file.write_text(content)
        yield {
            "status": "success",
            "format": "markdown",
            "file": str(output_file),
            "repositories": sum(len(repos) for repos in grouped.values())
        }
    else:
        # Multiple files (one per group)
        for group_name, repos in grouped.items():
            output_file = output_path / f"{group_name}.md"
            content = generate_markdown_content({group_name: repos}, include_readme, readme_length, components, sort_by)
            
            output_file.write_text(content)
            yield {
                "status": "success",
                "format": "markdown",
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_markdown_content(grouped: Dict[str, List[Dict]],
                            include_readme: bool = False, readme_length: int = 500,
                            components: str = None, sort_by: str = 'stars') -> str:
    """Generate Markdown content for repositories."""
    
    from ..export_components import ExportContext, ExportFormat, ExportComposer, default_registry
    # Import components to register them - must be done after export_components is loaded
    from ..export_components_impl import (
        HeaderComponent, SummaryStatisticsComponent, 
        TagCloudComponent, RepositoryCardsComponent,
        ReadmeContentComponent
    )
    
    # Flatten grouped repos for component system
    all_repos = []
    for repos in grouped.values():
        all_repos.extend(repos)
    
    # Create context
    context = ExportContext(
        format=ExportFormat.MARKDOWN,
        repositories=all_repos,
        config={
            'title': 'Repository Portfolio',
            'group_by': None if len(grouped) == 1 else 'group',
            'show_details': True,
            'sort_by': sort_by,
            'include_readme': include_readme,
            'readme_length': readme_length
        }
    )
    
    # Create composer with default or specified components
    composer = ExportComposer(default_registry)
    
    if components:
        # Use specified components
        component_list = [c.strip() for c in components.split(',')]
        for i, comp_name in enumerate(component_list):
            composer.add_component(comp_name, priority=(i + 1) * 10)
    else:
        # Use default components
        composer.add_component('header', priority=10)
        composer.add_component('summary_stats', priority=20)
        composer.add_component('tag_cloud', priority=30)
        composer.add_component('repository_cards', priority=40)
        if include_readme:
            composer.add_component('readme_content', priority=50)
    
    return composer.compose(context)


# Hugo export needs to be reimplemented with components


def export_html(grouped: Dict[str, List[Dict]], output_dir: str,
                single_file: bool, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as HTML files."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        output_file = output_path / "repositories.html"
        content = generate_html_content(grouped)
        
        output_file.write_text(content)
        yield {
            "status": "success",
            "format": "html",
            "file": str(output_file),
            "repositories": sum(len(repos) for repos in grouped.values())
        }
    else:
        # Create index page
        index_file = output_path / "index.html"
        index_content = generate_html_index(grouped)
        index_file.write_text(index_content)
        
        yield {
            "status": "success",
            "format": "html",
            "file": str(index_file),
            "type": "index"
        }
        
        # Create group pages
        for group_name, repos in grouped.items():
            group_file = output_path / f"{group_name.lower().replace(' ', '-')}.html"
            content = generate_html_content({group_name: repos})
            
            group_file.write_text(content)
            yield {
                "status": "success",
                "format": "html",
                "file": str(group_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_html_content(grouped: Dict[str, List[Dict]],
                         include_readme: bool = False, readme_length: int = 500,
                         components: str = None, sort_by: str = 'stars') -> str:
    """Generate HTML content for repositories."""
    
    from ..export_components import ExportContext, ExportFormat, ExportComposer, default_registry
    # Import components to register them - must be done after export_components is loaded
    from ..export_components_impl import (
        HeaderComponent, SummaryStatisticsComponent, 
        TagCloudComponent, RepositoryCardsComponent,
        ReadmeContentComponent
    )
    
    # Flatten grouped repos for component system
    all_repos = []
    for repos in grouped.values():
        all_repos.extend(repos)
    
    # Create context
    context = ExportContext(
        format=ExportFormat.HTML,
        repositories=all_repos,
        config={
            'title': 'Repository Portfolio',
            'group_by': None if len(grouped) == 1 else 'group',
            'show_details': True,
            'sort_by': sort_by,
            'include_readme': include_readme,
            'readme_length': readme_length
        }
    )
    
    # Create composer with default or specified components
    composer = ExportComposer(default_registry)
    
    if components:
        # Use specified components
        component_list = [c.strip() for c in components.split(',')]
        for i, comp_name in enumerate(component_list):
            composer.add_component(comp_name, priority=(i + 1) * 10)
    else:
        # Use default components
        composer.add_component('header', priority=10)
        composer.add_component('summary_stats', priority=20)
        composer.add_component('tag_cloud', priority=30)
        composer.add_component('repository_cards', priority=40)
        if include_readme:
            composer.add_component('readme_content', priority=50)
    
    # Generate component HTML
    component_html = composer.compose(context)
    
    # Wrap in HTML document with styling
    # Default HTML with interactive features
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repository Portfolio</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background-color: #24292e;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .filters {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .filter-group {
            display: inline-block;
            margin-right: 20px;
        }
        .repo-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .repo-card {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .repo-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .repo-name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #0366d6;
        }
        .repo-description {
            color: #586069;
            margin-bottom: 15px;
            font-size: 0.9em;
        }
        .repo-meta {
            display: flex;
            gap: 15px;
            font-size: 0.85em;
            color: #586069;
        }
        .repo-meta-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .tag {
            display: inline-block;
            padding: 2px 8px;
            background-color: #e1e4e8;
            border-radius: 3px;
            font-size: 0.8em;
            margin-right: 5px;
        }
        .search-box {
            width: 100%;
            padding: 10px;
            border: 1px solid #e1e4e8;
            border-radius: 4px;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Repository Portfolio</h1>
        <p>Generated on """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>
    
    <div class="filters">
        <div class="filter-group">
            <input type="text" id="search" class="search-box" placeholder="Search repositories...">
        </div>
        <div class="filter-group">
            <label for="language-filter">Language:</label>
            <select id="language-filter">
                <option value="">All</option>
            </select>
        </div>
        <div class="filter-group">
            <label for="sort-by">Sort by:</label>
            <select id="sort-by">
                <option value="name">Name</option>
                <option value="stars">Stars</option>
                <option value="updated">Last Updated</option>
            </select>
        </div>
    </div>
    
    <div class="repo-grid" id="repo-grid">
"""
    
    # Add repository cards
    for group_name, repos in grouped.items():
        for repo in repos:
            html += f"""
        <div class="repo-card" data-name="{repo.get('name', '').lower()}" 
             data-language="{repo.get('language', '').lower()}"
             data-stars="{repo.get('stargazers_count', 0)}"
             data-updated="{repo.get('updated_at', '')}">
            <div class="repo-name">{repo.get('name', 'Unknown')}</div>
            <div class="repo-description">{repo.get('description', 'No description available')}</div>
            <div class="repo-meta">
                <div class="repo-meta-item">
                    <span>📝</span> {repo.get('language', 'Unknown')}
                </div>
                <div class="repo-meta-item">
                    <span>⭐</span> {repo.get('stargazers_count', 0)}
                </div>
                <div class="repo-meta-item">
                    <span>📄</span> {(repo.get('license') or {}).get('spdx_id', 'No license')}
                </div>
            </div>
            <div style="margin-top: 10px;">
"""
            
            # Add topics as tags
            for topic in repo.get('topics', []):
                html += f'<span class="tag">{topic}</span>'
            
            html += """
            </div>
        </div>
"""
    
    html += """
    </div>
    
    <script>
        // Collect all languages
        const languages = new Set();
        document.querySelectorAll('.repo-card').forEach(card => {
            const lang = card.dataset.language;
            if (lang && lang !== 'unknown') languages.add(lang);
        });
        
        // Populate language filter
        const langFilter = document.getElementById('language-filter');
        Array.from(languages).sort().forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
            langFilter.appendChild(option);
        });
        
        // Filter function
        function filterRepos() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const selectedLang = document.getElementById('language-filter').value;
            const sortBy = document.getElementById('sort-by').value;
            
            const cards = Array.from(document.querySelectorAll('.repo-card'));
            
            // Filter
            cards.forEach(card => {
                const name = card.dataset.name;
                const lang = card.dataset.language;
                
                const matchesSearch = !searchTerm || name.includes(searchTerm);
                const matchesLang = !selectedLang || lang === selectedLang;
                
                card.style.display = matchesSearch && matchesLang ? 'block' : 'none';
            });
            
            // Sort
            const visibleCards = cards.filter(card => card.style.display !== 'none');
            visibleCards.sort((a, b) => {
                if (sortBy === 'name') {
                    return a.dataset.name.localeCompare(b.dataset.name);
                } else if (sortBy === 'stars') {
                    return parseInt(b.dataset.stars) - parseInt(a.dataset.stars);
                } else if (sortBy === 'updated') {
                    return b.dataset.updated.localeCompare(a.dataset.updated);
                }
            });
            
            // Reorder in DOM
            const grid = document.getElementById('repo-grid');
            visibleCards.forEach(card => grid.appendChild(card));
        }
        
        // Attach event listeners
        document.getElementById('search').addEventListener('input', filterRepos);
        document.getElementById('language-filter').addEventListener('change', filterRepos);
        document.getElementById('sort-by').addEventListener('change', filterRepos);
    </script>
</body>
</html>"""
    
    return html


def generate_html_index(grouped: Dict[str, List[Dict]]) -> str:
    """Generate HTML index page for multiple groups."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repository Portfolio - Index</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .group-link {
            display: block;
            padding: 15px;
            margin: 10px 0;
            background-color: #f5f5f5;
            border-radius: 8px;
            text-decoration: none;
            color: #333;
            transition: background-color 0.2s;
        }
        .group-link:hover {
            background-color: #e1e4e8;
        }
    </style>
</head>
<body>
    <h1>Repository Portfolio</h1>
    <p>Select a category to view repositories:</p>
"""
    
    for group_name, repos in sorted(grouped.items()):
        html += f"""
    <a href="{group_name.lower().replace(' ', '-')}.html" class="group-link">
        <h3>{group_name}</h3>
        <p>{len(repos)} repositories</p>
    </a>
"""
    
    html += """
</body>
</html>"""
    
    return html


def export_json(grouped: Dict[str, List[Dict]], output_dir: str,
                single_file: bool, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as JSON."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        output_file = output_path / "repositories.json"
        
        # Clean up internal fields
        clean_data = {}
        for group_name, repos in grouped.items():
            clean_repos = []
            for repo in repos:
                clean_repo = {k: v for k, v in repo.items() if not k.startswith('_')}
                clean_repos.append(clean_repo)
            clean_data[group_name] = clean_repos
        
        output_file.write_text(json.dumps(clean_data, indent=2, ensure_ascii=False))
        
        yield {
            "status": "success",
            "format": "json",
            "file": str(output_file),
            "repositories": sum(len(repos) for repos in grouped.values())
        }
    else:
        for group_name, repos in grouped.items():
            output_file = output_path / f"{group_name.lower().replace(' ', '-')}.json"
            
            clean_repos = []
            for repo in repos:
                clean_repo = {k: v for k, v in repo.items() if not k.startswith('_')}
                clean_repos.append(clean_repo)
            
            output_file.write_text(json.dumps(clean_repos, indent=2, ensure_ascii=False))
            
            yield {
                "status": "success",
                "format": "json",
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def export_csv(grouped: Dict[str, List[Dict]], output_dir: str,
               single_file: bool, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as CSV."""
    import csv
    
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    # Define CSV columns
    columns = ['name', 'description', 'language', 'stars', 'forks', 'license',
               'created_at', 'updated_at', 'homepage', 'repository_url', 'topics']
    
    if single_file:
        output_file = output_path / "repositories.csv"
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns + ['group'])
            writer.writeheader()
            
            for group_name, repos in grouped.items():
                for repo in repos:
                    row = {
                        'name': repo.get('name', ''),
                        'description': repo.get('description', ''),
                        'language': repo.get('language', ''),
                        'stars': repo.get('stargazers_count', 0),
                        'forks': repo.get('forks_count', 0),
                        'license': (repo.get('license') or {}).get('name', ''),
                        'created_at': repo.get('created_at', ''),
                        'updated_at': repo.get('updated_at', ''),
                        'homepage': repo.get('homepage', ''),
                        'repository_url': repo.get('html_url', ''),
                        'topics': ', '.join(repo.get('topics', [])),
                        'group': group_name
                    }
                    writer.writerow(row)
        
        yield {
            "status": "success",
            "format": "csv",
            "file": str(output_file),
            "repositories": sum(len(repos) for repos in grouped.values())
        }
    else:
        for group_name, repos in grouped.items():
            output_file = output_path / f"{group_name.lower().replace(' ', '-')}.csv"
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                
                for repo in repos:
                    row = {
                        'name': repo.get('name', ''),
                        'description': repo.get('description', ''),
                        'language': repo.get('language', ''),
                        'stars': repo.get('stargazers_count', 0),
                        'forks': repo.get('forks_count', 0),
                        'license': (repo.get('license') or {}).get('name', ''),
                        'created_at': repo.get('created_at', ''),
                        'updated_at': repo.get('updated_at', ''),
                        'homepage': repo.get('homepage', ''),
                        'repository_url': repo.get('html_url', ''),
                        'topics': ', '.join(repo.get('topics', []))
                    }
                    writer.writerow(row)
            
            yield {
                "status": "success",
                "format": "csv", 
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def export_pdf(grouped: Dict[str, List[Dict]], output_dir: str,
               single_file: bool, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as PDF (requires additional dependencies)."""
    # For now, generate LaTeX and note that it needs to be compiled
    yield from export_latex(grouped, output_dir, single_file, progress_callback)
    
    yield {
        "status": "info",
        "message": "LaTeX files generated. Compile with pdflatex to create PDFs."
    }


def export_latex(grouped: Dict[str, List[Dict]], output_dir: str,
                 single_file: bool, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as LaTeX documents."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        output_file = output_path / "repositories.tex"
        content = generate_latex_content(grouped)
        
        output_file.write_text(content)
        yield {
            "status": "success",
            "format": "latex",
            "file": str(output_file),
            "repositories": sum(len(repos) for repos in grouped.values())
        }
    else:
        for group_name, repos in grouped.items():
            output_file = output_path / f"{group_name.lower().replace(' ', '-')}.tex"
            content = generate_latex_content({group_name: repos})
            
            output_file.write_text(content)
            yield {
                "status": "success",
                "format": "latex",
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_latex_content(grouped: Dict[str, List[Dict]]) -> str:
    """Generate LaTeX content for repositories."""
    # Default LaTeX content
    tex = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=1in]{geometry}
\usepackage{hyperref}
\usepackage{listings}
\usepackage{xcolor}
\usepackage{graphicx}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,      
    urlcolor=cyan,
}

\title{Repository Portfolio}
\author{Generated by ghops}
\date{""" + datetime.now().strftime('%B %d, %Y') + r"""}

\begin{document}

\maketitle
\tableofcontents
\newpage

"""
    
    for group_name, repos in sorted(grouped.items()):
        if len(grouped) > 1:
            tex += f"\\section{{{group_name}}}\n\n"
        
        for repo in sorted(repos, key=lambda r: r.get('name', '')):
            # Escape LaTeX special characters
            name = repo.get('name', 'Unknown').replace('_', r'\_')
            desc = repo.get('description', 'No description').replace('_', r'\_').replace('#', r'\#').replace('&', r'\&')
            
            tex += f"\\subsection{{{name}}}\n\n"
            tex += f"\\textit{{{desc}}}\n\n"
            
            tex += r"\begin{itemize}" + "\n"
            tex += f"\\item \\textbf{{Language:}} {repo.get('language', 'Unknown')}\n"
            tex += f"\\item \\textbf{{Stars:}} {repo.get('stargazers_count', 0)}\n"
            tex += f"\\item \\textbf{{License:}} {(repo.get('license') or {}).get('name', 'No license')}\n"
            
            if repo.get('homepage'):
                tex += f"\\item \\textbf{{Homepage:}} \\url{{{repo['homepage']}}}\n"
            if repo.get('html_url'):
                tex += f"\\item \\textbf{{Repository:}} \\url{{{repo['html_url']}}}\n"
            
            topics = repo.get('topics', [])
            if topics:
                tex += f"\\item \\textbf{{Topics:}} {', '.join(topics)}\n"
            
            tex += r"\end{itemize}" + "\n\n"
    
    tex += r"\end{document}"
    
    return tex




@click.group("export")
def export_cmd():
    """Export repository data in various formats."""
    pass


@export_cmd.command()
@add_common_repo_options
@click.option('-f', '--format', type=click.Choice(['markdown', 'hugo', 'html', 'json', 'csv', 'pdf', 'latex']),
              default='markdown', help='Export format')
@click.option('-o', '--output', 'output_dir', help='Output directory')
@click.option('--single-file', is_flag=True, help='Export to single file instead of multiple')
@click.option('--group-by', help='Group repositories by tag prefix (e.g., "dir", "lang") or attribute (language, license, year)')
@click.option('--include-metadata', is_flag=True, default=True, help='Include full metadata')
@click.option('--include-readme', is_flag=True, help='Include README content in export')
@click.option('--readme-length', type=int, default=500, help='Maximum README length to include (0 for full)')
@click.option('--components', help='Comma-separated list of components to include (e.g., header,summary_stats,tag_cloud,repository_cards,readme_content)')
@click.option('--sort-by', type=click.Choice(['stars', 'name', 'updated', 'created']), default='stars', help='Sort repositories by')
@add_common_options('verbose', 'quiet')
@standard_command(streaming=True)
def generate(dir, recursive, tag_filters, all_tags, query,
            format, output_dir, single_file, group_by, include_metadata, 
            include_readme, readme_length, components, sort_by,
            progress, quiet, **kwargs):
    """Generate portfolio exports from repositories.
    
    \b
    Export repositories in various formats using components.
    Supports Hugo static sites, Markdown, HTML, PDF, and more.
    
    Examples:
    
    \b
        ghops export generate --format markdown -o docs/
        ghops export generate --format html --single-file  
        ghops export generate --group-by lang --format hugo
        ghops export generate --include-readme --components header,summary_stats
    """
    config = load_config()
    
    progress(f"Discovering repositories...")
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        raise NoReposFoundError(error_msg)
    
    progress(f"Found {len(repos)} repositories to export")
    
    
    progress(f"Export format: {format}")
    if output_dir:
        progress(f"Output directory: {output_dir}")
    
    # Track stats
    files_created = []
    total_repos_exported = 0
    
    # Export repositories with progress
    progress(f"Starting {format} export...")
    
    # Create export generator with progress callback
    export_gen = export_repositories(
        repos=repos,
        format=format,
        output_dir=output_dir,
        single_file=single_file,
        include_metadata=include_metadata,
        group_by=group_by,
        include_readme=include_readme,
        readme_length=readme_length if readme_length != 0 else None,
        components=components,
        sort_by=sort_by,
        progress_callback=progress
    )
    
    # Process exports with progress tracking  
    export_count = 0
    with progress.task(f"Creating {format} files", total=None) as update:
        for export_result in export_gen:
            export_count += 1
            
            # Update progress based on export result
            if export_result.get('status') == 'success':
                file_path = export_result.get('file')
                if file_path:
                    files_created.append(file_path)
                    filename = Path(file_path).name
                    update(export_count, filename)
                    
                repos_in_file = export_result.get('repositories', 0)
                if repos_in_file:
                    total_repos_exported += repos_in_file
                    
            elif export_result.get('status') == 'error':
                error_msg = export_result.get('message', export_result.get('error', 'Unknown error'))
                progress.error(f"Failed: {error_msg}")
                update(export_count, "error")
            elif export_result.get('status') == 'info':
                info_msg = export_result.get('message', '')
                if info_msg:
                    progress(info_msg)
                update(export_count, "info")
            
            # Stream result if not quiet
            if not quiet:
                yield export_result
    
    # Summary
    progress("")
    progress("Export Summary:")
    progress(f"  Format: {format}")
    progress(f"  Files created: {len(files_created)}")
    progress(f"  Repositories exported: {total_repos_exported}")
    
    if output_dir:
        progress(f"  Output directory: {output_dir}")
    
        
    if files_created and len(files_created) <= 10:
        progress("")
        progress("Files created:")
        for file_path in files_created:
            progress(f"  - {file_path}")
    elif files_created:
        progress(f"  Created {len(files_created)} files in {output_dir or '.'}")
    
    progress.success("Export completed successfully!")



# Add customize subcommand to export group
from .customize import customize
export_cmd.add_command(customize)