"""
Template engine for ghops export functionality.

Provides Jinja2-based templating for flexible export formats.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_template_dir() -> Path:
    """Get the directory where templates are stored."""
    template_dir = Path.home() / ".ghops" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    return template_dir


def get_builtin_templates() -> Dict[str, str]:
    """Get built-in template content."""
    return {
        "markdown": '''# {{ title | default("Repository Report") }}
{% if subtitle %}
{{ subtitle }}
{% endif %}

Generated on {{ generated_date }}

{% for group_name, repos in groups.items() %}
## {{ group_name }}

{% for repo in repos %}
### {{ repo.name }}
{% if repo.description %}
{{ repo.description }}
{% endif %}

- **Language**: {{ repo.language | default("Unknown") }}
- **Stars**: {{ repo.stars | default(0) }}
- **Owner**: {{ repo.owner | default("Unknown") }}
{% if repo.topics %}
- **Topics**: {{ repo.topics | join(", ") }}
{% endif %}
{% if repo.license %}
- **License**: {{ repo.license.name | default(repo.license.key) }}
{% endif %}

{% if repo.url %}
[View on GitHub]({{ repo.url }})
{% endif %}

---

{% endfor %}
{% endfor %}
''',
        
        "html": '''<!DOCTYPE html>
<html>
<head>
    <title>{{ title | default("Repository Report") }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .repo-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .repo-name { font-size: 1.2em; font-weight: bold; }
        .metadata { color: #666; }
        .group-header { color: #333; border-bottom: 2px solid #333; padding-bottom: 5px; }
    </style>
</head>
<body>
    <h1>{{ title | default("Repository Report") }}</h1>
    {% if subtitle %}
    <p>{{ subtitle }}</p>
    {% endif %}
    <p><em>Generated on {{ generated_date }}</em></p>
    
    {% for group_name, repos in groups.items() %}
    <h2 class="group-header">{{ group_name }}</h2>
    
    {% for repo in repos %}
    <div class="repo-card">
        <div class="repo-name">{{ repo.name }}</div>
        {% if repo.description %}
        <p>{{ repo.description }}</p>
        {% endif %}
        
        <div class="metadata">
            <p><strong>Language:</strong> {{ repo.language | default("Unknown") }}</p>
            <p><strong>Stars:</strong> {{ repo.stars | default(0) }}</p>
            <p><strong>Owner:</strong> {{ repo.owner | default("Unknown") }}</p>
            {% if repo.topics %}
            <p><strong>Topics:</strong> {{ repo.topics | join(", ") }}</p>
            {% endif %}
            {% if repo.license %}
            <p><strong>License:</strong> {{ repo.license.name | default(repo.license.key) }}</p>
            {% endif %}
        </div>
        
        {% if repo.url %}
        <p><a href="{{ repo.url }}">View on GitHub</a></p>
        {% endif %}
    </div>
    {% endfor %}
    {% endfor %}
</body>
</html>
''',
        
        "latex": r'''\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{hyperref}
\usepackage{enumitem}

\title{ {{ title | default("Repository Report") | replace("_", "\\_") }} }
{% if subtitle %}
\author{ {{ subtitle | replace("_", "\\_") }} }
{% endif %}
\date{ {{ generated_date }} }

\begin{document}
\maketitle

{% for group_name, repos in groups.items() %}
\section{ {{ group_name | replace("_", "\\_") }} }

{% for repo in repos %}
\subsection{ {{ repo.name | replace("_", "\\_") }} }

{% if repo.description %}
{{ repo.description | replace("_", "\\_") }}
{% endif %}

\begin{description}[leftmargin=!,labelwidth=\widthof{\bfseries Language}]
\item[Language] {{ repo.language | default("Unknown") | replace("_", "\\_") }}
\item[Stars] {{ repo.stars | default(0) }}
\item[Owner] {{ repo.owner | default("Unknown") | replace("_", "\\_") }}
{% if repo.topics %}
\item[Topics] {{ repo.topics | join(", ") | replace("_", "\\_") }}
{% endif %}
{% if repo.license %}
\item[License] {{ repo.license.name | default(repo.license.key) | replace("_", "\\_") }}
{% endif %}
\end{description}

{% if repo.url %}
\url{ {{ repo.url }} }
{% endif %}

{% endfor %}
{% endfor %}

\end{document}
''',
        
        "csv": '''name,language,stars,owner,license,topics,url
{% for group_name, repos in groups.items() %}{% for repo in repos %}{{ repo.name }},{{ repo.language | default("") }},{{ repo.stars | default(0) }},{{ repo.owner | default("") }},{{ repo.license.key | default("") if repo.license else "" }},"{{ repo.topics | join(";") if repo.topics else "" }}",{{ repo.url | default("") }}
{% endfor %}{% endfor %}''',
        
        "json": '''{{ groups | tojson(indent=2) }}''',
        
        # Hugo-specific templates
        "hugo_index": '''---
title: "Repository Catalog"
description: "Overview of all repositories"
date: {{ generated_date }}
draft: false
menu:
  main:
    name: "Repositories"
    weight: 10
---

# Repository Catalog

This catalog contains **{{ total_repos }}** repositories organized into **{{ group_count }}** categories.

## Categories

{% for group_name, repos in groups.items() %}
### [{{ group_name }}]({{group_name | lower | replace(' ', '-')}}/)

{{ repos | length }} repositories

{% for repo in repos[:3] %}
- **{{ repo.name }}**: {{ repo.description | default("No description") | truncate(60) }}
{% endfor %}
{% if repos | length > 3 %}
- *...and {{ repos | length - 3 }} more*
{% endif %}

{% endfor %}

---

*Last updated: {{ generated_date }}*
''',
        
        "hugo_group": '''---
title: "{{ group_name }}"
description: "{{ repos | length }} repositories in {{ group_name }}"
date: {{ generated_date }}
draft: false
weight: {{ weight | default(50) }}
---

# {{ group_name }}

This category contains {{ repos | length }} repositories.

## Repositories

{% for repo in repos %}
### [{{ repo.name }}]({{ repo.name | lower | replace(' ', '-') }}/)

{% if repo.description %}
{{ repo.description }}
{% endif %}

- **Language**: {{ repo.language | default("Unknown") }}
- **Stars**: {{ repo.stars | default(0) }}
{% if repo.topics %}
- **Topics**: {{ repo.topics | join(", ") }}
{% endif %}

---
{% endfor %}
''',
        
        "hugo_repo": '''---
title: "{{ repo.name }}"
description: "{{ repo.description | default('') }}"
date: {{ generated_date }}
draft: false
tags:
{% for tag in repo.tags | default([]) %}
  - "{{ tag }}"
{% endfor %}
categories:
  - "{{ group_name }}"
languages:
{% if repo.languages %}
{% for lang in repo.languages.keys() %}
  - "{{ lang }}"
{% endfor %}
{% else %}
  - "{{ repo.language | default('Unknown') }}"
{% endif %}
params:
  stars: {{ repo.stars | default(0) }}
  owner: "{{ repo.owner | default('') }}"
  license: "{{ repo.license.key if repo.license else 'none' }}"
  private: {{ repo.private | default(false) | lower }}
  archived: {{ repo.archived | default(false) | lower }}
{% if repo.url %}
  github_url: "{{ repo.url }}"
{% endif %}
---

# {{ repo.name }}

{% if repo.description %}
{{ repo.description }}
{% endif %}

## Overview

<table>
<tr>
  <td><strong>Primary Language</strong></td>
  <td>{{ repo.language | default("Unknown") }}</td>
</tr>
<tr>
  <td><strong>Stars</strong></td>
  <td>{{ repo.stars | default(0) }}</td>
</tr>
<tr>
  <td><strong>Owner</strong></td>
  <td>{{ repo.owner | default("Unknown") }}</td>
</tr>
<tr>
  <td><strong>License</strong></td>
  <td>{{ repo.license.name | default("No license") if repo.license else "No license" }}</td>
</tr>
{% if repo.created_at %}
<tr>
  <td><strong>Created</strong></td>
  <td>{{ repo.created_at }}</td>
</tr>
{% endif %}
{% if repo.updated_at %}
<tr>
  <td><strong>Last Updated</strong></td>
  <td>{{ repo.updated_at }}</td>
</tr>
{% endif %}
</table>

{% if repo.topics %}
## Topics

{% for topic in repo.topics %}
- {{ topic }}
{% endfor %}
{% endif %}

{% if repo.languages %}
## Languages

<table>
<tr>
  <th>Language</th>
  <th>Files</th>
  <th>Size</th>
</tr>
{% for lang, stats in repo.languages.items() %}
<tr>
  <td>{{ lang }}</td>
  <td>{{ stats.files }}</td>
  <td>{{ (stats.bytes / 1024) | round(1) }} KB</td>
</tr>
{% endfor %}
</table>
{% endif %}

{% if repo.readme_content %}
## README

{{ repo.readme_content }}
{% endif %}

{% if repo.url %}
## Links

- [View on GitHub]({{ repo.url }})
{% if repo.homepage %}
- [Project Homepage]({{ repo.homepage }})
{% endif %}
{% if repo.documentation_url %}
- [Documentation]({{ repo.documentation_url }})
{% endif %}
{% endif %}

---

*Last updated: {{ generated_date }}*
'''
    }


def render_template(template_content: str, data: Dict[str, Any]) -> str:
    """Render a Jinja2 template with the given data.
    
    Args:
        template_content: The Jinja2 template string
        data: Dictionary of data to pass to the template
        
    Returns:
        Rendered template string
    """
    try:
        from jinja2 import Template, Environment, select_autoescape
        
        # Create Jinja2 environment with auto-escaping
        env = Environment(autoescape=select_autoescape(['html', 'xml']))
        
        # Add custom filters
        env.filters['tojson'] = lambda x, **kwargs: json.dumps(x, **kwargs)
        
        # Create and render template
        template = env.from_string(template_content)
        return template.render(**data)
        
    except ImportError:
        logger.warning("Jinja2 not installed. Falling back to basic templating.")
        # Basic fallback - just return the template as-is
        return template_content
    except Exception as e:
        logger.error(f"Template rendering error: {e}")
        raise ValueError(f"Failed to render template: {e}")


def load_template(template_name_or_path: str, format: str) -> Optional[str]:
    """Load a template by name or path.
    
    Args:
        template_name_or_path: Template name (for built-in or saved) or file path
        format: Export format (markdown, html, latex, etc.)
        
    Returns:
        Template content string or None if not found
    """
    # Check if it's a file path
    template_path = Path(template_name_or_path)
    if template_path.exists() and template_path.is_file():
        try:
            return template_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read template file {template_path}: {e}")
            return None
    
    # Check saved templates
    template_dir = get_template_dir()
    saved_template = template_dir / f"{template_name_or_path}.template"
    if saved_template.exists():
        try:
            return saved_template.read_text()
        except Exception as e:
            logger.error(f"Failed to read saved template {saved_template}: {e}")
            return None
    
    # Check built-in templates
    builtin = get_builtin_templates()
    if template_name_or_path in builtin:
        return builtin[template_name_or_path]
    
    # Try format-specific built-in
    if format in builtin:
        return builtin[format]
    
    return None


def save_template(name: str, content: str) -> Path:
    """Save a template to the templates directory.
    
    Args:
        name: Template name (without extension)
        content: Template content
        
    Returns:
        Path to saved template file
    """
    template_dir = get_template_dir()
    template_path = template_dir / f"{name}.template"
    
    try:
        template_path.write_text(content)
        return template_path
    except Exception as e:
        logger.error(f"Failed to save template {name}: {e}")
        raise ValueError(f"Failed to save template: {e}")


def list_templates() -> List[Dict[str, Any]]:
    """List all available templates.
    
    Returns:
        List of template info dictionaries
    """
    templates = []
    
    # Add built-in templates
    for name in get_builtin_templates():
        templates.append({
            "name": name,
            "type": "builtin",
            "description": f"Built-in {name} template"
        })
    
    # Add saved templates
    template_dir = get_template_dir()
    for template_file in template_dir.glob("*.template"):
        templates.append({
            "name": template_file.stem,
            "type": "saved",
            "path": str(template_file),
            "description": f"User template: {template_file.stem}"
        })
    
    return templates


# Import json for the tojson filter
import json