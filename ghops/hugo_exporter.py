"""
Hugo-specific export functionality using the template engine.

This module provides a clean implementation of Hugo export
that properly leverages the Jinja2 template system.
"""

from pathlib import Path
from typing import Dict, List, Any, Generator
from datetime import datetime
import yaml
import logging

from .templates import load_template, render_template, save_template

logger = logging.getLogger(__name__)


def create_hugo_site_structure(base_path: Path) -> None:
    """Create the basic Hugo site structure if it doesn't exist."""
    directories = [
        base_path / "content" / "repositories",
        base_path / "data",
        base_path / "layouts" / "repositories",
        base_path / "static" / "images",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def export_hugo_with_templates(
    grouped: Dict[str, List[Dict]], 
    output_dir: str, 
    template_name: str = None,
    include_readme: bool = False,
    create_data_files: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """Export repositories as a Hugo static site using templates.
    
    Args:
        grouped: Dictionary of grouped repositories
        output_dir: Output directory for Hugo content
        template_name: Custom template name or path (optional)
        include_readme: Whether to include README content in repo pages
        create_data_files: Whether to create JSON data files for Hugo
        
    Yields:
        Status dictionaries for each file created
    """
    base_path = Path(output_dir) if output_dir else Path(".")
    content_path = base_path / "content" / "repositories"
    data_path = base_path / "data"
    
    # Create directory structure
    create_hugo_site_structure(base_path)
    
    # Common template data
    base_data = {
        "generated_date": datetime.now().isoformat(),
        "total_repos": sum(len(repos) for repos in grouped.values()),
        "group_count": len(grouped),
        "groups": grouped
    }
    
    # 1. Create main repositories index
    index_template = load_template(template_name or "hugo_index", "hugo")
    if index_template:
        try:
            index_content = render_template(index_template, base_data)
            index_file = content_path / "_index.md"
            index_file.write_text(index_content)
            
            yield {
                "status": "success",
                "format": "hugo",
                "file": str(index_file),
                "type": "index",
                "repositories": base_data["total_repos"]
            }
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            yield {
                "status": "error",
                "format": "hugo",
                "error": str(e),
                "type": "index"
            }
    
    # 2. Create group pages and individual repo pages
    group_template = load_template(template_name or "hugo_group", "hugo")
    repo_template = load_template(template_name or "hugo_repo", "hugo")
    
    weight = 10
    for group_name, repos in grouped.items():
        group_slug = slugify(group_name)
        group_path = content_path / group_slug
        group_path.mkdir(exist_ok=True)
        
        # Create group index
        if group_template:
            try:
                group_data = {
                    **base_data,
                    "group_name": group_name,
                    "repos": repos,
                    "weight": weight
                }
                group_content = render_template(group_template, group_data)
                group_file = group_path / "_index.md"
                group_file.write_text(group_content)
                
                yield {
                    "status": "success",
                    "format": "hugo",
                    "file": str(group_file),
                    "type": "group",
                    "group": group_name,
                    "repositories": len(repos)
                }
            except Exception as e:
                logger.error(f"Failed to create group {group_name}: {e}")
                yield {
                    "status": "error",
                    "format": "hugo",
                    "error": str(e),
                    "type": "group",
                    "group": group_name
                }
        
        weight += 10
        
        # Create individual repository pages
        if repo_template:
            for repo in repos:
                try:
                    repo_slug = slugify(repo.get('name', 'unknown'))
                    
                    # Optionally fetch README content
                    if include_readme and not repo.get('readme_content'):
                        repo['readme_content'] = fetch_readme_content(repo)
                    
                    repo_data = {
                        **base_data,
                        "repo": repo,
                        "group_name": group_name
                    }
                    
                    repo_content = render_template(repo_template, repo_data)
                    repo_file = group_path / f"{repo_slug}.md"
                    repo_file.write_text(repo_content)
                    
                    yield {
                        "status": "success",
                        "format": "hugo",
                        "file": str(repo_file),
                        "type": "repository",
                        "group": group_name,
                        "repository": repo.get('name')
                    }
                except Exception as e:
                    logger.error(f"Failed to create repo {repo.get('name')}: {e}")
                    yield {
                        "status": "error",
                        "format": "hugo",
                        "error": str(e),
                        "type": "repository",
                        "repository": repo.get('name')
                    }
    
    # 3. Create data files for Hugo templates
    if create_data_files:
        try:
            # All repositories data
            all_repos_file = data_path / "repositories.json"
            all_repos_data = []
            for group_name, repos in grouped.items():
                for repo in repos:
                    repo_data = repo.copy()
                    repo_data['group'] = group_name
                    all_repos_data.append(repo_data)
            
            import json
            all_repos_file.write_text(json.dumps(all_repos_data, indent=2))
            
            yield {
                "status": "success",
                "format": "hugo",
                "file": str(all_repos_file),
                "type": "data",
                "data": "repositories"
            }
            
            # Group summary data
            groups_file = data_path / "repository_groups.json"
            groups_data = {
                group_name: {
                    "count": len(repos),
                    "languages": list(set(r.get('language', 'Unknown') for r in repos)),
                    "total_stars": sum(r.get('stars', 0) for r in repos)
                }
                for group_name, repos in grouped.items()
            }
            
            groups_file.write_text(json.dumps(groups_data, indent=2))
            
            yield {
                "status": "success",
                "format": "hugo",
                "file": str(groups_file),
                "type": "data",
                "data": "repository_groups"
            }
            
        except Exception as e:
            logger.error(f"Failed to create data files: {e}")
            yield {
                "status": "error",
                "format": "hugo",
                "error": str(e),
                "type": "data"
            }
    
    # 4. Create example layouts if requested
    if template_name == "hugo_create_layouts":
        yield from create_hugo_layouts(base_path)


def create_hugo_layouts(base_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Create example Hugo layouts for the repository content type."""
    layouts_path = base_path / "layouts" / "repositories"
    
    layouts = {
        "single.html": '''{{ define "main" }}
<article class="repository">
  <header>
    <h1>{{ .Title }}</h1>
    {{ with .Params.description }}
    <p class="description">{{ . }}</p>
    {{ end }}
  </header>
  
  <div class="metadata">
    <dl>
      {{ with .Params.owner }}<dt>Owner</dt><dd>{{ . }}</dd>{{ end }}
      {{ with .Params.stars }}<dt>Stars</dt><dd>{{ . }}</dd>{{ end }}
      {{ with .Params.license }}<dt>License</dt><dd>{{ . }}</dd>{{ end }}
      {{ range .Params.languages }}<dt>Language</dt><dd>{{ . }}</dd>{{ end }}
    </dl>
  </div>
  
  <div class="content">
    {{ .Content }}
  </div>
  
  {{ with .Params.github_url }}
  <footer>
    <a href="{{ . }}" class="github-link">View on GitHub</a>
  </footer>
  {{ end }}
</article>
{{ end }}''',
        
        "list.html": '''{{ define "main" }}
<section class="repository-list">
  <header>
    <h1>{{ .Title }}</h1>
    {{ with .Params.summary }}
    <p>{{ . }}</p>
    {{ end }}
  </header>
  
  {{ .Content }}
  
  <div class="repositories">
    {{ range .Pages }}
    <article class="repository-card">
      <h2><a href="{{ .RelPermalink }}">{{ .Title }}</a></h2>
      {{ with .Params.description }}
      <p>{{ . }}</p>
      {{ end }}
      <div class="meta">
        {{ with .Params.stars }}<span class="stars">⭐ {{ . }}</span>{{ end }}
        {{ with .Params.owner }}<span class="owner">👤 {{ . }}</span>{{ end }}
      </div>
    </article>
    {{ end }}
  </div>
</section>
{{ end }}'''
    }
    
    for filename, content in layouts.items():
        try:
            layout_file = layouts_path / filename
            layout_file.write_text(content)
            
            yield {
                "status": "success",
                "format": "hugo",
                "file": str(layout_file),
                "type": "layout",
                "layout": filename
            }
        except Exception as e:
            logger.error(f"Failed to create layout {filename}: {e}")
            yield {
                "status": "error",
                "format": "hugo",
                "error": str(e),
                "type": "layout",
                "layout": filename
            }


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    return text.lower().replace(' ', '-').replace('/', '-')


def fetch_readme_content(repo: Dict[str, Any]) -> str:
    """Fetch README content for a repository (placeholder)."""
    # This would integrate with the GitHub API to fetch README
    # For now, return empty string
    return ""


def create_hugo_config_template():
    """Create a template for Hugo site configuration."""
    config_template = '''baseURL = "{{ base_url | default('https://example.com/') }}"
languageCode = "{{ language_code | default('en-us') }}"
title = "{{ site_title | default('Repository Portfolio') }}"
theme = "{{ theme | default('ananke') }}"

[params]
  description = "{{ site_description | default('A portfolio of my open source projects') }}"
  github = "{{ github_username | default('') }}"
  
[menu]
  [[menu.main]]
    name = "Repositories"
    url = "/repositories/"
    weight = 10
  
  [[menu.main]]
    name = "About"
    url = "/about/"
    weight = 20

[taxonomies]
  category = "categories"
  tag = "tags"
  language = "languages"

[outputs]
  home = ["HTML", "RSS", "JSON"]
  section = ["HTML", "RSS", "JSON"]
'''
    
    # Save as a template
    save_template("hugo_config", config_template)
    return config_template