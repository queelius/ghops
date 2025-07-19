# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ghops is a multi-platform git project management system that helps developers manage the full lifecycle of their projects across multiple platforms - from local development through hosting, distribution, documentation, and promotion.

**Key Philosophy**: Local-first with remote awareness. Your local git repositories are the ground truth, and remote platforms (GitHub, GitLab, PyPI, etc.) are services that enrich and distribute your projects.

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
- `make test` - Run comprehensive test suite (138 tests) using pytest
- `make install` - Install dependencies and package in development mode
- `make build` - Build the package for distribution
- `make clean` - Remove build artifacts and cache files

### Documentation
- `make docs` - Build documentation using mkdocs
- `make serve-docs` - Serve documentation locally at localhost:8000
- `make gh-pages` - Deploy documentation to GitHub Pages

### Testing
- `pytest --maxfail=3 --disable-warnings -v` - Run tests with detailed output
- Tests are located in `tests/` directory with 86% coverage

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

### New Architecture Components
- **Metadata Store** - Replaces caching, single source of repo metadata
- **Provider System** - Pluggable modules for GitHub, GitLab, PyPI, etc.
- **Query Engine** - Powerful queries across all metadata with fuzzy matching
- **Export System** - Generate markdown, Hugo content, documentation

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
- **list** - List repositories with deduplication and metadata
- **status** - Repository status with git, license, package info
- **get** - Clone repositories from GitHub
- **update** - Update and sync repositories
- **license** - Manage open source licenses
- **social** - Social media automation
- **service** - Background service for automation
- **config** - Configuration management
- **catalog** - Tag-based repository organization
- **query** - Fuzzy search with custom query language
- **metadata** - Metadata store management
- **docs** - Documentation detection, building, and deployment

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

## Working with the Codebase

### Command Implementation
New commands should:
1. Create a new file in `ghops/commands/`
2. Implement the command handler using Click decorators
3. Add business logic to `ghops/core.py` as pure functions
4. Register the command in `ghops/cli.py`

### Testing
- Follow existing test patterns in `tests/`
- Mock external API calls for reliability
- Test both success and error scenarios
- Maintain high test coverage (currently 86%)

### Configuration Changes
When adding new configuration options:
1. Update `get_default_config()` in `config.py`
2. Update environment variable handling in `apply_env_overrides()`
3. Document the new options in README.md

## Project Structure Notes

- Entry point: `ghops/cli.py:main()`
- Package metadata: `pyproject.toml` (uses hatchling build system)
- Documentation: `docs/` directory with mkdocs
- Service mode: Can run as daemon for automated operations
- Multi-platform social media: Twitter, LinkedIn, Mastodon support

## Important Design Decisions

### No Caching
We removed the caching layer in favor of:
- Direct API calls with rate limit handling
- Metadata store for persistent data
- Age-based refresh (--max-age option)

### Tag System
- **Explicit tags**: User-assigned tags stored in catalog
- **Implicit tags**: Auto-generated (repo:name, dir:parent, lang:python)
- **Provider tags**: From GitHub topics, GitLab labels, etc.
- **Protected namespaces**: Some prefixes reserved for system use

### Query Language
- Simple boolean expressions with fuzzy matching
- Path-based access to nested fields (license.key)
- Operators: ==, !=, ~=, >, <, contains, in
- Examples: "language ~= 'pyton'", "'python' in topics"