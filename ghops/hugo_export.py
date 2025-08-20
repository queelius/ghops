"""
Hugo export implementation using the component system.

Creates a Hugo static site structure with content files and data files.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Generator
from datetime import datetime

from .export_components import ExportContext, ExportFormat, ComponentRegistry, ExportComposer
from .export_components_impl import (
    HeaderComponent, SummaryStatisticsComponent, 
    TagCloudComponent, RepositoryCardsComponent
)


def create_hugo_front_matter(repo: Dict[str, Any], group_name: str = "") -> str:
    """
    Create Hugo front matter for a repository.
    
    Args:
        repo: Repository metadata
        group_name: Group name (e.g., language, category)
        
    Returns:
        YAML front matter string
    """
    # Build front matter data
    front_matter = {
        'title': repo.get('name', 'Unknown'),
        'date': datetime.now().isoformat(),
        'draft': False,
        'description': repo.get('description', ''),
    }
    
    # Add taxonomies
    if group_name:
        front_matter['categories'] = [group_name]
    
    # Extract tags
    tags = repo.get('tags', [])
    if tags:
        front_matter['tags'] = tags
    
    # Add topics as tags too
    topics = repo.get('topics', [])
    if topics:
        if 'tags' in front_matter:
            front_matter['tags'].extend(topics)
        else:
            front_matter['tags'] = topics
    
    # Add custom params for Hugo templates
    front_matter['params'] = {
        'repository_url': repo.get('remote_url', ''),
        'stars': repo.get('stargazers_count', 0),
        'forks': repo.get('forks_count', 0),
        'language': repo.get('language', 'Unknown'),
        'license': repo.get('license', {}).get('key', 'none') if repo.get('license') else 'none',
        'owner': repo.get('owner', ''),
        'has_readme': repo.get('has_readme', False),
        'has_docs': repo.get('has_docs', False),
        'last_updated': repo.get('updated_at', ''),
    }
    
    # Convert to YAML with --- delimiters
    yaml_content = yaml.dump(front_matter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_content}---\n\n"


def create_hugo_content(repo: Dict[str, Any], include_readme: bool = False) -> str:
    """
    Create Hugo markdown content for a repository.
    
    Args:
        repo: Repository metadata
        include_readme: Whether to include README content
        
    Returns:
        Markdown content string
    """
    lines = []
    
    # Repository description
    if repo.get('description'):
        lines.append(f"> {repo['description']}\n")
    
    # Quick stats section
    lines.append("## Quick Stats\n")
    stats = []
    
    if repo.get('language'):
        stats.append(f"**Language:** {repo['language']}")
    
    if repo.get('stargazers_count', 0) > 0:
        stats.append(f"**Stars:** ⭐ {repo['stargazers_count']}")
    
    if repo.get('forks_count', 0) > 0:
        stats.append(f"**Forks:** 🔀 {repo['forks_count']}")
    
    license_info = repo.get('license')
    if license_info:
        license_name = license_info.get('name', license_info.get('key', 'Unknown'))
        stats.append(f"**License:** {license_name}")
    
    if repo.get('topics'):
        topics_str = ', '.join(f"`{t}`" for t in repo['topics'])
        stats.append(f"**Topics:** {topics_str}")
    
    for stat in stats:
        lines.append(f"- {stat}")
    
    lines.append("")
    
    # Repository link
    if repo.get('remote_url'):
        lines.append(f"## Repository\n")
        lines.append(f"[View on GitHub]({repo['remote_url']})\n")
    
    # Languages breakdown if available
    if repo.get('languages'):
        lines.append("## Languages\n")
        for lang, info in repo['languages'].items():
            if isinstance(info, dict):
                file_count = info.get('files', 0)
                lines.append(f"- **{lang}:** {file_count} files")
            else:
                lines.append(f"- {lang}")
        lines.append("")
    
    # README content if requested
    if include_readme and repo.get('readme_content'):
        lines.append("## README\n")
        lines.append(repo['readme_content'])
        lines.append("")
    elif include_readme and repo.get('readme_preview'):
        lines.append("## README Preview\n")
        lines.append(repo['readme_preview'])
        lines.append("\n*[Full README available in repository]*\n")
    
    return '\n'.join(lines)


def export_hugo(grouped: Dict[str, List[Dict]], output_dir: str, 
                single_file: bool = False, include_readme: bool = False,
                progress_callback=None) -> Generator[Dict[str, Any], None, None]:
    """
    Export repositories as Hugo static site.
    
    Args:
        grouped: Dictionary of grouped repositories
        output_dir: Output directory for Hugo content
        single_file: If True, create single index file (ignored for Hugo)
        include_readme: Whether to include README content
        progress_callback: Progress reporting callback
        
    Yields:
        Status dictionaries for each file created
    """
    output_path = Path(output_dir) if output_dir else Path(".")
    
    # Create Hugo directory structure
    content_dir = output_path / "content" / "repositories"
    data_dir = output_path / "data"
    
    content_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    if progress_callback:
        progress_callback("Creating Hugo site structure...")
    
    # Create main _index.md for repositories section
    index_content = """---
