# TODO List

*Last updated: August 2025*

## Immediate / High Priority

### Bugs & Issues
- [ ] Fix remaining test failures (currently ~93% passing)
- [ ] Error handling for missing GitHub repos (getting GraphQL errors)
- [ ] Status command doesn't show tags properly yet

### Core Missing Features
- [ ] Tag discovery command (`ghops catalog tags --list` to see all available tags)
- [ ] GitLab support (currently GitHub-only for remote operations)
- [ ] Bitbucket support

## The Big Vision: Digital Legacy Platform

### Deadman Switch & Legacy Management
- [ ] Inactivity detection (no commits/activity for X days)
- [ ] Verification system (email/SMS to confirm you're alive)
- [ ] Succession planning (transfer ownership to designated people)
- [ ] Archive strategies (memorial mode, read-only archive, etc.)
- [ ] Auto-generate handoff documentation

### Presence Amplification
- [ ] Cross-posting to Dev.to, Medium, Hashnode
- [ ] Portfolio website generation
- [ ] Citation tracking (who's using your code)
- [ ] Impact metrics dashboard
- [ ] Conference talk proposal generator from README

### Service Architecture
- [ ] FastAPI web service (currently CLI only)
- [ ] MCP (Model Context Protocol) integration for AI assistants
- [ ] Webhook support for real-time updates
- [ ] Always-on daemon mode improvements
- [ ] Web dashboard UI

## Medium Priority

### Query Engine Enhancements
- [ ] Query history/saved queries
- [ ] Query builder UI
- [ ] More query operators
- [ ] Query performance optimization for large datasets

### Integrations
- [ ] npm registry support (currently PyPI only)
- [ ] crates.io for Rust packages
- [ ] Archive.org auto-backup
- [ ] Software Heritage preservation
- [ ] ORCID for academic presence

### Automation
- [ ] Scheduled social media posts
- [ ] Auto-update dependencies with PRs
- [ ] Release automation with changelogs
- [ ] Documentation auto-generation from code

## Low Priority / Future

### Architecture Changes
- [ ] Fluent API design (currently in TODO list)
- [ ] Plugin system for extensions
- [ ] GraphQL API alongside REST
- [ ] Optional database backend (currently file-based)

### Nice-to-Have Features
- [ ] Repository health scoring algorithm
- [ ] AI-powered README improvements
- [ ] License compatibility checker
- [ ] Dependency vulnerability scanning
- [ ] Generate CITATION.cff files

## Rename Consideration

Current name "ghops" no longer fits the scope. Candidates:
- [ ] **repokeeper** - Repository lifecycle management
- [ ] **gitlife** - Git repository lifecycle
- [ ] **devlegacy** - Developer legacy management
- [ ] **codepresence** - Code presence manager

Decision needed before 1.0 release.

## From Code TODOs

### audit.py
- [ ] Add project description detection in README
- [ ] Add installation instructions checker
- [ ] Add usage examples validator  
- [ ] Check .gitignore quality

## Completed Recently ✅
- [x] Hierarchical tagging with wildcards
- [x] PyPI classifier extraction and auto-tagging
- [x] Bidirectional sync (tags ↔ PyPI)
- [x] Social media posting (Twitter, LinkedIn, Mastodon)
- [x] Template engine with Jinja2
- [x] Hugo export with templates
- [x] Language detection for .gitignore
- [x] Query language with fuzzy matching
- [x] Repository deduplication

## Development Tracker

### In Progress / Session TODOs
These are being actively tracked during development sessions:

**Completed This Session:**
- ✅ Hierarchical tagging support  
- ✅ PyPI classifier extraction
- ✅ Bidirectional sync (tags ↔ PyPI)
- ✅ Hierarchical query support with wildcards
- ✅ Maturity/status tagging from PyPI

**Pending from Session:**
- 🔄 Tag discovery/documentation command
- 🔄 Manual tag overrides (with sync considerations)
- 🔄 Fix remaining test failures
- 🔄 Rename project decision

**New Vision Items Added:**
- 🎯 Deadman switch implementation (HIGH)
- 🎯 FastAPI web service (HIGH)
- 🎯 MCP integration (MEDIUM)
- 🎯 Cross-posting to Dev.to, Medium
- 🎯 GitLab/Bitbucket support

## Questions for Users

1. **Rename?** Should we rename from ghops? To what?
2. **Priority?** What feature would help you most right now?
3. **Scope?** Should legacy features be separate or integrated?
4. **Platforms?** Which git platforms do you use besides GitHub?

---

*Note: This project has evolved significantly from a simple GitHub operations tool to a comprehensive repository and digital presence manager. We're at a crossroads where we need to decide whether to embrace this larger vision or split into focused tools.*