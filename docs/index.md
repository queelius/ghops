# ghops Documentation

Welcome to the documentation for **ghops** - a powerful, local-first git project management system that helps developers manage the full lifecycle of their projects across multiple platforms.

## What is ghops?

`ghops` is a comprehensive project management tool that treats your local git repositories as the source of truth, with remote platforms (GitHub, GitLab, PyPI, etc.) serving as enrichment and distribution services. It provides powerful organization, discovery, auditing, and export capabilities for managing projects at scale.

## 🎯 Core Philosophy

- **Local-First**: Your local git repositories are the ground truth
- **JSONL by Default**: All commands output newline-delimited JSON for Unix pipeline composition
- **Tag-Based Organization**: Powerful tagging system with implicit tags from metadata
- **Query Language**: Fuzzy search with simple boolean expressions
- **Multi-Platform**: Works with GitHub, GitLab, Bitbucket, and more (coming soon)

## ✨ Key Features

### 🔍 **Repository Discovery & Organization**
- **Tag-Based Catalogs**: Organize repos with explicit tags and auto-generated implicit tags
- **Powerful Query Language**: Find repos with fuzzy matching: `ghops query "language ~= 'pyton'"`
- **Metadata Store**: Local database of all repository information for fast queries
- **Implicit Tags**: Automatic tags like `repo:name`, `lang:python`, `has:docs`, `dir:parent`

### 🛡️ **Repository Auditing**
- **Comprehensive Health Checks**: Audit repos for licenses, READMEs, security issues, and more
- **Auto-Fix Capabilities**: Automatically fix common issues with `--fix` flag
- **Security Scanning**: Detect hardcoded secrets and security vulnerabilities
- **Dependency Auditing**: Check for missing or outdated dependency management
- **Documentation Health**: Verify documentation setup and configuration

### 📄 **Portfolio Export**
- **Multiple Formats**: Export to Markdown, Hugo, HTML, JSON, CSV, LaTeX, and PDF
- **Interactive HTML**: Generated HTML includes live search, filtering, and sorting
- **Hugo Integration**: Create complete Hugo site structure with taxonomies
- **Grouping & Organization**: Group exports by language, directory, or custom tags
- **Template Support**: Customizable export templates for all formats

### 📚 **Documentation Management**
- **Multi-Tool Support**: Works with MkDocs, Sphinx, Jekyll, Hugo, and more
- **Status Checking**: See documentation health across all repos
- **Build & Serve**: Build and preview documentation locally
- **Deploy to GitHub Pages**: One-command deployment to GitHub Pages
- **Bulk Operations**: Manage docs across multiple repos simultaneously

### 🚀 **Repository Management**
- Clone all your GitHub repositories with a single command
- Update multiple repositories simultaneously with smart conflict resolution
- Track status across all your projects with detailed reporting and progress bars
- Flexible repository discovery with configurable ignore patterns

### 📦 **PyPI Integration**
- Automatically detect Python packages from `pyproject.toml`, `setup.py`, and `setup.cfg`
- Track PyPI publishing status and version information with real-time checking
- Identify outdated packages that need updates
- Performance optimized with optional checking for faster operations

### 📱 **Social Media Automation**
- Template-driven content generation for Twitter, LinkedIn, and Mastodon
- Smart sampling of repositories with configurable filters
- Dry-run support to preview posts before publishing
- Rate limiting and posting frequency controls

### 🌐 **GitHub Pages Detection**
- Multi-method detection for Jekyll, MkDocs, Sphinx, and custom configurations
- Automatically build GitHub Pages URLs from repository metadata
- Track which repositories have active documentation sites

### 📄 **License Management**
- GitHub API integration for license template fetching
- Bulk license addition across multiple repositories
- Template customization with automatic placeholder replacement
- Support for all major open source licenses

### ⚙️ **Configuration Management**
- Support for both JSON and TOML configuration formats
- Environment variable overrides for all settings
- Intelligent merging of defaults, file settings, and overrides
- Built-in configuration template generation

### ⚡ **Performance & Quality**
- Fast operations with real-time progress indicators
- Configurable filtering and performance options
- Clean console output with detailed statistics
- Comprehensive error handling and logging

### 🔧 **Unix Philosophy & JSONL Output**
- All commands output newline-delimited JSON (JSONL) by default
- Stream-friendly format for processing millions of repos
- Compose with standard Unix tools (jq, grep, awk)
- Human-readable tables available with `--pretty` flag

## 🚀 Quick Start

```bash
# Install ghops
pip install ghops

# Generate configuration with examples
ghops config generate

# Clone all your repositories
ghops get

# Check status of all repositories (outputs JSONL)
ghops status -r

# Pretty-print status as a table
ghops status -r --pretty

# Filter repos with jq
ghops status | jq 'select(.status.uncommitted_changes == true)'

# Sample repositories for social media (dry run)
ghops social sample --size 3
ghops social post --dry-run
```

## Use Cases

### **Open Source Maintainers**
- Track all your projects in one place
- Automate social media promotion of releases
- Monitor PyPI package status across projects
- Keep licenses up to date

