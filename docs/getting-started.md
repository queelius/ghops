# Getting Started with ghops

Welcome to ghops! This guide will help you get up and running with the repository orchestration platform in just a few minutes.

## Prerequisites

- Python 3.8 or higher
- Git installed and configured
- Optional: GitHub personal access token for enhanced features

## Installation

### Install from PyPI (Recommended)

```bash
pip install ghops
```

### Install from Source

```bash
git clone https://github.com/queelius/ghops.git
cd ghops
pip install -e .
```

### Verify Installation

```bash
ghops --version
ghops --help
```

## Quick Setup

### 1. Generate Configuration

Create your initial configuration file with sensible defaults:

```bash
ghops config generate
```

This creates `~/.ghops/config.json` with example settings. The configuration includes:
- Repository directories to scan
- GitHub API settings
- Social media templates
- Export preferences

### 2. Configure Repository Directories

Edit `~/.ghops/config.json` to specify where your repositories are located:

```json
{
  "general": {
    "repository_directories": [
      "~/projects",
      "~/work",
      "~/github/**"
    ]
  }
}
```

The `**` pattern recursively searches subdirectories.

### 3. Set Up GitHub Token (Optional)

For enhanced GitHub features, add your personal access token:

```bash
export GHOPS_GITHUB_TOKEN="your-token-here"
```

Or add it to your configuration:

```json
{
  "github": {
    "token": "your-token-here"
  }
}
```

## Your First Commands

### List Your Repositories

```bash
# List all repositories (JSONL output)
ghops list

# Pretty-print as a table
ghops list --pretty

# Show only Python projects
ghops list --pretty | grep Python
```

### Check Repository Status

```bash
# Status of current directory
ghops status

# Status of all repositories
ghops status -r --pretty

# Find repos with uncommitted changes (using jq)
ghops status -r | jq 'select(.status.uncommitted_changes == true)'
```

### Organize with Tags

```bash
# Add tags to repositories
ghops catalog tag myproject "important" "python" "ml"

# Query by tags
ghops query "tag:important"

# List all tags
ghops catalog tags --pretty
```

### Analyze Repository Clusters

Clustering helps you organize and understand relationships between your repositories.

```bash
# Find similar repositories using K-means
ghops cluster analyze --algorithm kmeans --n-clusters 5 -r

# Use DBSCAN for density-based clustering
ghops cluster analyze --algorithm dbscan --eps 0.3 -r

# Pretty-print cluster analysis
ghops cluster analyze --pretty

# Find duplicate code across repositories
ghops cluster find-duplicates --min-similarity 0.7 -r --pretty

# Get consolidation suggestions for similar repos
ghops cluster suggest-consolidation --confidence 0.8 -r --pretty

# Export cluster results for visualization
ghops cluster export --format html --output clusters.html
```

**Understanding Clustering Algorithms:**

- **K-means**: Fast, works well when you know the number of clusters. Good for evenly distributed groups.
- **DBSCAN**: Finds clusters of arbitrary shapes, no need to specify cluster count. Good for finding outliers.
- **Hierarchical**: Creates a tree of clusters, great for understanding nested relationships.
- **Network**: Uses repository connections and dependencies for clustering.

### Run a Workflow

Workflows automate complex multi-step operations with conditional logic and parallel execution.

```bash
# Run example morning routine workflow
ghops workflow run examples/workflows/morning-routine.yaml

# Run release pipeline with variables
ghops workflow run examples/workflows/release-pipeline.yaml \
  --var version=1.2.0 \
  --var branch=main

# Dry run to preview without executing
ghops workflow run my-workflow.yaml --dry-run

# Validate workflow syntax
ghops workflow validate my-workflow.yaml
```

**Create Your First Workflow:**

