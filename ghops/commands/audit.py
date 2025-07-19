"""
Audit command for checking and fixing repository health issues.

This command follows our design principles:
- Default output is JSONL streaming
- --pretty flag for human-readable table output
- Core logic returns generators for streaming
- No side effects in core functions
"""

import click
import json
import os
from pathlib import Path
from typing import Generator, Dict, Any, List, Optional
from datetime import datetime

from ..config import logger, load_config
from ..repo_filter import get_filtered_repos, add_common_repo_options
from ..metadata import get_metadata_store
from ..render import render_table
from ..core import get_license_template


def audit_license(repo_path: str, fix: bool = False, license_type: str = None,
                  author: str = None, email: str = None, year: str = None,
                  force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository's license status.
    
    Returns audit results following standard schema.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "license",
        "status": "pass",  # pass, fail, fixed, error
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        
        # Check for existing license files
        license_files = []
        for pattern in ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENCE', 'LICENCE.txt', 'LICENCE.md']:
            matches = list(repo_path_obj.glob(pattern))
            license_files.extend(matches)
        
        if not license_files:
            result["status"] = "fail"
            result["issues"].append("No LICENSE file found")
            result["details"]["has_license"] = False
            
            if fix and license_type:
                # Apply fix
                if not dry_run:
                    # Get license template
                    template_info = get_license_template(license_type)
                    if template_info and "body" in template_info:
                        template = template_info["body"]
                        
                        # Replace placeholders
                        if author:
                            template = template.replace("[fullname]", author)
                            template = template.replace("[name]", author)
                        if email:
                            template = template.replace("[email]", email)
                        if year:
                            template = template.replace("[year]", year)
                        else:
                            template = template.replace("[year]", str(datetime.now().year))
                        
                        # Write license file
                        license_path = repo_path_obj / "LICENSE"
                        license_path.write_text(template)
                        
                        result["status"] = "fixed"
                        result["fixes"].append(f"Added {license_type} LICENSE file")
                        result["details"]["license_type"] = license_type
                        result["details"]["license_file"] = str(license_path)
                    else:
                        result["status"] = "error"
                        result["details"]["error"] = f"Failed to get template for {license_type}"
                else:
                    result["status"] = "fixed"
                    result["fixes"].append(f"[DRY RUN] Would add {license_type} LICENSE file")
                    result["details"]["license_type"] = license_type
        else:
            # License exists
            result["details"]["has_license"] = True
            result["details"]["license_files"] = [str(f.relative_to(repo_path_obj)) for f in license_files]
            
            # TODO: Could check license content, year, etc.
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_readme(repo_path: str, fix: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository's README status.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "readme",
        "status": "pass",
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        
        # Check for README files
        readme_files = []
        for pattern in ['README.md', 'README.txt', 'README.rst', 'README', 'readme.md']:
            matches = list(repo_path_obj.glob(pattern))
            readme_files.extend(matches)
        
        if not readme_files:
            result["status"] = "fail"
            result["issues"].append("No README file found")
            result["details"]["has_readme"] = False
            
            if fix:
                # Create basic README
                if not dry_run:
                    readme_content = f"""# {repo_name}

## Description

TODO: Add project description

## Installation

TODO: Add installation instructions

## Usage

TODO: Add usage examples

## License

See LICENSE file for details.
"""
                    readme_path = repo_path_obj / "README.md"
                    readme_path.write_text(readme_content)
                    
                    result["status"] = "fixed"
                    result["fixes"].append("Added basic README.md")
                    result["details"]["readme_file"] = str(readme_path)
                else:
                    result["status"] = "fixed"
                    result["fixes"].append("[DRY RUN] Would add basic README.md")
        else:
            result["details"]["has_readme"] = True
            result["details"]["readme_files"] = [str(f.relative_to(repo_path_obj)) for f in readme_files]
            
            # TODO: Could check README content quality
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_security(repo_path: str, fix: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository for security issues.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "security",
        "status": "pass",
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        
        # Check for common secret patterns in files
        secret_patterns = [
            (r'(?i)api[_-]?key\s*=\s*["\']?[a-zA-Z0-9]{20,}', 'API key'),
            (r'(?i)secret[_-]?key\s*=\s*["\']?[a-zA-Z0-9]{20,}', 'Secret key'),
            (r'(?i)password\s*=\s*["\']?[^\s"\']{8,}', 'Hardcoded password'),
            (r'(?i)token\s*=\s*["\']?[a-zA-Z0-9]{20,}', 'Token'),
            (r'[a-zA-Z0-9+/]{40,}={0,2}', 'Base64 encoded secret'),
        ]
        
        # Files to check
        check_files = ['.env', 'config.py', 'settings.py', 'config.json', 'settings.json']
        found_secrets = []
        
        import re
        for file_name in check_files:
            file_path = repo_path_obj / file_name
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_text()
                    for pattern, secret_type in secret_patterns:
                        if re.search(pattern, content):
                            found_secrets.append(f"{secret_type} in {file_name}")
                            result["status"] = "fail"
                            result["issues"].append(f"Potential {secret_type} found in {file_name}")
                except Exception:
                    pass
        
        # Check if .env is in .gitignore
        gitignore_path = repo_path_obj / ".gitignore"
        env_path = repo_path_obj / ".env"
        
        if env_path.exists():
            if not gitignore_path.exists():
                result["status"] = "fail"
                result["issues"].append(".env file exists but no .gitignore")
                
                if fix:
                    if not dry_run:
                        gitignore_path.write_text(".env\n")
                        result["status"] = "fixed"
                        result["fixes"].append("Created .gitignore with .env entry")
                    else:
                        result["status"] = "fixed"
                        result["fixes"].append("[DRY RUN] Would create .gitignore with .env entry")
            else:
                gitignore_content = gitignore_path.read_text()
                if ".env" not in gitignore_content:
                    result["status"] = "fail"
                    result["issues"].append(".env file not in .gitignore")
                    
                    if fix:
                        if not dry_run:
                            with gitignore_path.open('a') as f:
                                f.write("\n.env\n")
                            result["status"] = "fixed"
                            result["fixes"].append("Added .env to .gitignore")
                        else:
                            result["status"] = "fixed"
                            result["fixes"].append("[DRY RUN] Would add .env to .gitignore")
        
        result["details"]["secrets_found"] = len(found_secrets)
        result["details"]["secret_locations"] = found_secrets[:5]  # Limit details
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_deps(repo_path: str, fix: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository's dependencies.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "dependencies",
        "status": "pass",
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        
        # Check Python dependencies
        requirements_files = ['requirements.txt', 'requirements-dev.txt', 'requirements.in']
        pyproject_path = repo_path_obj / "pyproject.toml"
        pipfile_path = repo_path_obj / "Pipfile"
        
        has_deps = False
        outdated_deps = []
        
        # Check for dependency files
        for req_file in requirements_files:
            req_path = repo_path_obj / req_file
            if req_path.exists():
                has_deps = True
                result["details"]["dependency_files"] = result["details"].get("dependency_files", [])
                result["details"]["dependency_files"].append(req_file)
        
        if pyproject_path.exists():
            has_deps = True
            result["details"]["dependency_files"] = result["details"].get("dependency_files", [])
            result["details"]["dependency_files"].append("pyproject.toml")
        
        if pipfile_path.exists():
            has_deps = True
            result["details"]["dependency_files"] = result["details"].get("dependency_files", [])
            result["details"]["dependency_files"].append("Pipfile")
        
        # Check package.json for JavaScript projects
        package_json_path = repo_path_obj / "package.json"
        if package_json_path.exists():
            has_deps = True
            result["details"]["dependency_files"] = result["details"].get("dependency_files", [])
            result["details"]["dependency_files"].append("package.json")
            
            # Check for package-lock.json
            if not (repo_path_obj / "package-lock.json").exists() and not (repo_path_obj / "yarn.lock").exists():
                result["status"] = "fail"
                result["issues"].append("No lock file (package-lock.json or yarn.lock)")
        
        # TODO: Actually check for outdated dependencies
        # This would require running pip-compile, npm audit, etc.
        
        if not has_deps:
            # Check if this is a code project that should have deps
            py_files = list(repo_path_obj.glob("**/*.py"))
            js_files = list(repo_path_obj.glob("**/*.js"))
            
            if len(py_files) > 2:  # More than just __init__.py
                result["status"] = "fail"
                result["issues"].append("Python project without dependency management")
            elif len(js_files) > 2:
                result["status"] = "fail"
                result["issues"].append("JavaScript project without package.json")
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_docs(repo_path: str, fix: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository's documentation.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "documentation",
        "status": "pass",
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        
        # Check for documentation
        from ..commands.docs import detect_docs_tool
        docs_info = detect_docs_tool(str(repo_path_obj))
        
        if docs_info:
            result["details"]["has_docs"] = True
            result["details"]["docs_tool"] = docs_info["tool"]
            result["details"]["docs_config"] = docs_info.get("config")
        else:
            # Check if there's a docs directory without tooling
            docs_dirs = ['docs', 'documentation', 'doc']
            has_docs_dir = False
            
            for docs_dir in docs_dirs:
                if (repo_path_obj / docs_dir).exists():
                    has_docs_dir = True
                    result["details"]["docs_directory"] = docs_dir
                    break
            
            if has_docs_dir:
                result["status"] = "fail"
                result["issues"].append("Documentation directory exists but no documentation tool configured")
                
                if fix:
                    # Create basic mkdocs.yml
                    if not dry_run:
                        mkdocs_config = f"""site_name: {repo_name}
site_description: Documentation for {repo_name}
nav:
  - Home: index.md
theme:
  name: material
"""
                        mkdocs_path = repo_path_obj / "mkdocs.yml"
                        mkdocs_path.write_text(mkdocs_config)
                        
                        # Create index.md if it doesn't exist
                        docs_index = repo_path_obj / result["details"]["docs_directory"] / "index.md"
                        if not docs_index.exists():
                            docs_index.parent.mkdir(exist_ok=True)
                            docs_index.write_text(f"# {repo_name}\n\nWelcome to the documentation.")
                        
                        result["status"] = "fixed"
                        result["fixes"].append("Added MkDocs configuration")
                    else:
                        result["status"] = "fixed"
                        result["fixes"].append("[DRY RUN] Would add MkDocs configuration")
            else:
                # No docs at all
                code_files = list(repo_path_obj.glob("**/*.py")) + list(repo_path_obj.glob("**/*.js"))
                if len(code_files) > 5:  # Non-trivial project
                    result["status"] = "fail"
                    result["issues"].append("No documentation found for code project")
        
        # Check for API documentation
        if result["details"].get("docs_tool") == "mkdocs":
            mkdocs_config_path = repo_path_obj / (docs_info.get("config") or "mkdocs.yml")
            if mkdocs_config_path.exists():
                config_content = mkdocs_config_path.read_text()
                if "mkdocstrings" not in config_content and len(list(repo_path_obj.glob("**/*.py"))) > 5:
                    result["issues"].append("Python project without API documentation plugin")
                    if result["status"] == "pass":
                        result["status"] = "fail"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_gitignore(repo_path: str, fix: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Audit a repository's .gitignore status.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "gitignore",
        "status": "pass",
        "issues": [],
        "fixes": [],
        "details": {}
    }
    
    try:
        repo_path_obj = Path(repo_path)
        gitignore_path = repo_path_obj / ".gitignore"
        
        if not gitignore_path.exists():
            result["status"] = "fail"
            result["issues"].append("No .gitignore file found")
            result["details"]["has_gitignore"] = False
            
            if fix:
                # TODO: Detect language and add appropriate .gitignore
                if not dry_run:
                    # Basic .gitignore
                    gitignore_content = """# OS files
.DS_Store
Thumbs.db

# Editor files
.vscode/
.idea/
*.swp
*.swo
*~

# Dependencies
node_modules/
venv/
env/
__pycache__/
*.pyc

# Build artifacts
dist/
build/
*.egg-info/

# Logs
*.log

# Environment files
.env
.env.local
"""
                    gitignore_path.write_text(gitignore_content)
                    
                    result["status"] = "fixed"
                    result["fixes"].append("Added basic .gitignore")
                else:
                    result["status"] = "fixed"
                    result["fixes"].append("[DRY RUN] Would add basic .gitignore")
        else:
            result["details"]["has_gitignore"] = True
            
            # TODO: Could check .gitignore quality
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["details"]["error_type"] = type(e).__name__
        
    return result


def audit_all(repo_path: str, fix: bool = False, license_type: str = None,
              author: str = None, email: str = None, year: str = None,
              force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Run all audits on a repository.
    """
    repo_name = os.path.basename(repo_path)
    result = {
        "path": os.path.abspath(repo_path),
        "name": repo_name,
        "check": "all",
        "status": "pass",  # Will be fail if any check fails
        "checks": {}
    }
    
    # Run individual audits
    checks = {
        "license": audit_license(repo_path, fix, license_type, author, email, year, force, dry_run),
        "readme": audit_readme(repo_path, fix, dry_run),
        "gitignore": audit_gitignore(repo_path, fix, dry_run),
        "security": audit_security(repo_path, fix, dry_run),
        "dependencies": audit_deps(repo_path, fix, dry_run),
        "documentation": audit_docs(repo_path, fix, dry_run)
    }
    
    # Aggregate status
    statuses = [check["status"] for check in checks.values()]
    if "error" in statuses:
        result["status"] = "error"
    elif "fail" in statuses:
        result["status"] = "fail"
    elif "fixed" in statuses:
        result["status"] = "fixed"
    
    result["checks"] = checks
    
    # Summary counts
    result["summary"] = {
        "total_checks": len(checks),
        "passed": sum(1 for c in checks.values() if c["status"] == "pass"),
        "failed": sum(1 for c in checks.values() if c["status"] == "fail"),
        "fixed": sum(1 for c in checks.values() if c["status"] == "fixed"),
        "errors": sum(1 for c in checks.values() if c["status"] == "error")
    }
    
    return result


def audit_repositories(check_type: str = "all", repos: List[str] = None,
                      fix: bool = False, license_type: str = None,
                      author: str = None, email: str = None, year: str = None,
                      force: bool = False, dry_run: bool = False) -> Generator[Dict[str, Any], None, None]:
    """
    Generator that yields audit results for repositories.
    """
    if repos is None:
        repos = []
    
    for repo_path in repos:
        if check_type == "all":
            yield audit_all(repo_path, fix, license_type, author, email, year, force, dry_run)
        elif check_type == "license":
            yield audit_license(repo_path, fix, license_type, author, email, year, force, dry_run)
        elif check_type == "readme":
            yield audit_readme(repo_path, fix, dry_run)
        elif check_type == "gitignore":
            yield audit_gitignore(repo_path, fix, dry_run)
        elif check_type == "security":
            yield audit_security(repo_path, fix, dry_run)
        elif check_type == "dependencies":
            yield audit_deps(repo_path, fix, dry_run)
        elif check_type == "documentation":
            yield audit_docs(repo_path, fix, dry_run)


@click.group("audit")
def audit_cmd():
    """Audit repositories for health and compliance issues."""
    pass


@audit_cmd.command("license")
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--type", "license_type", help="License type (e.g., MIT, Apache-2.0)")
@click.option("--author", help="Author name for license")
@click.option("--email", help="Author email for license")
@click.option("--year", help="Copyright year")
@click.option("--force", is_flag=True, help="Overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
def audit_license_handler(dir, recursive, tag_filters, all_tags, query,
                         fix, license_type, author, email, year, force, dry_run, pretty):
    """Audit repository licenses."""
    config = load_config()
    
    # Get author/email from config if not provided
    if fix and not author:
        author = config.get("general", {}).get("git_user_name")
    if fix and not email:
        email = config.get("general", {}).get("git_user_email")
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="license",
        repos=repos,
        fix=fix,
        license_type=license_type,
        author=author,
        email=email,
        year=year,
        force=force,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Prepare table data
        headers = ["Repository", "Status", "Issues", "Fixes"]
        rows = []
        
        for result in results:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "fixed": "🔧",
                "error": "⚠️"
            }.get(result["status"], "?")
            
            issues = ", ".join(result.get("issues", []))
            fixes = ", ".join(result.get("fixes", []))
            
            rows.append([
                result["name"],
                f"{status_icon} {result['status']}",
                issues or "-",
                fixes or "-"
            ])
        
        render_table(headers, rows, title="License Audit Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)


@audit_cmd.command("readme")
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
def audit_readme_handler(dir, recursive, tag_filters, all_tags, query,
                        fix, dry_run, pretty):
    """Audit repository READMEs."""
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="readme",
        repos=repos,
        fix=fix,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Prepare table data
        headers = ["Repository", "Status", "Issues", "Fixes"]
        rows = []
        
        for result in results:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "fixed": "🔧",
                "error": "⚠️"
            }.get(result["status"], "?")
            
            issues = ", ".join(result.get("issues", []))
            fixes = ", ".join(result.get("fixes", []))
            
            rows.append([
                result["name"],
                f"{status_icon} {result['status']}",
                issues or "-",
                fixes or "-"
            ])
        
        render_table(headers, rows, title="README Audit Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)


@audit_cmd.command()
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--license-type", help="License type for fixes (e.g., MIT)")
@click.option("--author", help="Author name for license")
@click.option("--email", help="Author email for license")
@click.option("--year", help="Copyright year")
@click.option("--force", is_flag=True, help="Overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
@click.pass_context
def all(ctx, dir, recursive, tag_filters, all_tags, query,
        fix, license_type, author, email, year, force, dry_run, pretty):
    """Run all audits on repositories."""
    config = load_config()
    
    # Get author/email from config if not provided
    if fix and not author:
        author = config.get("general", {}).get("git_user_name")
    if fix and not email:
        email = config.get("general", {}).get("git_user_email")
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="all",
        repos=repos,
        fix=fix,
        license_type=license_type,
        author=author,
        email=email,
        year=year,
        force=force,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Summary table
        total_repos = len(results)
        total_passed = sum(1 for r in results if r["status"] == "pass")
        total_failed = sum(1 for r in results if r["status"] == "fail")
        total_fixed = sum(1 for r in results if r["status"] == "fixed")
        total_errors = sum(1 for r in results if r["status"] == "error")
        
        print(f"\n📊 Audit Summary: {total_repos} repositories")
        print(f"   ✓ Passed: {total_passed}")
        print(f"   ✗ Failed: {total_failed}")
        print(f"   🔧 Fixed: {total_fixed}")
        print(f"   ⚠️  Errors: {total_errors}")
        
        # Detailed table
        headers = ["Repository", "License", "README", "Gitignore", "Security", "Deps", "Docs", "Overall"]
        rows = []
        
        for result in results:
            checks = result.get("checks", {})
            
            def format_status(status):
                return {
                    "pass": "✓",
                    "fail": "✗",
                    "fixed": "🔧",
                    "error": "⚠️"
                }.get(status, "?")
            
            rows.append([
                result["name"],
                format_status(checks.get("license", {}).get("status", "-")),
                format_status(checks.get("readme", {}).get("status", "-")),
                format_status(checks.get("gitignore", {}).get("status", "-")),
                format_status(checks.get("security", {}).get("status", "-")),
                format_status(checks.get("dependencies", {}).get("status", "-")),
                format_status(checks.get("documentation", {}).get("status", "-")),
                format_status(result["status"])
            ])
        
        render_table(headers, rows, title="\nDetailed Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)


@audit_cmd.command("security")
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
def audit_security_handler(dir, recursive, tag_filters, all_tags, query,
                          fix, dry_run, pretty):
    """Audit repositories for security issues."""
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="security",
        repos=repos,
        fix=fix,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Prepare table data
        headers = ["Repository", "Status", "Issues", "Fixes"]
        rows = []
        
        for result in results:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "fixed": "🔧",
                "error": "⚠️"
            }.get(result["status"], "?")
            
            issues = ", ".join(result.get("issues", []))
            fixes = ", ".join(result.get("fixes", []))
            
            rows.append([
                result["name"],
                f"{status_icon} {result['status']}",
                issues or "-",
                fixes or "-"
            ])
        
        render_table(headers, rows, title="Security Audit Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)


@audit_cmd.command("deps")
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
def audit_deps_handler(dir, recursive, tag_filters, all_tags, query,
                      fix, dry_run, pretty):
    """Audit repository dependencies."""
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="dependencies",
        repos=repos,
        fix=fix,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Prepare table data
        headers = ["Repository", "Status", "Issues", "Dependency Files"]
        rows = []
        
        for result in results:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "fixed": "🔧",
                "error": "⚠️"
            }.get(result["status"], "?")
            
            issues = ", ".join(result.get("issues", []))
            dep_files = ", ".join(result.get("details", {}).get("dependency_files", []))
            
            rows.append([
                result["name"],
                f"{status_icon} {result['status']}",
                issues or "-",
                dep_files or "-"
            ])
        
        render_table(headers, rows, title="Dependency Audit Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)


@audit_cmd.command("docs")
@add_common_repo_options
@click.option("--fix", is_flag=True, help="Fix issues found")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--pretty", is_flag=True, help="Display as formatted table")
def audit_docs_handler(dir, recursive, tag_filters, all_tags, query,
                      fix, dry_run, pretty):
    """Audit repository documentation."""
    config = load_config()
    
    # Get filtered repositories
    repos, filter_desc = get_filtered_repos(
        dir=dir,
        recursive=recursive,
        tag_filters=tag_filters,
        all_tags=all_tags,
        query=query,
        config=config
    )
    
    if not repos:
        error_msg = f"No repositories found"
        if filter_desc:
            error_msg += f" matching {filter_desc}"
        logger.error(error_msg)
        return
    
    # Run audits
    audits = audit_repositories(
        check_type="documentation",
        repos=repos,
        fix=fix,
        dry_run=dry_run
    )
    
    if pretty:
        # Collect and render as table
        results = list(audits)
        
        # Prepare table data
        headers = ["Repository", "Status", "Issues", "Docs Tool"]
        rows = []
        
        for result in results:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "fixed": "🔧",
                "error": "⚠️"
            }.get(result["status"], "?")
            
            issues = ", ".join(result.get("issues", []))
            docs_tool = result.get("details", {}).get("docs_tool", "-")
            
            rows.append([
                result["name"],
                f"{status_icon} {result['status']}",
                issues or "-",
                docs_tool
            ])
        
        render_table(headers, rows, title="Documentation Audit Results")
    else:
        # Stream JSONL output
        for audit in audits:
            print(json.dumps(audit, ensure_ascii=False), flush=True)