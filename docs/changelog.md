# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0] - 2025-06-27

### 🎉 Major Architecture Overhaul

#### ✨ Added
- **Modular Command Structure**: Complete refactoring into dedicated command modules (`commands/get.py`, `commands/update.py`, `commands/status.py`, `commands/license.py`)
- **Comprehensive Testing Suite**: 138 unit and integration tests achieving 86% code coverage
- **Enhanced License Management**: Full GitHub API integration for license templates with customization support
- **Advanced Configuration System**: Support for JSON/TOML formats with environment variable overrides
- **Social Media Automation Framework**: Template-driven content generation for Twitter, LinkedIn, and Mastodon
- **Robust Error Handling**: Graceful handling of network failures, API timeouts, and edge cases
- **Performance Optimizations**: Optional PyPI/Pages checks with `--no-pypi-check` and `--no-pages-check` flags
- **Progress Reporting**: Real-time progress bars and comprehensive operation summaries

#### 🔧 Improved
- **PyPI Detection**: Enhanced package detection from `pyproject.toml`, `setup.py`, and `setup.cfg` with fallback strategies
- **GitHub Pages Detection**: Multi-method detection supporting Jekyll, MkDocs, Sphinx, and custom configurations
- **Repository Updates**: Smart conflict resolution strategies and improved merge handling
- **CLI Interface**: Consistent argument handling and better help documentation
- **Configuration Management**: Intelligent config merging with defaults, file settings, and environment overrides

#### 🐛 Fixed
- **Import Errors**: Resolved circular dependencies and module loading issues
- **Global State Issues**: Eliminated shared state problems in concurrent operations  
- **API Error Handling**: Better handling of GitHub API rate limits and network failures
- **Version Comparison**: Fixed package version parsing and comparison logic
- **Path Handling**: Improved cross-platform path resolution and repository discovery

#### 📚 Documentation
- **Updated README**: Comprehensive feature overview with usage examples and configuration details
- **API Documentation**: Detailed command reference and configuration options
- **Contributing Guide**: Updated development workflow and testing procedures
- **Example Configurations**: Complete TOML/JSON configuration templates

#### 🧪 Testing & Quality
- **Unit Tests**: Comprehensive coverage of individual functions and methods
- **Integration Tests**: End-to-end CLI testing with mocked external dependencies
- **Error Scenario Testing**: Edge cases, network failures, and malformed data handling
- **Performance Testing**: Validation of concurrent operations and large repository sets
- **CI/CD Pipeline**: Automated testing and coverage reporting

### 🔄 Migration Guide

#### Breaking Changes
- Configuration file structure has been updated for better organization
- Some command line arguments have been renamed for consistency
- Social media configuration now requires explicit platform configuration

#### Migration Steps
1. Run `ghops config generate` to create an updated configuration file
2. Update any existing `.ghopsrc` files to match the new structure
3. Update scripts to use new command line argument names

## [0.5.x] - Previous Versions

### Legacy Features
- Basic repository cloning and updating
- Simple PyPI package detection
- Basic GitHub Pages detection
- Monolithic architecture

---

For detailed information about any release, see the [GitHub Releases](https://github.com/queelius/ghops/releases) page.