```bash
cat > my-workflow.yaml << 'EOF'
name: Daily Repository Health Check
description: Check all repositories for issues and generate report

variables:
  notification_email: dev@example.com
  max_age_days: 30

tasks:
  - id: check_status
    type: ghops
    name: Check all repository statuses
    command: status
    args: ["--recursive", "--format", "json"]
    parse_output: true
    output_var: repo_statuses

  - id: find_stale
    type: ghops
    name: Find stale repositories
    command: query
    args:
      - "days_since_commit > ${max_age_days}"
    parse_output: true
    output_var: stale_repos
    depends_on: [check_status]

  - id: analyze_duplicates
    type: ghops
    name: Find duplicate code
    command: cluster find-duplicates
    args: ["--recursive", "--min-similarity", "0.8"]
    parse_output: true
    output_var: duplicates
    depends_on: [check_status]

  - id: generate_report
    type: python
    name: Generate health report
    code: |
      report = []
      report.append("# Repository Health Report")
      report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
      report.append("")

      if context.get('stale_repos'):
          report.append(f"## Stale Repositories ({len(context['stale_repos'])})")
          for repo in context['stale_repos']:
              report.append(f"- {repo['name']}: {repo['days_since_commit']} days old")
          report.append("")

      if context.get('duplicates'):
          report.append(f"## Duplicate Code Found ({len(context['duplicates'])})")
          for dup in context['duplicates']:
              report.append(f"- {dup['repo1']} ↔ {dup['repo2']}: {dup['similarity']:.0%} similar")
          report.append("")

      with open('health-report.md', 'w') as f:
          f.write('\n'.join(report))

      context['report_path'] = 'health-report.md'
    depends_on: [find_stale, analyze_duplicates]

  - id: send_notification
    type: shell
    name: Email the report
    command: |
      cat ${report_path} | mail -s "Daily Repository Report" ${notification_email}
    condition: stale_repos or duplicates
    ignore_errors: true
    depends_on: [generate_report]

on_failure: continue
timeout: 600
EOF

# Run your workflow
ghops workflow run my-workflow.yaml
```

**Workflow Features:**
- **Parallel Execution**: Independent tasks run concurrently
- **Conditional Steps**: Use `condition` to control execution
- **Variable Templating**: Access variables with `${var_name}`
- **Error Handling**: Configure retries and fallback actions
- **Output Capture**: Save step outputs to variables for later use

## Interactive Learning

### Jupyter Notebooks

Explore ghops features interactively with our tutorial notebooks:

```bash
# Clone the repository to access notebooks
git clone https://github.com/queelius/ghops.git
cd ghops/notebooks

# Start Jupyter
jupyter notebook

# Open notebooks in order:
# 1. 01_getting_started.ipynb
# 2. 02_clustering_analysis.ipynb
# 3. 03_workflow_orchestration.ipynb
# 4. 04_advanced_integrations.ipynb
# 5. 05_data_visualization.ipynb
```

## Common Workflows

### Morning Repository Review

```bash
# Update all repositories
ghops update -r

# Check status
ghops status -r --pretty

# Audit for issues
ghops audit -r --check license,readme,security
```

### Export Portfolio

```bash
# Export to Markdown
ghops export markdown --output portfolio.md

# Export to interactive HTML
ghops export html --output portfolio.html --group-by language

# Export for Hugo site
ghops export hugo --output-dir my-site/content
```

### Social Media Automation

```bash
# Sample repositories for promotion
ghops social sample --size 3

# Preview posts (dry run)
ghops social post --dry-run

# Post to configured platforms
ghops social post
```

## Environment Variables

ghops respects the following environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `GHOPS_CONFIG` | Path to config file | `~/.config/ghops/config.json` |
| `GHOPS_GITHUB_TOKEN` | GitHub API token | `ghp_xxxxxxxxxxxx` |
| `GHOPS_LOG_LEVEL` | Logging level | `DEBUG`, `INFO`, `WARNING` |
| `GHOPS_NO_COLOR` | Disable colored output | `1` or `true` |

## Command Output Formats

ghops follows Unix philosophy - all commands output JSONL by default:

```bash
# JSONL output (default) - great for piping
ghops list | jq '.name'

# Pretty table output - great for humans
ghops list --pretty

# Export specific format
ghops export json --output repos.json
ghops export csv --output repos.csv
```

## Next Steps

Now that you're up and running:

1. **Explore Commands**: Run `ghops --help` to see all available commands
2. **Read the Usage Guide**: Dive deeper into [command reference](usage.md)
3. **Try Clustering**: Group similar repositories with [clustering integration](integrations/clustering.md)
4. **Automate Workflows**: Create complex automations with [workflow orchestration](integrations/workflow.md)
5. **Query Your Repos**: Master the [query language](query-cookbook.md)

## Getting Help

- **Documentation**: You're reading it!
- **Command Help**: `ghops <command> --help`
- **GitHub Issues**: [Report bugs or request features](https://github.com/queelius/ghops/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/queelius/ghops/discussions)

## Troubleshooting Quick Fixes

### No repositories found
- Check your `repository_directories` configuration
- Ensure directories contain `.git` folders
- Use `ghops config show` to verify settings

### GitHub API rate limit
- Add a GitHub token to increase limits
- Use `--no-github-check` to skip API calls
- Configure rate limiting in config

### Permission denied errors
- Check file permissions in repository directories
- Ensure git credentials are configured
- Run with appropriate user permissions

For more detailed troubleshooting, see the [Troubleshooting Guide](guides/troubleshooting.md).