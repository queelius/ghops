# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ghops is a multi-platform git project management system that helps developers manage the full lifecycle of their projects across multiple platforms - from local development through hosting, distribution, documentation, and promotion.

**Key Philosophy**: Local-first with remote awareness. Your local git repositories are the ground truth, and remote platforms (GitHub, GitLab, PyPI, etc.) are services that enrich and distribute your projects.

**Current Version**: 0.8.0 (with clustering, workflow orchestration, TUI, and shell features)

## Vision & Use Cases

### Core Capabilities
1. **Multi-Platform Management** - Track repos across GitHub, GitLab, Bitbucket, etc.
2. **Distribution & Publishing** - Release to PyPI, npm, DOIs, documentation sites
3. **Project Promotion** - Coordinate social media, track engagement metrics
4. **Local Organization** - Tag-based catalogs, dynamic views, powerful queries
5. **Documentation Management** - Generate and publish docs to multiple platforms

### Target Workflows
- Manage collections of repos across multiple hosting providers
- Orchestrate releases across platforms (git tag → GitHub → PyPI → social)
- Query and organize repos by any metadata (local or remote)
- Export portfolio/documentation views for blogs and websites
- Track project health across all dimensions

## CRITICAL DESIGN PRINCIPLES

### 1. Unix Philosophy First
- **Do one thing well**: Each command has a single, clear purpose
- **Compose via pipes**: Output of one command feeds into another
- **Text streams are the universal interface**: JSONL is our text stream format

### 2. Output Format Rules
- **DEFAULT is JSONL**: Every command outputs newline-delimited JSON by default
- **Stream, don't collect**: Output each object as it's processed
- **NO --json flag**: JSONL is already JSON (one object per line)
- **Human output is opt-in**: Use --pretty or --table for human-readable tables
- **Errors go to stderr**: Keep stdout clean for piping

### 3. Architecture Layers
```
Commands (CLI) → Core Functions → Data Models
     ↓                ↓              ↓
   Parse args    Pure functions   Plain dicts
   Handle I/O    No side effects  Consistent schema
   Format output Return generators Stream-friendly
```

### 4. Core Function Rules
- **Pure functions**: Take data, return data, no side effects
- **Return generators**: Enable streaming, don't collect everything in memory
- **Consistent data models**: Always return dicts with documented schemas
- **No printing**: Core functions never print, format, or interact with the terminal
- **Testable**: Can be tested without mocking filesystem or network

### 5. Command Implementation Pattern
```python
@click.command()
@click.option('--pretty', is_flag=True, help='Display as formatted table')
def status_handler(pretty):
    """Show repository status."""
    # Get data as generator
    repos = core.get_repository_status(path)
    
    if pretty:
        # Collect and render as table
        render.status_table(list(repos))
    else:
        # Stream JSONL (default)
        for repo in repos:
            print(json.dumps(repo), flush=True)
```

### 6. Error Handling
- **Structured errors**: Errors are JSON objects: `{"error": "message", "context": {...}}`
- **Continue on error**: Don't stop the stream, output error objects
- **stderr for fatal errors**: Only use stderr for unrecoverable errors

### 7. Standard Data Models

#### Repository Status Object
```json
{
  "path": "/absolute/path/to/repo",
  "name": "repo-name",
  "status": {
    "branch": "main",
    "clean": true,
    "ahead": 0,
    "behind": 0,
    "has_upstream": true,
    "uncommitted_changes": false,
    "unpushed_commits": false
  },
  "remote": {
    "url": "https://github.com/user/repo.git",
    "owner": "user",
    "name": "repo"
  },
  "license": {
    "type": "MIT",
    "file": "LICENSE",
    "year": 2024,
    "holder": "John Doe"
  },
  "package": {
    "type": "python",
    "name": "my-package",
    "version": "1.0.0",
    "published": true,
    "registry": "pypi"
  },
  "github": {
    "pages_url": "https://user.github.io/repo",
    "is_private": false,
    "is_fork": false,
    "stars": 42
  }
}
```

#### Error Object
```json
{
  "error": "string describing error",
  "type": "git_error|file_error|api_error|...",
  "context": {
    "path": "/path/to/repo",
    "command": "git status",
    "stderr": "detailed error output"
  }
}
```

## Development Commands

