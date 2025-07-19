# ghops docs Command

The `ghops docs` command provides comprehensive documentation management for your repositories, including detection, building, serving, and deployment to GitHub Pages.

## Overview

The docs command can:
- Detect documentation tools (MkDocs, Sphinx, Jekyll, Hugo, etc.)
- Build documentation locally
- Serve documentation for preview
- Deploy to GitHub Pages
- Track documentation status across all repositories

## Commands

### docs status

Show documentation status for repositories:

```bash
# Show docs status for all repositories (JSONL output)
ghops docs status

# Pretty table format
ghops docs status --pretty

# Specific directory
ghops docs status --dir /path/to/repos --recursive
```

Output includes:
- Documentation tool detected
- Configuration files found
- GitHub Pages status
- Build/serve commands available

### docs detect

Detect which documentation tool a repository uses:

```bash
# Detect docs tool for current directory
ghops docs detect .

# Output (JSONL)
{
  "tool": "mkdocs",
  "config": "mkdocs.yml",
  "build_cmd": "mkdocs build",
  "serve_cmd": "mkdocs serve",
  "output_dir": "site",
  "detected_files": ["mkdocs.yml"]
}
```

### docs build

Build documentation for one or more repositories:

```bash
# Build docs for current repository
ghops docs build .

# Build all repositories with docs (using tag filter)
ghops docs build -t "repo:*"

# Build only MkDocs projects
ghops docs build -t "tool:mkdocs"

# Build Python projects with docs
ghops docs build -t "lang:python" -t "has:docs" --all-tags

# Dry run to see what would be built
ghops docs build -t "has:docs" --dry-run
```

### docs serve

Serve documentation locally for preview:

```bash
# Serve current repository docs
ghops docs serve .

# Custom port
ghops docs serve . --port 8080

# Open browser automatically
ghops docs serve . --open
```

### docs deploy

Deploy documentation to GitHub Pages:

```bash
# Deploy current repository
ghops docs deploy .

# Custom branch (default: gh-pages)
ghops docs deploy . --branch docs

# Custom commit message
ghops docs deploy . --message "Update API docs"

# Dry run
ghops docs deploy . --dry-run
```

## Supported Documentation Tools

The docs command automatically detects:

1. **MkDocs** - `mkdocs.yml` or `mkdocs.yaml`
2. **Sphinx** - `docs/conf.py` or `doc/conf.py`
3. **Jekyll** - `_config.yml`, `_posts`, `_layouts`
4. **Docusaurus** - `docusaurus.config.js`
5. **VuePress** - `.vuepress/config.js`
6. **Hugo** - `config.toml/yaml/json` with `content/` or `themes/`
7. **Generic Markdown** - Any `docs/` directory with `.md` files

## Examples

### Find all repos with documentation

```bash
# List repos with docs
ghops docs status | jq 'select(.has_docs == true)'

# Count by documentation tool
ghops docs status | jq -s 'group_by(.docs_tool) | map({tool: .[0].docs_tool, count: length})'

# Find repos without GitHub Pages
ghops docs status | jq 'select(.has_docs == true and .pages_url == null)'
```

### Batch operations

```bash
# Build all MkDocs projects
ghops docs status | \
  jq -r 'select(.docs_tool == "mkdocs") | .path' | \
  xargs -I {} ghops docs build {}

# Deploy all repos with built docs
ghops docs build --all --tool mkdocs
ghops docs status | \
  jq -r 'select(.docs_tool == "mkdocs") | .path' | \
  xargs -I {} ghops docs deploy {}
```

### Integration with other commands

```bash
# Find Python projects with docs
ghops query "lang:python" | \
  jq -r '.path' | \
  xargs -I {} ghops docs detect {} | \
  jq 'select(.tool != null)'

# Export repos with docs to Hugo
ghops docs status | \
  jq 'select(.has_docs == true)' | \
  ghops export --format hugo --stdin
```

## JSONL Output Schema

```json
{
  "path": "/absolute/path/to/repo",
  "name": "repo-name",
  "has_docs": true,
  "docs_tool": "mkdocs",
  "docs_config": "mkdocs.yml",
  "detected_files": ["mkdocs.yml"],
  "pages_url": "https://user.github.io/repo"
}
```

## Notes

- The deploy command requires either `ghp-import` or git to be installed
- Some documentation tools may require specific dependencies to be installed
- GitHub Pages detection works both locally and via API
- All commands output JSONL by default for pipeline composition