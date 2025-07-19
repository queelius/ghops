# Repository Organization with Catalog and Query

ghops provides powerful tools for organizing and finding repositories through its tagging system and query language.

## Catalog System

The catalog system allows you to organize repositories with tags, both explicit (user-defined) and implicit (auto-generated).

### Adding Tags

```bash
# Tag a single repository
ghops catalog add myproject python ml research

# Tag multiple repos
ghops catalog add project1 client-work urgent
ghops catalog add project2 client-work completed
```

### Viewing Tagged Repositories

```bash
# Show all tagged repos
ghops catalog show --pretty

# Filter by specific tags
ghops catalog show -t python --pretty

# Require multiple tags (AND operation)
ghops catalog show -t python -t ml --all-tags --pretty

# JSONL output for processing
ghops catalog show -t client-work | jq -r '.name'
```

### Removing Tags

```bash
# Remove specific tags
ghops catalog remove myproject urgent

# Remove all tags from a repo
ghops catalog clear myproject
```

### Implicit Tags

The system automatically generates implicit tags from repository metadata:

| Tag Pattern | Description | Example |
|-------------|-------------|---------|
| `repo:NAME` | Repository name | `repo:ghops` |
| `lang:LANGUAGE` | Primary language | `lang:python` |
| `dir:PARENT` | Parent directory | `dir:work` |
| `org:OWNER` | GitHub organization | `org:facebook` |
| `has:LICENSE` | Has license file | `has:license` |
| `has:README` | Has README file | `has:readme` |
| `has:DOCS` | Has documentation | `has:docs` |
| `tool:TOOL` | Documentation tool | `tool:mkdocs` |
| `license:TYPE` | License type | `license:mit` |
| `topic:TOPIC` | GitHub topics | `topic:machine-learning` |

## Query Language

The query command provides fuzzy matching and complex boolean expressions.

### Basic Syntax

```bash
# Simple equality
ghops query "language == 'Python'"

# Fuzzy matching with ~=
ghops query "language ~= 'pyton'"  # Matches Python

# Comparisons
ghops query "stars > 10"
ghops query "forks >= 5"
ghops query "created_at < '2023-01-01'"

# Contains operator
ghops query "'machine-learning' in topics"
ghops query "topics contains 'ml'"

# Not equal
ghops query "license.key != 'proprietary'"
```

### Complex Expressions

```bash
# AND operations
ghops query "stars > 10 and language == 'Python'"

# OR operations
ghops query "language == 'Python' or language == 'JavaScript'"

# Parentheses for grouping
ghops query "(stars > 5 or forks > 2) and language ~= 'python'"

# Nested field access
ghops query "license.name contains 'MIT'"
ghops query "remote.owner == 'myorg'"
```

### Fuzzy Matching

The `~=` operator uses fuzzy string matching:

```bash
# Typos are forgiven
ghops query "name ~= 'djago'"  # Matches django

# Partial matches
ghops query "description ~= 'web framework'"

# Case insensitive
ghops query "language ~= 'PYTHON'"
```

## Combining Catalog and Query

Use both systems together for powerful filtering:

```bash
# Tag-based pre-filtering with query refinement
ghops list -t "lang:python" | jq -r '.path' | \
  xargs -I {} ghops query "stars > 5" --path {}

# Find untagged repos
ghops query "true" | jq -r '.name' > all-repos.txt
ghops catalog show | jq -r '.name' > tagged-repos.txt
comm -23 <(sort all-repos.txt) <(sort tagged-repos.txt)
```

## Common Patterns

### Project Organization

```bash
# Tag by project status
ghops catalog add project1 active in-development
ghops catalog add project2 completed archived
ghops catalog add project3 active needs-review

# Find active projects needing review
ghops catalog show -t active -t needs-review --all-tags
```

### Client Work

```bash
# Tag by client
ghops catalog add webapp client:acme web
ghops catalog add api client:acme backend
ghops catalog add report client:bigco analysis

# All work for a client
ghops catalog show -t "client:acme"
```

### Technology Stacks

```bash
# Tag by stack
ghops catalog add frontend react typescript webpack
ghops catalog add backend python django postgresql
ghops catalog add mobile flutter dart

# Find all TypeScript projects
ghops catalog show -t typescript
# Or use implicit tags
ghops list -t "lang:typescript"
```

### Maintenance Status

```bash
# Tag by maintenance needs
ghops catalog add oldproject needs:update needs:tests
ghops catalog add newproject well-maintained has:ci

# Find projects needing attention
ghops catalog show -t "needs:update"
```

## Query Examples

### Finding Repositories

```bash
# Popular Python projects
ghops query "language == 'Python' and stars > 10"

# Recently updated
ghops query "updated_at > '2024-01-01'"

# Projects without licenses
ghops query "not has_license"

# Large projects
ghops query "file_count > 1000 or total_size > 10000000"

# ML projects
ghops query "'machine-learning' in topics or 'ml' in topics or name contains 'learn'"
```

### Complex Queries

```bash
# Active web projects
ghops query "(language == 'JavaScript' or language == 'TypeScript') and updated_at > '2023-06-01' and ('web' in topics or description contains 'web')"

# Python packages on PyPI
ghops query "language == 'Python' and has_package == true and package.registry == 'pypi'"

# Documentation sites
ghops query "has_docs == true and (has_pages == true or homepage contains 'github.io')"
```

## Integration with Other Commands

### Audit Filtered Repos

```bash
# Audit all client work
ghops audit all -t "client:*" --pretty

# Audit Python projects without docs
ghops audit docs -q "language == 'Python' and not has_docs"
```

### Export Filtered Repos

```bash
# Export active projects to Hugo
ghops export generate -t active -f hugo -o ./site/content/active

# Export popular repos to PDF
ghops export generate -q "stars > 5 or forks > 2" -f pdf
```

### Bulk Operations

```bash
# Update all work repos
ghops update -t "dir:work"

# Build docs for all documented Python projects
ghops docs build -q "language == 'Python' and has_docs == true"
```

## Best Practices

1. **Use Namespaces**: Prefix related tags (e.g., `client:*`, `project:*`, `status:*`)

2. **Combine Systems**: Use tags for stable categorization, queries for dynamic filtering

3. **Document Tags**: Keep a README of your tagging conventions

4. **Regular Cleanup**: Remove obsolete tags periodically
   ```bash
   ghops catalog show -t obsolete | jq -r '.name' | \
     xargs -I {} ghops catalog remove {} obsolete
   ```

5. **Export Tag Documentation**:
   ```bash
   # Generate tag documentation
   ghops catalog show | jq -r '.tags[]' | sort | uniq -c | \
     sort -rn > tag-usage.txt
   ```