### Essential Commands
```bash
make install          # Create .venv, install dependencies and package in dev mode
make test            # Run test suite using pytest (requires .venv activation)
make build           # Build wheel and sdist packages
make clean           # Remove build artifacts, cache files, and .venv
```

**IMPORTANT**: All `make` commands automatically use `.venv/` virtual environment. The Makefile handles activation internally. You don't need to manually activate the venv before running make commands.

### Documentation
```bash
make docs            # Build documentation using mkdocs
make serve-docs      # Serve documentation at http://localhost:8000
make gh-pages        # Deploy documentation to GitHub Pages
```

### Publishing
```bash
make build-pypi      # Build packages for PyPI distribution
make publish-pypi    # Upload to PyPI (requires twine and credentials)
```

### Testing
```bash
# Run all tests via make (uses .venv automatically)
make test

# Or activate .venv and run pytest directly:
source .venv/bin/activate

# Run all tests with verbose output
pytest --maxfail=3 --disable-warnings -v

# Run specific test file
pytest tests/test_core.py -v

# Run tests matching pattern
pytest -k "test_status" -v

# Run with coverage (RECOMMENDED after changes)
pytest --cov=ghops --cov-report=html

# Run with coverage and open report
pytest --cov=ghops --cov-report=html && open htmlcov/index.html
```

**Test Coverage Requirements**:
- Test suite contains 138+ comprehensive tests with ~86% code coverage
- Tests located in `tests/` directory, using `pyfakefs` for filesystem mocking
- **ALWAYS run coverage after adding new features**: `pytest --cov=ghops --cov-report=html`
- New code should maintain or improve the 86% coverage threshold
- Coverage report available in `htmlcov/index.html` after running coverage

## Architecture

### Core Module Structure
- `ghops/cli.py` - Main CLI entry point using Click framework
- `ghops/config.py` - Configuration management with JSON/TOML support
- `ghops/core.py` - Pure business logic functions (side-effect free)
- `ghops/commands/` - Individual command implementations
- `ghops/utils.py` - Shared utility functions
- `ghops/metadata.py` - Unified metadata store for all repo information
- `ghops/simple_query.py` - Query language with fuzzy matching
- `ghops/pypi.py` - PyPI package detection and API integration
- `ghops/social.py` - Social media content generation
- `ghops/tags.py` - Tag management and implicit tag generation

### Architecture Components

**Data Layer**:
- **Metadata Store** (`ghops/metadata.py`) - Unified metadata storage replacing distributed caching
  - Stores all repo info: git status, remotes, licenses, packages, GitHub data
  - Language detection with extensive file type support
  - Age-based refresh with `--max-age` option
  - Located at `~/.ghops/metadata.json`

**Business Logic**:
- **Core** (`ghops/core.py`) - Pure, side-effect-free business logic functions
  - Functions return generators for streaming
  - Never print or interact with terminal
  - Take data, return data (dicts/lists)
  - Highly testable without mocks

**CLI Layer**:
- **Commands** (`ghops/commands/*.py`) - Individual command implementations
  - Parse arguments with Click
  - Get data from core functions (as generators)
  - Format output: JSONL (default) or --pretty (tables)
  - Handle I/O and user interaction

**Query & Filter**:
- **Query Engine** (`ghops/query.py`, `ghops/simple_query.py`) - Powerful queries with fuzzy matching
- **Repo Filter** (`ghops/repo_filter.py`) - Common filtering logic for tags/queries
- **Tags System** (`ghops/tags.py`) - Tag management with implicit tags

**Export & Rendering**:
- **Export Components** (`ghops/export_components.py`, `ghops/export_components_impl.py`) - Component-based export system
- **Component Hooks** (`ghops/component_hooks.py`) - Customization hooks for exports
- **Format Utils** (`ghops/format_utils.py`) - Output format utilities (JSONL, CSV, YAML, TSV)
- **Hugo Export** (`ghops/hugo_export.py`) - Specialized Hugo site generation
- **Render** (`ghops/render.py`) - Table rendering with Rich library

**Integrations** (v0.8.0+):
- **Clustering** (`ghops/integrations/clustering/`) - Repository clustering algorithms
- **Workflow** (`ghops/integrations/workflow/`) - Workflow orchestration engine
- **Templates** (`ghops/integrations/templates/`) - Template extraction and management
- **Timemachine** (`ghops/integrations/timemachine/`) - Historical analysis
- **Network Analysis** (`ghops/integrations/network_analysis.py`) - Repository relationship graphs

