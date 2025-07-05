# ghops Ecosystem Architecture Vision

## Core Philosophy
- **Unix Philosophy**: Each tool does one thing well
- **Composable**: Tools work together via streaming JSONL
- **Extensible**: Plugin architecture for custom operations

## Tool Separation

### `ghops` - Repository Operations
**Focus**: Direct operations on git repositories
```bash
ghops status     # Repository health and metadata
ghops sync       # Sync with remotes
ghops clean      # Cleanup operations
ghops backup     # Archive repositories
ghops migrate    # Move between services (GitHub -> GitLab)
ghops health     # Check repository integrity
```

### `ghj` - GitHub Metadata & Search
**Focus**: GitHub API data mining and analysis
```bash
ghj search --query "language:python stars:>100"
ghj analyze --user username
ghj export --format csv
```

### `repodocs` - Documentation Generation
**Focus**: Transform repositories into documentation sites
```bash
repodocs generate --input repos.jsonl --output-dir ./site
repodocs hugo --theme academic
repodocs search-index --engine lunr
```

## Data Flow Architecture

```
┌─────────┐    JSONL    ┌──────────┐    JSONL    ┌──────────┐
│  ghops  │──────────→  │    jq    │──────────→  │ repodocs │
│ status  │             │ filter   │             │ generate │
└─────────┘             └──────────┘             └──────────┘
     │                       │                       │
     │                       ▼                       ▼
     │                  ┌──────────┐             ┌──────────┐
     │                  │   ghj    │             │   Hugo   │
     │                  │ enrich   │             │   Site   │
     │                  └──────────┘             └──────────┘
     │
     ▼ JSONL
┌──────────┐
│ Custom   │
│ Scripts  │
└──────────┘
```

## ghops Export Group Proposal

For the export functionality in `ghops`, focus on repository-level operations:

### Export Operations
```bash
# Repository migration
ghops export github-to-gitlab --repos repos.jsonl
ghops export backup --format tar.gz
ghops export clone-bundle --include-lfs

# Integration exports
ghops export dashboard --format json    # For external dashboards
ghops export metrics --format prometheus
ghops export inventory --format csv
```

### NOT in ghops export
- Documentation generation (belongs in `repodocs`)
- Markdown conversion (belongs in `repodocs`) 
- Static site generation (belongs in `repodocs`)

## Example Workflow

```bash
# 1. Discover and analyze repositories
ghops status --recursive > repos.jsonl

# 2. Filter for specific criteria
cat repos.jsonl | jq 'select(.github.on_github and .license.name)' > public-repos.jsonl

# 3. Migrate to GitLab
ghops export github-to-gitlab --input public-repos.jsonl

# 4. Generate documentation site
repodocs generate --input public-repos.jsonl --template hugo-academic

# 5. Enrich with GitHub API data
ghj enrich --input public-repos.jsonl > enriched-repos.jsonl
```

## Plugin Architecture for ghops

```python
# ghops/plugins/export/gitlab.py
@click.command("gitlab")
@click.option("--input", type=click.File('r'))
def export_to_gitlab(input):
    """Export repositories to GitLab."""
    for line in input:
        repo = json.loads(line)
        # Migration logic here
        yield {"repo": repo["name"], "status": "migrated", "url": new_url}
```

## Benefits of This Architecture

1. **Focused Tools**: Each tool has a clear, single responsibility
2. **Composability**: JSONL streaming enables powerful combinations
3. **Extensibility**: Plugin architecture for custom operations
4. **Reusability**: Components can be mixed and matched
5. **Maintenance**: Easier to maintain smaller, focused codebases

## Recommendation

Keep `ghops` focused on repository operations. Add export functionality for:
- Repository migration between services
- Backup and archival operations
- Integration with external tools (dashboards, monitoring)

Create separate tools for documentation generation and GitHub API analysis.
