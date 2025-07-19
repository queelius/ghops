"""
Export command for generating structured content from repositories.

This command follows our design principles:
- Default output is JSONL streaming
- Multiple export formats supported
- Template-based for customization
- Tag-aware for hierarchical exports
"""

import click
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from datetime import datetime
import yaml

from ..config import logger, load_config
from ..repo_filter import get_filtered_repos, add_common_repo_options
from ..metadata import get_metadata_store
from ..render import render_table
from ..commands.catalog import get_repositories_by_tags


def export_repositories(repos: List[str], format: str, template: str = None,
                       output_dir: str = None, single_file: bool = False,
                       include_metadata: bool = True, group_by: str = None) -> Generator[Dict[str, Any], None, None]:
    """
    Export repositories in various formats.
    
    Args:
        repos: List of repository paths
        format: Output format (markdown, hugo, html, json, csv, pdf, latex)
        template: Template name or path
        output_dir: Output directory
        single_file: Export to single file vs multiple files
        include_metadata: Include full metadata in export
        group_by: Group repositories by tag prefix (e.g., "dir", "lang")
        
    Yields:
        Export status dictionaries
    """
    store = get_metadata_store()
    config = load_config()
    
    # Collect metadata for all repos
    repo_data = []
    for repo_path in repos:
        metadata = store.get(repo_path)
        if metadata:
            # Get tags for this repo
            repo_tags = []
            catalog_repos = list(get_repositories_by_tags(["repo:*"], config))
            for catalog_repo in catalog_repos:
                if catalog_repo['path'] == repo_path:
                    repo_tags = catalog_repo.get('tags', [])
                    break
            
            metadata['_tags'] = repo_tags
            repo_data.append(metadata)
    
    # Group repositories if requested
    if group_by:
        grouped = group_repositories_by_tag(repo_data, group_by)
    else:
        grouped = {"all": repo_data}
    
    # Export based on format
    if format == "markdown":
        yield from export_markdown(grouped, output_dir, single_file, template)
    elif format == "hugo":
        yield from export_hugo(grouped, output_dir, template)
    elif format == "html":
        yield from export_html(grouped, output_dir, single_file, template)
    elif format == "json":
        yield from export_json(grouped, output_dir, single_file)
    elif format == "csv":
        yield from export_csv(grouped, output_dir, single_file)
    elif format == "pdf":
        yield from export_pdf(grouped, output_dir, single_file, template)
    elif format == "latex":
        yield from export_latex(grouped, output_dir, single_file, template)
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
                   single_file: bool, template: str = None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as Markdown files."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        # Single markdown file
        output_file = output_path / "repositories.md"
        content = generate_markdown_content(grouped, template)
        
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
            content = generate_markdown_content({group_name: repos}, template)
            
            output_file.write_text(content)
            yield {
                "status": "success",
                "format": "markdown",
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_markdown_content(grouped: Dict[str, List[Dict]], template: str = None) -> str:
    """Generate Markdown content for repositories."""
    if template:
        # Load custom template
        return apply_template(grouped, template, "markdown")
    
    # Default markdown template
    lines = ["# Repository Portfolio", ""]
    lines.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Table of contents
    if len(grouped) > 1:
        lines.append("## Table of Contents")
        lines.append("")
        for group_name in sorted(grouped.keys()):
            lines.append(f"- [{group_name}](#{group_name.lower().replace(' ', '-')})")
        lines.append("")
    
    # Repository sections
    for group_name, repos in sorted(grouped.items()):
        if len(grouped) > 1:
            lines.append(f"## {group_name}")
            lines.append("")
        
        for repo in sorted(repos, key=lambda r: r.get('name', '')):
            lines.append(f"### {repo.get('name', 'Unknown')}")
            lines.append("")
            
            # Description
            desc = repo.get('description', 'No description available')
            lines.append(f"*{desc}*")
            lines.append("")
            
            # Key info
            lines.append("**Details:**")
            lines.append(f"- Language: {repo.get('language', 'Unknown')}")
            lines.append(f"- Stars: {repo.get('stargazers_count', 0)}")
            lines.append(f"- License: {repo.get('license', {}).get('name', 'No license')}")
            
            # Links
            if repo.get('homepage'):
                lines.append(f"- Homepage: [{repo['homepage']}]({repo['homepage']})")
            if repo.get('html_url'):
                lines.append(f"- Repository: [{repo['html_url']}]({repo['html_url']})")
            
            # Topics/Tags
            topics = repo.get('topics', [])
            if topics:
                lines.append(f"- Topics: {', '.join(topics)}")
            
            lines.append("")
    
    return "\n".join(lines)


def export_hugo(grouped: Dict[str, List[Dict]], output_dir: str, 
                template: str = None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as Hugo content."""
    output_path = Path(output_dir) if output_dir else Path("content/repositories")
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create _index.md for the section
    index_content = generate_hugo_index(grouped)
    (output_path / "_index.md").write_text(index_content)
    
    # Create individual pages for each repository
    for group_name, repos in grouped.items():
        group_path = output_path / group_name.lower().replace(' ', '-')
        group_path.mkdir(exist_ok=True)
        
        # Group index
        group_index = generate_hugo_group_index(group_name, repos)
        (group_path / "_index.md").write_text(group_index)
        
        # Individual repo pages
        for repo in repos:
            repo_slug = repo.get('name', 'unknown').lower().replace(' ', '-')
            repo_file = group_path / f"{repo_slug}.md"
            
            content = generate_hugo_repo_page(repo, group_name)
            repo_file.write_text(content)
            
            yield {
                "status": "success",
                "format": "hugo",
                "file": str(repo_file),
                "repository": repo.get('name'),
                "group": group_name
            }


def generate_hugo_index(grouped: Dict[str, List[Dict]]) -> str:
    """Generate Hugo section index page."""
    total_repos = sum(len(repos) for repos in grouped.values())
    
    front_matter = {
        "title": "Repository Portfolio",
        "date": datetime.now().isoformat(),
        "type": "repositories",
        "layout": "list",
        "summary": f"Portfolio of {total_repos} repositories",
        "menu": {
            "main": {
                "name": "Repositories",
                "weight": 10
            }
        }
    }
    
    content = f"---\n{yaml.dump(front_matter, default_flow_style=False)}---\n\n"
    content += "# Repository Portfolio\n\n"
    content += f"This portfolio contains {total_repos} repositories organized by category.\n\n"
    
    # Statistics
    content += "## Statistics\n\n"
    
    # Language distribution
    lang_counts = {}
    for repos in grouped.values():
        for repo in repos:
            lang = repo.get('language', 'Unknown')
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    
    content += "### Languages\n\n"
    for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
        content += f"- {lang}: {count} repositories\n"
    
    return content


def generate_hugo_group_index(group_name: str, repos: List[Dict]) -> str:
    """Generate Hugo group index page."""
    front_matter = {
        "title": group_name.title(),
        "date": datetime.now().isoformat(),
        "type": "repositories",
        "layout": "list",
        "summary": f"{len(repos)} repositories in {group_name}"
    }
    
    content = f"---\n{yaml.dump(front_matter, default_flow_style=False)}---\n\n"
    content += f"# {group_name.title()}\n\n"
    content += f"This section contains {len(repos)} repositories.\n\n"
    
    return content


def generate_hugo_repo_page(repo: Dict, group_name: str) -> str:
    """Generate Hugo page for individual repository."""
    front_matter = {
        "title": repo.get('name', 'Unknown'),
        "date": repo.get('created_at', datetime.now().isoformat()),
        "lastmod": repo.get('updated_at', datetime.now().isoformat()),
        "type": "repository",
        "layout": "single",
        "summary": repo.get('description', 'No description available'),
        "tags": repo.get('topics', []),
        "categories": [group_name],
        "params": {
            "language": repo.get('language', 'Unknown'),
            "stars": repo.get('stargazers_count', 0),
            "forks": repo.get('forks_count', 0),
            "license": repo.get('license', {}).get('key', 'none'),
            "homepage": repo.get('homepage', ''),
            "repository_url": repo.get('html_url', ''),
            "owner": repo.get('owner', '')
        }
    }
    
    content = f"---\n{yaml.dump(front_matter, default_flow_style=False)}---\n\n"
    
    # Main content
    content += f"# {repo.get('name', 'Unknown')}\n\n"
    content += f"{repo.get('description', 'No description available')}\n\n"
    
    # Repository details
    content += "## Details\n\n"
    content += f"- **Language:** {repo.get('language', 'Unknown')}\n"
    content += f"- **Stars:** {repo.get('stargazers_count', 0)}\n"
    content += f"- **Forks:** {repo.get('forks_count', 0)}\n"
    content += f"- **License:** {repo.get('license', {}).get('name', 'No license')}\n"
    content += f"- **Created:** {repo.get('created_at', 'Unknown')}\n"
    content += f"- **Last Updated:** {repo.get('updated_at', 'Unknown')}\n"
    
    # Links
    content += "\n## Links\n\n"
    if repo.get('homepage'):
        content += f"- [Project Homepage]({repo['homepage']})\n"
    if repo.get('html_url'):
        content += f"- [GitHub Repository]({repo['html_url']})\n"
    
    # Topics
    topics = repo.get('topics', [])
    if topics:
        content += "\n## Topics\n\n"
        content += ", ".join(f"`{topic}`" for topic in topics)
        content += "\n"
    
    return content


def export_html(grouped: Dict[str, List[Dict]], output_dir: str,
                single_file: bool, template: str = None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as HTML files."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        output_file = output_path / "repositories.html"
        content = generate_html_content(grouped, template)
        
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
            content = generate_html_content({group_name: repos}, template)
            
            group_file.write_text(content)
            yield {
                "status": "success",
                "format": "html",
                "file": str(group_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_html_content(grouped: Dict[str, List[Dict]], template: str = None) -> str:
    """Generate HTML content for repositories."""
    if template:
        return apply_template(grouped, template, "html")
    
    # Default HTML template with interactive features
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
                    <span>📄</span> {repo.get('license', {}).get('spdx_id', 'No license')}
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
                single_file: bool) -> Generator[Dict[str, Any], None, None]:
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
               single_file: bool) -> Generator[Dict[str, Any], None, None]:
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
                        'license': repo.get('license', {}).get('name', ''),
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
                        'license': repo.get('license', {}).get('name', ''),
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
               single_file: bool, template: str = None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as PDF (requires additional dependencies)."""
    # For now, generate LaTeX and note that it needs to be compiled
    yield from export_latex(grouped, output_dir, single_file, template)
    
    yield {
        "status": "info",
        "message": "LaTeX files generated. Compile with pdflatex to create PDFs."
    }


def export_latex(grouped: Dict[str, List[Dict]], output_dir: str,
                 single_file: bool, template: str = None) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as LaTeX documents."""
    output_path = Path(output_dir) if output_dir else Path(".")
    output_path.mkdir(exist_ok=True)
    
    if single_file:
        output_file = output_path / "repositories.tex"
        content = generate_latex_content(grouped, template)
        
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
            content = generate_latex_content({group_name: repos}, template)
            
            output_file.write_text(content)
            yield {
                "status": "success",
                "format": "latex",
                "file": str(output_file),
                "group": group_name,
                "repositories": len(repos)
            }


def generate_latex_content(grouped: Dict[str, List[Dict]], template: str = None) -> str:
    """Generate LaTeX content for repositories."""
    if template:
        return apply_template(grouped, template, "latex")
    
    # Default LaTeX template
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
            tex += f"\\item \\textbf{{License:}} {repo.get('license', {}).get('name', 'No license')}\n"
            
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


def apply_template(grouped: Dict[str, List[Dict]], template_path: str, format: str) -> str:
    """Apply a custom template to the data."""
    # TODO: Implement template engine (Jinja2, etc.)
    # For now, return default content
    if format == "markdown":
        return generate_markdown_content(grouped)
    elif format == "html":
        return generate_html_content(grouped)
    elif format == "latex":
        return generate_latex_content(grouped)
    else:
        return ""


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
@click.option('--template', help='Template name or path')
@click.option('--group-by', help='Group repositories by tag prefix (e.g., "dir", "lang")')
@click.option('--include-metadata', is_flag=True, default=True, help='Include full metadata')
@click.option('--pretty', is_flag=True, help='Display export progress')
def generate(dir, recursive, tag_filters, all_tags, query,
            format, output_dir, single_file, template, group_by, include_metadata, pretty):
    """Generate portfolio exports from repositories."""
    config = load_config()
    
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
        logger.error(error_msg)
        return
    
    # Export repositories
    exports = export_repositories(
        repos=repos,
        format=format,
        template=template,
        output_dir=output_dir,
        single_file=single_file,
        include_metadata=include_metadata,
        group_by=group_by
    )
    
    if pretty:
        # Collect results for summary
        results = list(exports)
        
        # Summary
        success_count = sum(1 for r in results if r.get('status') == 'success')
        total_repos = sum(r.get('repositories', 0) for r in results if r.get('repositories'))
        
        print(f"\n✨ Export completed!")
        print(f"   Format: {format}")
        print(f"   Files created: {success_count}")
        print(f"   Repositories exported: {total_repos}")
        
        if output_dir:
            print(f"   Output directory: {output_dir}")
        
        # Show files created
        print("\nFiles created:")
        for result in results:
            if result.get('status') == 'success' and result.get('file'):
                print(f"   - {result['file']}")
    else:
        # Stream JSONL output
        for export in exports:
            print(json.dumps(export, ensure_ascii=False), flush=True)


@export_cmd.command("templates")
@click.option('--list', 'list_templates', is_flag=True, help='List available templates')
@click.option('--show', help='Show template content')
@click.option('--create', help='Create new template')
def templates(list_templates, show, create):
    """Manage export templates."""
    template_dir = Path.home() / ".ghops" / "templates"
    template_dir.mkdir(exist_ok=True)
    
    if list_templates:
        templates = list(template_dir.glob("*.template"))
        if templates:
            print("Available templates:")
            for template in templates:
                print(f"  - {template.stem}")
        else:
            print("No templates found.")
    
    elif show:
        template_path = template_dir / f"{show}.template"
        if template_path.exists():
            print(template_path.read_text())
        else:
            print(f"Template '{show}' not found.")
    
    elif create:
        # TODO: Implement template creation wizard
        print(f"Template creation not yet implemented.")
    
    else:
        click.echo("Specify --list, --show, or --create")