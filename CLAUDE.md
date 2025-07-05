# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ghops is a powerful CLI tool for managing GitHub repositories at scale. It provides automated repository operations, license management, and social media promotion for open source projects.

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
- `ghops/pypi.py` - PyPI package detection and API integration
- `ghops/social.py` - Social media content generation

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
- `click` - CLI framework (implied from usage)

## Configuration

Configuration is managed through `~/.ghopsrc` (JSON or TOML format). Use `GHOPS_CONFIG` environment variable to override location.

Key configuration sections:
- `general.repository_directories` - List of repo directories (supports glob patterns)
- `social_media.platforms` - Platform-specific API credentials and templates
- `service` - Background service configuration for automated posting

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