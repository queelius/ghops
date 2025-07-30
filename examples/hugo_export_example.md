# Hugo Export Example

This example demonstrates how to export your repositories as a Hugo static site using ghops.

## Basic Hugo Export

Export all repositories to a Hugo site:

```bash
# Export to default location (content/repositories)
ghops export list --format hugo

# Export to specific directory
ghops export list --format hugo --output-dir my-hugo-site

# Export with grouping by language
ghops export list --format hugo --group-by language --output-dir my-hugo-site
```

## Using Custom Templates

You can customize the Hugo output using templates:

```bash
# List available templates
ghops export templates --list

# Show a built-in template
ghops export templates --show hugo_repo

# Create a custom template
ghops export templates --create my_hugo_template

# Use custom template
ghops export list --format hugo --template my_hugo_template
```

## Creating a Complete Hugo Site

Here's a complete workflow to create a Hugo site from your repositories:

```bash
# 1. Create a new Hugo site
hugo new site my-portfolio

# 2. Export repositories to the Hugo site
ghops export list --format hugo --output-dir my-portfolio --group-by language

# 3. The export creates:
#    - content/repositories/_index.md (main index)
#    - content/repositories/python/_index.md (language group)
#    - content/repositories/python/my-project.md (individual repos)
#    - data/repositories.json (all repo data)
#    - data/repository_groups.json (group summaries)

# 4. Add a theme (e.g., Ananke)
cd my-portfolio
git init
git submodule add https://github.com/theNewDynamic/gohugo-theme-ananke themes/ananke
echo "theme = 'ananke'" >> config.toml

# 5. Start the Hugo server
hugo server -D
```

## Custom Hugo Template Example

Create a custom template for a portfolio-style layout:

```jinja2
---
title: "{{ repo.name }}"
description: "{{ repo.description | default('') | truncate(160) }}"
date: {{ generated_date }}
draft: false
featured_image: "/images/projects/{{ repo.name | lower | replace(' ', '-') }}.png"
tags:
{% for tag in repo.tags | default([]) %}
  - "{{ tag }}"
{% endfor %}
categories:
  - "{{ group_name }}"
  - "Portfolio"
languages:
{% if repo.languages %}
{% for lang in repo.languages.keys() %}
  - "{{ lang }}"
{% endfor %}
{% endif %}
params:
  stars: {{ repo.stars | default(0) }}
  last_commit: "{{ repo.last_commit.timestamp | default('') }}"
  repo_size: {{ repo.total_size | default(0) }}
  primary_language: "{{ repo.language | default('Unknown') }}"
  license: "{{ repo.license.key if repo.license else 'none' }}"
---

{{< project-header >}}

## About This Project

{{ repo.description | default("This project doesn't have a description yet.") }}

### Quick Stats

- **Primary Language:** {{ repo.language | default("Unknown") }}
- **Total Size:** {{ (repo.total_size / 1024 / 1024) | round(2) }} MB
- **Last Updated:** {{ repo.last_commit.timestamp | default("Unknown") }}
- **License:** {{ repo.license.name if repo.license else "No license specified" }}

{% if repo.languages %}
### Language Breakdown

<div class="language-chart">
{% for lang, stats in repo.languages.items() %}
  <div class="language-bar" style="width: {{ (stats.bytes / repo.total_size * 100) | round(1) }}%">
    {{ lang }} ({{ (stats.bytes / 1024) | round(1) }} KB)
  </div>
{% endfor %}
</div>
{% endif %}

{% if repo.topics %}
### Topics

{{< tag-cloud >}}
{% for topic in repo.topics %}
{{< tag "{{ topic }}" >}}
{% endfor %}
{{< /tag-cloud >}}
{% endif %}

## Get Started

```bash
# Clone the repository
git clone {{ repo.url | default("#") }}

# Navigate to the project
cd {{ repo.name }}
```

{% if repo.has_docs %}
## Documentation

This project includes documentation. Build it with:

```bash
{{ repo.docs_tool }} build
```
{% endif %}

{{< project-footer >}}
```

## Hugo Front Matter Variables

The templates have access to all repository metadata:

- `repo.name` - Repository name
- `repo.description` - Description
- `repo.language` - Primary programming language
- `repo.languages` - All languages with file/byte counts
- `repo.stars` - Star count
- `repo.owner` - Repository owner
- `repo.topics` - GitHub topics
- `repo.tags` - ghops tags
- `repo.license` - License information
- `repo.url` - Repository URL
- `repo.created_at` - Creation date
- `repo.updated_at` - Last update date
- `repo.last_commit` - Last commit information
- `repo.has_docs` - Whether docs are present
- `repo.docs_tool` - Documentation tool used
- And many more...

## Data Files

The Hugo export also creates JSON data files that can be used in your Hugo templates:

### Using Repository Data in Hugo Templates

```go-html-template
<!-- List all repositories -->
{{ range .Site.Data.repositories }}
<article class="repo-card">
  <h3>{{ .name }}</h3>
  <p>{{ .description }}</p>
  <span class="stars">⭐ {{ .stars }}</span>
</article>
{{ end }}

<!-- Group statistics -->
{{ range $group, $stats := .Site.Data.repository_groups }}
<div class="group-stats">
  <h4>{{ $group }}</h4>
  <p>{{ $stats.count }} repositories</p>
  <p>{{ $stats.total_stars }} total stars</p>
</div>
{{ end }}
```

## Advanced Features

### Include README Content

```bash
# Export with README content included
ghops export list --format hugo --output-dir my-site --include-metadata
```

### Create Hugo Layouts

The exporter can create example Hugo layouts:

```bash
# This creates layouts/repositories/single.html and list.html
ghops export list --format hugo --template hugo_create_layouts
```

### Filter Repositories

```bash
# Export only Python projects with 10+ stars
ghops export list --query "language == 'Python' and stars >= 10" --format hugo

# Export only public, non-archived repos
ghops export list --query "not private and not archived" --format hugo
```