# Roadmap: From ghops to Digital Legacy Platform

## Current Status

ghops has evolved from a simple GitHub operations tool into a comprehensive repository and digital presence management system. This document outlines our vision and planned features.

## Core Philosophy

**Local-first with remote awareness**: Your local git repositories are the ground truth, and remote platforms (GitHub, GitLab, PyPI, social media) are services that enrich and distribute your work.

## Completed Features ✅

### Repository Management
- Multi-platform repository discovery (GitHub, GitLab, local)
- Deduplication by remote URL
- Rich metadata extraction (license, package info, GitHub stats)
- Powerful query language with fuzzy matching
- Hierarchical tagging system

### Package & Documentation
- PyPI package detection and publishing
- Bidirectional sync between tags and PyPI classifiers
- Hugo static site generation
- MkDocs integration
- Template-based content generation

### Automation & Intelligence
- Social media posting (Twitter/X, LinkedIn, Mastodon)
- Automatic language detection for .gitignore generation
- Service mode for background operations
- Smart tag extraction from PyPI classifiers

## Upcoming Features 🚀

### Phase 1: Enhanced Discovery & Organization (Q1 2024)
- [ ] Tag discovery/documentation command (`ghops catalog tags --list`)
- [ ] Bulk tag operations across multiple repos
- [ ] Enhanced query language with more operators
- [ ] Repository health scoring and recommendations

### Phase 2: Digital Presence Amplification (Q2 2024)
- [ ] Cross-posting to Dev.to, Medium, Hashnode
- [ ] SEO optimization for documentation
- [ ] Automatic portfolio/resume generation
- [ ] Citation and impact tracking
- [ ] Conference talk proposal generation

### Phase 3: Service & Integration Platform (Q3 2024)
- [ ] FastAPI service for web interface
- [ ] MCP (Model Context Protocol) integration
- [ ] Webhook support for CI/CD
- [ ] GraphQL API for advanced queries
- [ ] Plugin architecture for extensions

### Phase 4: Digital Legacy Management (Q4 2024)
- [ ] Deadman switch implementation
- [ ] Succession planning for repositories
- [ ] Archive strategies (active/archived/memorial)
- [ ] Project handoff documentation generation
- [ ] Legal compliance tools (license audit, GDPR)

## Potential Rename

As the project has grown beyond GitHub operations, we're considering a rename that better reflects its scope:

### Candidates:
- **repokeeper** - Emphasizes long-term repository stewardship
- **gitlife** - The complete lifecycle of your git repositories
- **devpresence** - Your development presence manager
- **codelegacy** - Focus on lasting impact

## Integration Opportunities

### Model Context Protocol (MCP)
- Expose repository metadata to AI assistants
- Enable natural language queries
- Automated code documentation generation

### FastAPI Service
- Web dashboard for repository management
- REST API for third-party integrations
- Real-time notifications and monitoring
- Public portfolio hosting

### Platform Integrations
- **Git Platforms**: GitHub, GitLab, Bitbucket, Gitea
- **Package Registries**: PyPI, npm, crates.io, RubyGems
- **Documentation**: Read the Docs, GitHub Pages, Netlify
- **Social**: Twitter/X, LinkedIn, Mastodon, Bluesky
- **Academic**: ORCID, Google Scholar, arXiv

## Feature Governance

To prevent feature creep, all new features must:
1. Support the core mission of repository lifecycle management
2. Integrate cleanly with existing features
3. Be automatable and scriptable
4. Respect the local-first philosophy
5. Have clear use cases from real users

## Configuration Example

```yaml
# Future ~/.ghops/config.yaml structure
general:
  service_mode: daemon
  api_port: 8080

repositories:
  scan_directories:
    - ~/github
    - ~/work
  auto_tag: true
  health_checks: daily

presence:
  social_media:
    auto_post: true
    platforms: [twitter, linkedin, mastodon]
  portfolio:
    generate: true
    host: github-pages

legacy:
  deadman_switch:
    enabled: true
    inactivity_days: 180
  succession:
    default_inheritor: "@open-source-foundation"
  archives:
    - provider: archive.org
    - provider: software-heritage

integrations:
  mcp:
    enabled: true
    port: 8081
  webhooks:
    - url: https://ci.example.com/hook
      events: [push, tag, release]
```

## Contributing

We welcome contributions! Priority areas:
1. Platform integrations (GitLab, Bitbucket)
2. Package registry support beyond PyPI
3. Documentation improvements
4. Query language enhancements
5. Social media platform adapters

## Questions for Community

1. Should we rename the project? What name best captures its mission?
2. Which features would provide the most immediate value?
3. Should legacy management be a separate project or integrated?
4. What integrations would you find most useful?

## Timeline

- **2024 Q1**: Complete Phase 1, gather feedback on rename
- **2024 Q2**: Launch presence features, beta web interface
- **2024 Q3**: Full service platform with API
- **2024 Q4**: Digital legacy features, 1.0 release

---

*This roadmap is a living document. Features and timelines may change based on community feedback and contributions.*