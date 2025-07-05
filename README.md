# ghops

[![PyPI Version](https://img.shields.io/pypi/v/ghops.svg)](https://pypi.org/project/ghops/)
[![Python Support](https://img.shields.io/pypi/pyversions/ghops.svg)](https://pypi.org/project/ghops/)
[![Test Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen.svg)](https://github.com/queelius/ghops)
[![Build Status](https://img.shields.io/badge/tests-138%20passing-brightgreen.svg)](https://github.com/queelius/ghops)
[![License](https://img.shields.io/pypi/l/ghops.svg)](https://github.com/queelius/ghops/blob/main/LICENSE)

A powerful, modular CLI tool for managing GitHub repositories at scale. Automate repository operations, manage licenses, and coordinate social media promotion for your open source projects.

## ✨ Features

### 🏗️ **Robust Architecture**

- **Modular Design**: Clean separation of concerns with dedicated command modules
- **Extensible**: Easy to add new commands and functionality  
- **Well-Tested**: 86% test coverage with 138 comprehensive unit and integration tests
- **Error Resilient**: Graceful handling of network failures and edge cases

### 📦 **Repository Management**

- **Multi-Repository Operations**: Clone, update, and monitor multiple repositories efficiently
- **Intelligent Sync**: Smart pull with rebase, conflict detection, and resolution strategies
- **Progress Tracking**: Real-time progress bars and detailed operation summaries
- **Flexible Discovery**: Recursive repository scanning with configurable ignore patterns

### 📄 **License Management**

- **GitHub Integration**: Fetch license templates directly from GitHub API
- **Bulk Operations**: Add licenses to multiple repositories at once
- **Template Customization**: Automatic placeholder replacement for author details
- **Multiple Formats**: Support for all major open source licenses

### 🌐 **GitHub Pages Detection**

- **Multi-Method Detection**: Scans for Jekyll, MkDocs, Sphinx, and custom configurations
- **URL Construction**: Automatically builds GitHub Pages URLs from repository metadata
- **Documentation Tracking**: Monitor which projects have active documentation sites

### 📱 **Social Media Automation**

- **Content Generation**: Template-driven post creation for Twitter, LinkedIn, and Mastodon
- **Smart Sampling**: Random repository selection with configurable filters
- **Dry Run Support**: Preview posts before publishing
- **Rate Limiting**: Built-in posting frequency controls and daily limits

### ⚙️ **Configuration Management**

- **Flexible Formats**: Support for both JSON and TOML configuration files
- **Environment Overrides**: All settings can be controlled via environment variables
- **Default Merging**: Intelligent combination of defaults, file settings, and overrides
- **Example Generation**: Built-in config template generation

### 🤖 **Automated Service Mode**

- **Scheduled Posting**: Run ghops as a background service for automated social media posting
- **Multi-Directory Support**: Configure multiple repository locations with glob pattern support
- **Periodic Reporting**: Generate comprehensive repository status reports
- **Email Notifications**: Automated email alerts and daily summaries
- **Error Monitoring**: Built-in error detection and email alerts

## 🚀 Installation

You can install `ghops` via `pip`:

```bash
pip install ghops
```

Or from source:

```bash
git clone https://github.com/queelius/ghops.git
cd ghops
make install
```

## ⚡ Quick Start

```bash
# Generate a configuration file with examples
ghops config generate

# Clone all your repos
ghops get

# Update all repos in the current directory
ghops update -r

# Check the status of all repos (includes PyPI and GitHub Pages info)
ghops status -r

# Quick status check without PyPI detection
ghops status --no-pypi-check

# Sample repositories for social media posting
ghops social sample --size 3

# Create social media posts (dry run)
ghops social post --dry-run
```

## 📋 Commands

### Repository Operations

- **`ghops get [options]`** - Clone all repositories from your GitHub account
  - `--users USER [USER ...]` - Specify GitHub usernames to clone from
  - `--dir DIRECTORY` - Target directory for cloning
  - `--ignore REPO [REPO ...]` - Skip specific repositories
  - `--license LICENSE` - Add license files during cloning
  - `--dry-run` - Preview operations without making changes

- **`ghops update [options]`** - Update local repositories
  - `-r, --recursive` - Search for repositories recursively
  - `--auto-commit` - Commit changes before pulling
  - `--commit-message MESSAGE` - Custom commit message
  - `--conflicts {abort,ours,theirs}` - Conflict resolution strategy
  - `--prompt` - Ask before pushing changes
  - `--license LICENSE` - Add/update license files during update

- **`ghops status [options]`** - Comprehensive repository status
  - `-r, --recursive` - Search recursively
  - `--json` - Output in JSON format for scripting
  - `--no-pypi-check` - Skip PyPI status checks (faster)
  - `--no-pages-check` - Skip GitHub Pages detection
  - `--summary` - Show summary statistics

### Configuration Management

- **`ghops config generate`** - Create example configuration file
- **`ghops config show`** - Display current configuration with all merges applied

### License Operations

- **`ghops license list [--json]`** - Show available license templates
- **`ghops license show LICENSE [--json]`** - Display specific license template

### Social Media Automation

- **`ghops social sample [options]`** - Preview repository selection
  - `--size N` - Number of repositories to sample
  - `--json` - Output in JSON format

- **`ghops social post [options]`** - Generate and post content
  - `--size N` - Number of posts to create
  - `--dry-run` - Preview posts without publishing
  - `--platforms PLATFORM [PLATFORM ...]` - Target specific platforms

### Service Mode

- **`ghops service start`** - Start automated posting service
  - `--dry-run` - Run service in preview mode
- **`ghops service run-once`** - Execute single posting cycle
  - `--dry-run` - Preview what would be posted

## 🔧 Advanced Configuration

`ghops` uses a configuration file located at `~/.ghopsrc` (JSON or TOML format). Set custom location with `GHOPS_CONFIG` environment variable.

### Key Configuration Sections

#### Repository Directories

```toml
[general]
# Multiple directories with glob pattern support
repository_directories = [
    "~/github",           # Direct path
    "~/projects/*/repos", # Glob pattern
    "~/work/code"         # Another direct path
]
github_username = "your_username"
```

#### Service Configuration

```toml
[service]
enabled = true                  # Enable scheduled posting service
interval_minutes = 120          # Minutes between posting cycles
start_time = "09:00"           # Preferred start time

[service.reporting]
enabled = true                  # Enable periodic reports
interval_hours = 24            # Hours between reports
include_stats = true           # Include operation statistics
include_status = true          # Include repository status
include_recent_activity = true # Include recent activity

[service.notifications.email]
enabled = true                 # Enable email notifications
smtp_server = "smtp.gmail.com" # SMTP server
smtp_port = 587                # SMTP port
username = "your@email.com"    # Email username
password = "app_password"      # Email password/app password
from_email = "your@email.com"  # From address
to_email = "your@email.com"    # To address
daily_summary = true           # Send daily reports
error_alerts = true            # Send error alerts
```

#### Social Media Platforms

```toml
[social_media.platforms.twitter]
enabled = false
api_key = "your_api_key"
api_secret = "your_api_secret"
access_token = "your_access_token"
access_token_secret = "your_access_token_secret"

[social_media.platforms.twitter.templates]
pypi_release = "🚀 New release: {package_name} v{version} is now available on PyPI! {pypi_url} #{package_name} #python #opensource"
github_pages = "📖 Updated documentation for {repo_name}: {pages_url} #docs #opensource"
random_highlight = "✨ Working on {repo_name}: {description} {repo_url} #{language} #coding"
```

#### Posting Rules

```toml
[social_media.posting]
random_sample_size = 3          # Number of repos to randomly highlight
daily_limit = 5                 # Maximum posts per day
min_hours_between_posts = 2     # Minimum time between posts
exclude_private = true          # Don't post about private repos
exclude_forks = true            # Don't post about forked repos
```

## 💡 Examples

### Check Repository Status

```bash
# Full status with PyPI and GitHub Pages
ghops status -r

# Fast status check
ghops status --no-pypi-check

# JSON output for scripting
ghops status --json
```

### Social Media Promotion

```bash
# See what repositories would be selected
ghops social sample --size 5

# Preview social media posts
ghops social post --dry-run --size 3

# Actually post (requires configured API credentials)
ghops social post --size 2
```

### Repository Management

```bash
# Clone all your repositories
ghops get --dir ~/projects

# Update repositories recursively
ghops update -r --dir ~/projects

# Add MIT license to repositories during update
ghops update -r --license mit --license-name "Your Name" --license-email "you@example.com"
```

### Service Mode Operations

```bash
# Start automated service (background posting and reporting)
ghops service start

# Test service with dry-run
ghops service start --dry-run

# Run single cycle for testing
ghops service run-once --dry-run

# Create systemd service (see examples/ghops.service)
sudo systemctl enable ghops
sudo systemctl start ghops
```

### Multi-Directory Management

```bash
# Configure multiple repository locations
ghops config generate  # Edit to add repository_directories

# Status across all configured directories
ghops status

# Update repositories in all configured locations
ghops update -r
```

## ⚡ Performance & Advanced Usage

### Performance Options

- Use `--no-pypi-check` for faster status checks when you don't need PyPI information
- Use `--no-pages-check` to skip GitHub Pages detection
- Configure `max_concurrent_operations` in config for better performance

## 🧪 Testing & Quality

- **138 comprehensive tests** covering all major functionality
- **86% test coverage** with unit and integration testing
- **Continuous integration** with automated testing
- **Error handling** for network failures and edge cases
- **Performance benchmarks** for large repository sets
- **Mock testing** for reliable external API testing

### Test Coverage by Module

- **CLI & Commands**: Complete argument parsing and execution testing
- **Configuration System**: All file formats and environment override scenarios
- **PyPI Integration**: Package detection, API calls, and error conditions
- **Social Media**: Content generation, platform integration, and rate limiting
- **License Management**: GitHub API integration and template processing
- **Status Reporting**: Repository scanning, progress tracking, and output formatting

## 🏗️ Architecture

`ghops` follows a clean, modular architecture designed for maintainability and extensibility:

```text
ghops/
├── cli.py              # Main CLI entry point with click
├── __main__.py         # Python module execution entry
├── commands/           # Modular command implementations
│   ├── get.py         # Repository cloning logic
│   ├── update.py      # Repository updating and syncing
│   ├── status.py      # Status reporting and analytics
│   └── license.py     # License management operations
├── config.py          # Configuration loading and merging
├── utils.py           # Shared utilities and helpers
├── pypi.py            # PyPI package detection and API
└── social.py          # Social media content generation
```

### Design Principles

- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Error Resilience**: Graceful handling of network failures and edge cases
- **Performance**: Optional API checks and concurrent operations
- **Extensibility**: Easy to add new commands and features
- **Testability**: Comprehensive test coverage with mocking for external services

## 🤝 Contributing

Contributions are welcome! Please see the [Contributing Guide](contributing.md) for more details.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

© 2025 [Alex Towell](https://github.com/queelius)