**UI Components**:
- **TUI** (`ghops/tui/`) - Interactive text interface with Textual
  - `app.py` - Main TUI application entry point
  - `dashboard.py` - Dashboard screen with repository overview
  - `activity.py` - Activity tracking and monitoring
  - `watcher.py` - File system watching for live updates
  - `file_poller.py` - Polling-based file monitoring
- **Shell** (`ghops/shell/`) - Interactive shell environment
  - `shell.py` - REPL-style command shell with history
- **CLI Utils** (`ghops/cli_utils.py`) - Common CLI decorators and utilities
- **Progress** (`ghops/progress.py`) - Unified progress reporting system

### Key Design Patterns
- **Modular Commands**: Each command is a separate module in `ghops/commands/`
- **Pure Core Logic**: `core.py` contains side-effect-free business logic
- **Configuration Cascading**: Defaults → config file → environment variables
- **Rich CLI**: Uses Rich library for enhanced terminal output

### Dependencies
- `rich>=13.0.0` - Enhanced terminal output and progress bars
- `requests>=2.25.0` - HTTP requests for API integration
- `packaging>=21.0` - Package version handling
- `tweepy` - Twitter API integration
- `click` - CLI framework
- `rapidfuzz` - Fuzzy string matching for query language
- `toml` - TOML configuration file support

### Commands Implemented

Core commands:
- **list** - List repositories with deduplication and metadata
- **status** - Repository status with git, license, package info
- **get** - Clone repositories from GitHub
- **update** - Update and sync repositories
- **license** - Manage open source licenses
- **config** - Configuration management

Organization & discovery:
- **tag** - Hierarchical tag management (add, remove, move, list, tree)
- **catalog** - Tag-based repository organization (legacy, use `tag` instead)
- **query** - Fuzzy search with custom query language
- **metadata** - Metadata store management

Content generation:
- **social** - Social media automation
- **export** - Generate portfolios in multiple formats (markdown, hugo, html, pdf, etc.)
- **docs** - Documentation detection, building, and deployment

Advanced features:
- **audit** - Repository health checks and auto-fix capabilities
- **service** - Background service for automation
- **network** - Network analysis of repository relationships
- **ai** - AI-powered repository conversation features
- **cluster** - Repository clustering and consolidation analysis

Interactive:
- **tui** - Interactive text user interface with dashboard
- **shell** - Interactive ghops shell with command history and VFS navigation

Workflow & automation:
- **workflow** - YAML-based workflow orchestration engine

Hidden/integration commands:
- **customize** - Template customization for exports

## Configuration

Configuration is managed through `~/.ghops/config.json` (or YAML). Use `GHOPS_CONFIG` environment variable to override location.

Key configuration sections:
- `general.repository_directories` - List of repo directories (supports ** glob patterns)
- `github.token` - GitHub API token (or use GHOPS_GITHUB_TOKEN env var)
- `github.rate_limit` - Retry configuration with exponential backoff
- `social_media.platforms` - Platform-specific API credentials and templates
- `service` - Background service configuration for automated operations
- `repository_tags` - Manual tag assignments for repos

### Rate Limiting
GitHub API calls use intelligent rate limiting:
- Configurable max_retries and max_delay_seconds
- Respects GitHub's rate limit reset time
- Exponential backoff between retries

## Important Design Decisions

### No Caching
We removed the caching layer in favor of:
- Direct API calls with rate limit handling
- Metadata store for persistent data
- Age-based refresh (--max-age option)

### Workflow System Architecture
- **YAML-based**: Human-readable, version-control friendly
- **DAG execution**: Automatic dependency resolution and parallel execution
- **Action types**: shell, python, http, git, ghops, custom
- **Template expressions**: Jinja2-style variable interpolation
- **Error handling**: Configurable retry with exponential backoff

### Clustering System Design
- **Multiple algorithms**: K-means, DBSCAN, hierarchical, network-based, ensemble
- **Feature extraction**: Technology stack, size metrics, activity patterns, complexity
- **Code duplication**: Function/class-level similarity detection across repos
- **Consolidation advisor**: Confidence scoring and effort estimation for merges

### Tag System
- **Explicit tags**: User-assigned tags stored in catalog
- **Implicit tags**: Auto-generated (repo:name, dir:parent, lang:python)
- **Provider tags**: From GitHub topics, GitLab labels, etc.
- **Protected namespaces**: Some prefixes reserved for system use

