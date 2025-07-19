# Audit Command

The `ghops audit` command provides comprehensive health checks for your repositories, identifying and optionally fixing common issues.

## Overview

The audit command checks repositories for:
- Missing or outdated licenses
- Missing README files
- Security vulnerabilities (hardcoded secrets)
- Dependency management issues
- Documentation setup problems
- Missing or incomplete .gitignore files

## Usage

```bash
ghops audit SUBCOMMAND [OPTIONS]
```

## Subcommands

### `ghops audit all`

Run all audit checks on repositories.

```bash
# Audit all repositories
ghops audit all --pretty

# Audit and fix issues
ghops audit all --fix

# Audit Python repositories only
ghops audit all -t "lang:python" --pretty

# Dry run to see what would be fixed
ghops audit all --fix --dry-run
```

### `ghops audit license`

Check for missing or problematic license files.

```bash
# Check all repos for licenses
ghops audit license --pretty

# Add MIT licenses to repos missing them
ghops audit license --fix --type MIT --author "Your Name"

# Audit specific repositories
ghops audit license -t "dir:work" --fix --type Apache-2.0
```

### `ghops audit security`

Scan for potential security issues like hardcoded secrets.

```bash
# Security scan all repos
ghops audit security --pretty

# Fix security issues (adds secrets to .gitignore)
ghops audit security --fix

# Scan specific repos
ghops audit security -q "language == 'python'"
```

### `ghops audit deps`

Check dependency management health.

```bash
# Check all repos
ghops audit deps --pretty

# Check JavaScript projects
ghops audit deps -q "has:package.json"

# Check Python projects
ghops audit deps -t "lang:python"
```

### `ghops audit docs`

Verify documentation setup and configuration.

```bash
# Check documentation health
ghops audit docs --pretty

# Fix missing documentation setup
ghops audit docs --fix

# Check repos that should have docs
ghops audit docs -q "file_count > 100"
```

## Common Options

- `--fix` - Automatically fix issues found
- `--dry-run` - Preview what would be fixed without making changes
- `-t, --tag TAG` - Filter repositories by tag
- `-q, --query EXPR` - Filter by query expression
- `--pretty` - Display as formatted table (default is JSONL)

## Output Format

By default, audit commands output JSONL for pipeline processing:

```bash
# Find all repos failing security audit
ghops audit security | jq 'select(.status == "fail")'

# Get summary of all audit failures
ghops audit all | jq 'select(.status == "fail") | {
  name: .name,
  failed_checks: [.checks | to_entries[] | select(.value.status == "fail") | .key]
}'

# Export audit results to CSV
ghops audit all | jq -r '
  [.name, .status, (.checks.license.status), (.checks.security.status)] | @csv
' > audit-results.csv
```

## Fix Capabilities

The `--fix` flag enables automatic remediation:

| Check | Fix Action |
|-------|------------|
| License | Adds license file with proper attribution |
| README | Creates basic README.md template |
| Security | Adds .env to .gitignore, creates .gitignore if missing |
| Docs | Adds MkDocs configuration for repos with docs/ directory |
| Gitignore | Creates comprehensive .gitignore for detected language |

## Examples

### Comprehensive Audit Report

```bash
# Generate full audit report for all repos
ghops audit all --pretty > audit-report.txt

# Get JSON summary
ghops audit all | jq -s '{
  total: length,
  passed: [.[] | select(.status == "pass")] | length,
  failed: [.[] | select(.status == "fail")] | length,
  fixed: [.[] | select(.status == "fixed")] | length
}'
```

### Targeted Fixes

```bash
# Fix all Python repos missing licenses
ghops audit license -t "lang:python" --fix --type MIT \
  --author "Your Name" --email "your@email.com"

# Add READMEs to all work projects
ghops audit readme -t "dir:work" --fix

# Secure all repos with potential issues
ghops audit security --fix
```

### Integration with CI/CD

```bash
# Fail CI if any audits fail
if ghops audit all | jq -e 'any(.status == "fail")'; then
  echo "Audit failed!"
  exit 1
fi
```