title: "Repositories"
date: {}
menu: "main"
weight: 10
---

# Repository Portfolio

This section contains all repositories organized by category.

""".format(datetime.now().isoformat())
    
    # Add summary statistics using components
    all_repos = []
    for repos in grouped.values():
        all_repos.extend(repos)
    
    # Use component system for summary
    context = ExportContext(
        format=ExportFormat.MARKDOWN,
        repositories=all_repos,
        config={}
    )
    
    stats_component = SummaryStatisticsComponent()
    if stats_component.should_render(context):
        index_content += stats_component.render(context)
        index_content += "\n\n"
    
    # Write main index
    index_file = content_dir / "_index.md"
    index_file.write_text(index_content)
    
    yield {
        'status': 'success',
        'action': 'created',
        'file': str(index_file),
        'type': 'index'
    }
    
    # Process each group
    total_repos = sum(len(repos) for repos in grouped.values())
    repo_count = 0
    
    for group_name, repos in grouped.items():
        # Clean group name for directory
        safe_group_name = group_name.lower().replace(' ', '-').replace('/', '-')
        group_dir = content_dir / safe_group_name
        group_dir.mkdir(parents=True, exist_ok=True)
        
        # Create group index
        group_index_content = f"""---
title: "{group_name}"
date: {datetime.now().isoformat()}
---

# {group_name}

Repositories in this category: {len(repos)}

"""
        
        # Add tag cloud for this group using component
        group_context = ExportContext(
            format=ExportFormat.MARKDOWN,
            repositories=repos,
            config={}
        )
        
        tag_cloud = TagCloudComponent()
        if tag_cloud.should_render(group_context):
            group_index_content += "## Topics\n\n"
            group_index_content += tag_cloud.render(group_context)
            group_index_content += "\n\n"
        
        group_index_file = group_dir / "_index.md"
        group_index_file.write_text(group_index_content)
        
        yield {
            'status': 'success',
            'action': 'created',
            'file': str(group_index_file),
            'type': 'group_index',
            'group': group_name
        }
        
        # Create individual repository pages
        for repo in repos:
            repo_count += 1
            
            if progress_callback:
                progress_callback(f"Processing {repo_count}/{total_repos}: {repo.get('name', 'Unknown')}")
            
            # Create safe filename
            repo_name = repo.get('name', 'unknown')
            safe_filename = repo_name.lower().replace(' ', '-').replace('/', '-') + '.md'
            
            # Generate content
            content = create_hugo_front_matter(repo, group_name)
            content += create_hugo_content(repo, include_readme)
            
            # Write file
            repo_file = group_dir / safe_filename
            repo_file.write_text(content)
            
            yield {
                'status': 'success',
                'action': 'created',
                'file': str(repo_file),
                'type': 'repository',
                'name': repo_name,
                'group': group_name
            }
    
    # Create data files for use in Hugo templates
    if progress_callback:
        progress_callback("Creating data files...")
    
    # All repositories data
    repos_data_file = data_dir / "repositories.json"
    repos_data_file.write_text(json.dumps(all_repos, indent=2, default=str))
    
    yield {
        'status': 'success',
        'action': 'created',
        'file': str(repos_data_file),
        'type': 'data',
        'description': 'All repositories data'
    }
    
    # Group summaries
    group_summaries = {}
    for group_name, repos in grouped.items():
        group_summaries[group_name] = {
            'count': len(repos),
            'total_stars': sum(r.get('stargazers_count', 0) for r in repos),
            'total_forks': sum(r.get('forks_count', 0) for r in repos),
            'languages': list(set(r.get('language', 'Unknown') for r in repos if r.get('language'))),
            'topics': list(set(topic for r in repos for topic in r.get('topics', [])))
        }
    
    groups_data_file = data_dir / "repository_groups.json"
    groups_data_file.write_text(json.dumps(group_summaries, indent=2))
    
    yield {
        'status': 'success',
        'action': 'created',
        'file': str(groups_data_file),
        'type': 'data',
        'description': 'Group summaries'
    }
    
    if progress_callback:
        progress_callback(f"Hugo export complete: {repo_count} repositories exported")