### Query Language
- Simple boolean expressions with fuzzy matching via `rapidfuzz`
- Path-based access to nested fields (e.g., `license.key`, `package.version`)
- Operators: `==`, `!=`, `~=` (fuzzy), `>`, `<`, `contains`, `in`
- Examples:
  - `"language ~= 'pyton'"` - fuzzy match Python
  - `"'ml' in topics"` - check if 'ml' in topics list
  - `"stars > 10 and language == 'Python'"` - multiple conditions

## Project Structure Notes

- Entry point: `ghops/cli.py:main()`
- Package metadata: `pyproject.toml` (uses hatchling build system)
- Build system: hatchling (not setuptools)
- Documentation: `docs/` directory with mkdocs (Material theme)
- Service mode: Can run as daemon for automated operations
- Multi-platform social media: Twitter, LinkedIn, Mastodon support
- Virtual environment: All make commands use `.venv/` for isolation

## Development Workflow

### Initial Setup
```bash
# Clone and set up development environment
git clone https://github.com/queelius/ghops.git
cd ghops
make install  # Creates .venv and installs dependencies

# Verify installation
source .venv/bin/activate
ghops --version
pytest --version
```

### Development Cycle
1. **Make changes** to code in `ghops/` directory
2. **Write tests** in `tests/` directory
3. **Run tests** with `make test` or `pytest`
4. **Check coverage** with `pytest --cov=ghops --cov-report=html`
5. **Build docs** with `make docs` if updating documentation
6. **Commit** changes following conventional commits style

### Before Committing
```bash
# 1. Run full test suite
pytest --maxfail=3 --disable-warnings -v

# 2. Check test coverage (aim for >86%)
pytest --cov=ghops --cov-report=html

# 3. Build package to verify no build issues
make build

# 4. Build docs to verify documentation builds
make docs
```

## Working with the Codebase

### Adding New Commands

1. **Create command file** in `ghops/commands/your_command.py`:
```python
import click
from ..config import load_config
from ..core import your_core_function

@click.command('your-command')
@click.option('--pretty', is_flag=True, help='Display as formatted table')
def your_command_handler(pretty):
    """Brief description of your command."""
    # Get data as generator from core
    results = your_core_function()

    if pretty:
        # Render as table for humans
        from ..render import render_table
        render_table(list(results), columns=['key1', 'key2'])
    else:
        # Stream JSONL (default)
        import json
        for result in results:
            print(json.dumps(result), flush=True)
```

2. **Add business logic** to `ghops/core.py`:
```python
def your_core_function() -> Generator[Dict[str, Any], None, None]:
    """
    Pure function that does the work.

    Yields:
        Dict with consistent schema
    """
    for item in data_source:
        yield {
            "key1": value1,
            "key2": value2,
            "status": "success"
        }
```

3. **Register command** in `ghops/cli.py`:
```python
from ghops.commands.your_command import your_command_handler

# In the cli() function setup:
cli.add_command(your_command_handler)
```

4. **Write tests** in `tests/test_your_command.py`:
```python
import pytest
from ghops.core import your_core_function

def test_your_core_function():
    results = list(your_core_function())
    assert len(results) > 0
    assert 'key1' in results[0]
```

### Testing Patterns

**Core function tests** (no mocking needed):
```python
def test_list_repos():
    """Test pure business logic."""
    result = core.list_repos(
        source="directory",
        directory="/tmp/test",
        recursive=False,
        dedup=False,
        dedup_details=False
    )
    assert result['status'] in ['success', 'no_repos_found']
```

**Command tests** (mock external calls):
```python
from unittest.mock import patch, MagicMock

@patch('ghops.commands.status.get_git_status')
def test_status_command(mock_git_status):
    mock_git_status.return_value = {'branch': 'main', 'clean': True}
    # Test command behavior
```

**Integration tests** (use fixtures):
```python
def test_full_workflow(tmp_path):
    """Test complete workflow with temp files."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    # Run commands, verify results
```

### Configuration Changes

When adding new configuration options:

1. **Update defaults** in `ghops/config.py`:
```python
def get_default_config():
    return {
        # ...existing...
        'your_section': {
            'your_option': default_value
        }
    }
```