### **Development Teams**
- Synchronize repository updates across team members
- Track project health and activity
- Maintain consistent licensing and documentation

### **Individual Developers**
- Organize and monitor personal projects
- Automate promotion of your work
- Track your open source contributions

## Getting Started

1. **[Installation](usage.md#installation-and-setup)** - Install and configure ghops
2. **[Basic Usage](usage.md#core-commands)** - Learn the core commands
3. **[Configuration](usage.md#configuration-management)** - Set up your preferences
4. **[Advanced Features](usage.md#pypi-integration)** - Explore PyPI and social media features

## Documentation Sections

- **[Usage Guide](usage.md)** - Comprehensive command reference and examples
- **[Future Plans](future-plans.md)** - Roadmap and upcoming features
- **[Contributing](../contributing.md)** - How to contribute to the project

## Recent Updates

### Version 0.6.0 🎉

**Major Architecture & Quality Overhaul** - This release represents a complete transformation of `ghops` into a robust, enterprise-ready tool.

#### 🏗️ **Complete Architecture Redesign**

- ✅ **Modular Command Structure**: Separated all commands into dedicated modules (`ghops/commands/`)
- ✅ **Clean Separation of Concerns**: Utilities, configuration, and API integrations properly separated
- ✅ **Extensible Design**: Easy to add new commands and features without breaking existing functionality
- ✅ **Import Optimization**: Eliminated circular dependencies and improved startup time

#### 🧪 **Comprehensive Testing Framework**

- ✅ **138 Tests**: Complete test coverage for all functionality
- ✅ **86% Code Coverage**: Robust testing of edge cases and error conditions
- ✅ **Unit & Integration Tests**: Both isolated component testing and end-to-end workflows
- ✅ **Mock Testing**: Reliable testing of external API interactions
- ✅ **Error Condition Testing**: Comprehensive failure scenario coverage

#### ⚡ **Performance & Reliability Enhancements**

- ✅ **Optional API Checks**: `--no-pypi-check` and `--no-pages-check` for faster operations
- ✅ **Robust Error Handling**: Graceful handling of network failures and edge cases
- ✅ **Progress Indicators**: Real-time progress bars for long-running operations
- ✅ **Concurrent Operations**: Configurable parallel processing for better performance
- ✅ **JSONL Streaming**: Stream-friendly output for processing large repository sets
- ✅ **Unix Pipeline Integration**: Compose with jq, grep, and other standard tools

#### 📱 **Advanced Social Media Framework**

- ✅ **Template-Driven Content**: Customizable post templates for different content types
- ✅ **Multi-Platform Support**: Twitter, LinkedIn, and Mastodon integration
- ✅ **Smart Sampling**: Configurable repository filtering and random selection
- ✅ **Dry-Run Support**: Preview posts before publishing
- ✅ **Rate Limiting**: Built-in posting frequency controls and daily limits

#### ⚙️ **Enhanced Configuration System**

- ✅ **Multiple Formats**: Support for both JSON and TOML configuration files
- ✅ **Environment Overrides**: All settings controllable via environment variables
- ✅ **Intelligent Merging**: Proper precedence of defaults, files, and overrides
- ✅ **Example Generation**: `ghops config generate` creates comprehensive examples

#### 📄 **Robust License Management**

- ✅ **GitHub API Integration**: Direct fetching of license templates from GitHub
- ✅ **Template Customization**: Automatic placeholder replacement for author details
- ✅ **Bulk Operations**: Add licenses to multiple repositories efficiently
- ✅ **All Major Licenses**: Support for MIT, Apache, GPL, and many others

#### 🌐 **Enhanced GitHub Pages Detection**

- ✅ **Multi-Method Detection**: Scans for Jekyll, MkDocs, Sphinx, and custom configurations
- ✅ **URL Construction**: Automatically builds Pages URLs from repository metadata
- ✅ **Documentation Tracking**: Monitor which projects have active documentation

#### 📦 **Improved PyPI Integration**

- ✅ **Smart Package Detection**: Enhanced scanning of `pyproject.toml`, `setup.py`, `setup.cfg`
- ✅ **Version Comparison**: Track local vs published version differences
- ✅ **Performance Options**: Optional PyPI checking for faster status operations
- ✅ **Error Resilience**: Graceful handling of PyPI API issues

### Version 0.5.x (Legacy)

- ✅ **PyPI Integration**: Automatic detection and tracking of Python packages
- ✅ **Social Media Framework**: Generate and post content about your projects
- ✅ **Configuration System**: Flexible configuration with example generation
- ✅ **Performance Improvements**: Progress bars and faster operations
- ✅ **Enhanced Status**: Clean status reporting with PyPI and GitHub Pages info

## Community and Support

- **GitHub Repository**: [github.com/queelius/ghops](https://github.com/queelius/ghops)
- **Issues and Bug Reports**: [GitHub Issues](https://github.com/queelius/ghops/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/queelius/ghops/discussions)

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/queelius/ghops/blob/main/LICENSE) file for details.

---

Ready to streamline your GitHub workflow? [Get started with the installation guide](usage.md#installation-and-setup)!
