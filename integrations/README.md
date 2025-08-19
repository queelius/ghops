# Integrations

This directory contains integration modules for connecting ghops with external services and protocols.

## Available Integrations

### MCP (Model Context Protocol)
Status: Planned
- Expose repository metadata to AI assistants
- Enable natural language repository queries
- Automated documentation generation
- Automatically update repository metadata
- Fix up commit message history
- Generate pull request summaries
- Fix Pull Request titles and descriptions
- Generate release notes
- Generate changelogs
- Generate code summaries
- Generate code documentation
- Generate code examples
- Generate code tests
- Generate code benchmarks

### FastAPI Service
Status: Planned
- Web dashboard for repository management
- REST API endpoints
- WebSocket support for real-time updates
- OAuth integration for social platforms

### Webhooks
Status: Planned
- GitHub webhooks for real-time updates
- CI/CD integration
- Custom event handlers

## Integration Architecture

Each integration should:
1. Be self-contained in its own subdirectory
2. Include its own requirements.txt if needed
3. Provide a clear interface to core ghops functionality
4. Include comprehensive tests
5. Document its configuration options

## Example Structure

```
integrations/
├── mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── handlers.py
│   ├── requirements.txt
│   └── README.md
├── fastapi/
│   ├── __init__.py
│   ├── app.py
│   ├── routes/
│   ├── models/
│   ├── requirements.txt
│   └── README.md
└── webhooks/
    ├── __init__.py
    ├── handlers.py
    ├── validators.py
    └── README.md
```

## Contributing

When adding a new integration:
1. Create a new subdirectory
2. Include a README with setup instructions
3. Add integration tests
4. Update this README
5. Add configuration examples to main docs