2. **Add environment variable** in `apply_env_overrides()`:
```python
def apply_env_overrides(config):
    # ...existing...
    if 'GHOPS_YOUR_OPTION' in os.environ:
        config['your_section']['your_option'] = os.environ['GHOPS_YOUR_OPTION']
```

3. **Document in README.md** and `docs/` if it's user-facing

### Output Format Guidelines

**Default JSONL output**:
```python
# Stream one JSON object per line
for item in items:
    print(json.dumps(item), flush=True)
```

**Optional pretty output**:
```python
if pretty:
    from ..render import render_table
    render_table(list(items), columns=['col1', 'col2'])
```

**Error output**:
```python
# Errors go to stderr
import sys
error_obj = {
    "error": "Description",
    "type": "error_type",
    "context": {"path": "/some/path"}
}
print(json.dumps(error_obj), file=sys.stderr)
```

**Support multiple formats** with `format_utils`:
```python
from ..format_utils import format_output

# Will respect GHOPS_FORMAT env var or --format flag
format_output(data, format='json')  # json, csv, yaml, tsv
```

### Common Utilities

**Find repositories**:
```python
from ghops.utils import find_git_repos, find_git_repos_from_config

repos = find_git_repos('/path/to/search', recursive=True)
config_repos = find_git_repos_from_config(config['general']['repository_directories'], recursive=False)
```

**Git operations**:
```python
from ghops.utils import get_git_status, get_remote_url, parse_repo_url, run_command

status = get_git_status('/path/to/repo')
remote = get_remote_url('/path/to/repo')
owner, name = parse_repo_url(remote)
output, returncode = run_command(['git', 'status'], cwd='/path/to/repo')
```

**Metadata access**:
```python
from ghops.metadata import get_metadata_store

store = get_metadata_store()
metadata = store.get_metadata('/path/to/repo')
store.update_metadata('/path/to/repo', metadata)
```

**Progress reporting**:
```python
from ghops.progress import get_progress_reporter

with get_progress_reporter() as progress:
    task = progress.add_task("Processing", total=len(items))
    for item in items:
        # do work
        progress.update(task, advance=1)
```

### Exit Codes

Use exit codes from `ghops/exit_codes.py`:
```python
from ghops.exit_codes import (
    ExitCode,
    NoReposFoundError,
    ConfigError,
    NetworkError
)

# Raise for specific errors
raise NoReposFoundError("No repositories found in /path")

# Or return exit codes
sys.exit(ExitCode.NO_REPOS_FOUND)
```

### Interactive Components

**TUI Dashboard** (`ghops/tui/dashboard.py`):
- Rich visual dashboard with repository overview
- Live updates via file system watching
- Activity tracking and visualization
- Keyboard navigation and shortcuts

**Shell Interface** (`ghops/shell/shell.py`):
- REPL-style command shell with completion
- Command history and multi-line support
- Built-in help and inline documentation

**Activity Monitoring**:
- `ghops htop` - Process-style repository monitor
- `ghops top` - Real-time activity tracking
- Live updates from git commits and metadata changes

### Workflow Examples

Workflows are stored in `~/.ghops/workflows/` as YAML files:

```yaml
name: morning-routine
description: Daily repository maintenance
steps:
  - name: update-metadata
    action: ghops
    args: ["metadata", "refresh", "--github"]

  - name: check-status
    action: ghops
    args: ["status", "-r"]

  - name: audit-security
    action: ghops
    args: ["audit", "security"]
    if: "{{ steps.check_status.status == 'success' }}"
```

Run with: `ghops workflow run morning-routine`

### Clustering Workflow

Typical clustering analysis workflow:

```bash
# 1. Extract features from repositories
ghops cluster analyze --algorithm kmeans --n-clusters auto

# 2. Find code duplication
ghops cluster find-duplicates --threshold 0.85 --pretty

# 3. Get consolidation recommendations
ghops cluster suggest-consolidation --min-confidence 0.7

# 4. Export results
ghops cluster export --format html --output ./cluster-report/
```

### Shell VFS Tag Management

The interactive shell provides a virtual filesystem for tag management:

```bash
# Start the shell
ghops shell

# Navigate the tag hierarchy
cd /by-tag
ls                          # Show all top-level tags
cd alex
ls                          # Show alex/* tags
cd beta
ls                          # Show repos tagged with alex/beta

# Add tags using filesystem operations
cp /repos/myproject /by-tag/work/active
cp /repos/myproject /by-tag/topic/ml/research

# Move repos between tags
mv /by-tag/alex/beta/myproject /by-tag/alex/production

# Remove tags
rm /by-tag/work/active/myproject

# Create tag namespaces
mkdir -p /by-tag/client/acme/backend

# Refresh VFS after external changes
refresh
```

### CLI Tag Management (Shell Parity)

The CLI now has full parity with shell operations:

```bash
# Add tags (like shell 'cp')
ghops tag add myproject alex/beta
ghops tag add myproject topic:ml/research work/active

# Remove tags (like shell 'rm')
ghops tag remove myproject alex/beta

# Move between tags (like shell 'mv')
ghops tag move myproject alex/beta alex/production

# List all tags
ghops tag list

# List repositories with specific tag
ghops tag list -t "alex/*"

# Show tag hierarchy as tree
ghops tag tree
ghops tag tree -t alex          # Show alex/* subtree

# Show tags for a repository
ghops tag list -r myproject
```

**Hierarchical Tag Examples**:
- Simple: `alex/beta` → `/by-tag/alex/beta/` or `ghops tag add repo alex/beta`
- Key:value: `lang:python` → `/by-tag/lang/python/` or `ghops tag add repo lang:python`
- Multi-level: `topic:scientific/engineering/ai` → `/by-tag/topic/scientific/engineering/ai/` or `ghops tag add repo topic:scientific/engineering/ai`

## Important Implementation Notes

### Metadata Store Location
- Default: `~/.ghops/metadata.json`
- Set `GHOPS_METADATA_PATH` to override
- Automatically refreshes based on `--max-age` option

### Rate Limiting (GitHub API)
- Configured in `github.rate_limit` section
- Exponential backoff with max retries
- Respects GitHub's rate limit reset time
- Use `GHOPS_GITHUB_TOKEN` for higher limits

### Service Mode
- Can run as daemon with `ghops service start`
- Configured intervals for posting and reporting
- Email notifications via SMTP
- Systemd service file in `examples/ghops.service`

### TUI Mode
- Launch with `ghops tui` for interactive dashboard
- Launch with `ghops shell` for interactive command shell with hierarchical tag VFS
- Requires `textual>=0.40.0` optional dependency
- Real-time file system watching with `watchdog>=3.0.0`
- Activity tracking from git history and metadata changes

### Interactive Shell with Hierarchical Tag VFS
- **Virtual Filesystem**: Navigate repositories like a filesystem
  - `/repos/` - All repositories
  - `/by-tag/` - Hierarchical tag-based organization
  - `/by-language/` - Grouped by programming language
  - `/by-status/` - Grouped by git status (clean/dirty)
- **Filesystem Operations for Tags**:
  - `cp /repos/myproject /by-tag/alex/beta` - Add tag to repository
  - `mv /by-tag/alex/beta/myproject /by-tag/alex/production` - Move between tags
  - `rm /by-tag/alex/beta/myproject` - Remove tag from repository
  - `mkdir -p /by-tag/work/client/acme` - Create tag namespace
- **Tag Hierarchies**: Tags like `alex/beta` and `topic:scientific/engineering/ai` create directory structures
- **Navigation**: Use `cd`, `ls`, `pwd` like a regular shell
- **Full command completion and history**
- **Inline help and documentation**
- **Multi-line command support**
- **Exit with `exit` or `quit` commands**

### Integrations
Optional dependencies enable advanced features:
- **Clustering**: `numpy>=1.20.0`, `scikit-learn>=1.0.0`, `scipy>=1.7.0`
  - K-means, DBSCAN, hierarchical, and network-based clustering
  - Code duplication detection across repositories
  - Consolidation advisor with confidence scoring
- **Workflow**: `pyyaml>=5.0.0`
  - YAML-based workflow definitions
  - DAG execution with parallel/sequential steps
  - Built-in actions: shell, python, http, git, ghops
- **Network Analysis**: `numpy>=1.20.0`
  - Repository relationship graphs
  - Dependency analysis
- **Export (PDF)**: `weasyprint>=54.0`
  - PDF portfolio generation
- **TUI**: `textual>=0.40.0`, `textual-dev>=1.0.0`, `watchdog>=3.0.0`
  - Interactive text interfaces
  - Real-time monitoring

Install all: `pip install ghops[all]`