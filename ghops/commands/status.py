"""
Handles the 'status' command for displaying repository status.
"""
#!/usr/bin/env python3

import os
import json
import random
from pathlib import Path
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from ..config import console, logger, stats, config
from ..utils import find_git_repos, get_git_status, run_command
from ..pypi import detect_pypi_package, is_package_outdated

def get_gh_pages_url(repo_path):
    """
    Get the GitHub Pages URL for a repository.
    """
    try:
        # Get the remote URL
        remote_url = run_command("git remote get-url origin", repo_path, capture_output=True, check=False, log_stderr=False)
        if not remote_url:
            return None
        
        remote_url = remote_url.strip()
        
        # Parse the remote URL to get owner and repo name
        if remote_url.startswith("https://github.com/"):
            parts = remote_url.replace("https://github.com/", "").replace(".git", "").split("/")
        elif remote_url.startswith("git@github.com:"):
            parts = remote_url.replace("git@github.com:", "").replace(".git", "").split("/")
        else:
            return None
        
        if len(parts) != 2:
            return None
        
        owner, repo = parts
        
        # Try multiple methods to detect GitHub Pages
        
        # Method 1: Use GitHub CLI if available
        try:
            pages_result = run_command(f"gh api repos/{owner}/{repo}/pages", repo_path, capture_output=True, check=False, log_stderr=False)
            if pages_result:
                pages_data = json.loads(pages_result)
                return pages_data.get("html_url")
        except (json.JSONDecodeError, Exception):
            pass
        
        # Method 2: Check for gh-pages branch
        try:
            branches_result = run_command("git branch -r", repo_path, capture_output=True, check=False, log_stderr=False)
            if branches_result and "origin/gh-pages" in branches_result:
                return f"https://{owner}.github.io/{repo}/"
        except Exception:
            pass
        
        # Method 3: Check for docs folder in main branch (GitHub Pages can serve from /docs)
        docs_path = Path(repo_path) / "docs"
        if docs_path.exists() and docs_path.is_dir():
            # Check if there's an index.html or index.md in docs
            if (docs_path / "index.html").exists() or (docs_path / "index.md").exists():
                return f"https://{owner}.github.io/{repo}/"
        
        # Method 4: Check for GitHub Pages configuration files
        github_pages_files = [
            "_config.yml",  # Jekyll
            "mkdocs.yml",   # MkDocs
            "conf.py",      # Sphinx (usually in docs/)
            "book.toml",    # mdBook
        ]
        
        for pages_file in github_pages_files:
            if (Path(repo_path) / pages_file).exists():
                return f"https://{owner}.github.io/{repo}/"
            # Also check in docs/ subdirectory
            if (Path(repo_path) / "docs" / pages_file).exists():
                return f"https://{owner}.github.io/{repo}/"
        
        # Method 5: Check for common static site generators
        static_indicators = [
            "package.json",  # Could be a Node.js static site
            "gatsby-config.js",  # Gatsby
            "next.config.js",    # Next.js
            "nuxt.config.js",    # Nuxt.js
            "vuepress.config.js", # VuePress
        ]
        
        for indicator in static_indicators:
            if (Path(repo_path) / indicator).exists():
                # Check package.json for static site scripts
                if indicator == "package.json":
                    try:
                        with open(Path(repo_path) / "package.json", 'r') as f:
                            package_data = json.loads(f.read())
                            scripts = package_data.get("scripts", {})
                            # Look for common static site build/deploy scripts
                            static_scripts = ["build", "deploy", "gh-pages", "pages"]
                            if any(script in scripts for script in static_scripts):
                                return f"https://{owner}.github.io/{repo}/"
                    except:
                        pass
                else:
                    return f"https://{owner}.github.io/{repo}/"
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting GitHub Pages URL for {repo_path}: {e}")
        return None

def get_license_info(repo_path):
    """
    Get license information for a repository.
    """
    repo_path = Path(repo_path)
    
    # Check for common license file names
    license_files = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENCE', 'LICENCE.txt', 'LICENCE.md']
    
    for license_file in license_files:
        license_path = repo_path / license_file
        if license_path.exists():
            try:
                with open(license_path, 'r', encoding='utf-8') as f:
                    content = f.read().upper()
                
                # Simple license detection based on content
                if 'MIT LICENSE' in content or 'MIT' in content:
                    return 'MIT'
                elif 'APACHE LICENSE' in content or 'APACHE' in content:
                    return 'Apache-2.0'
                elif 'GNU GENERAL PUBLIC LICENSE' in content or 'GPL' in content:
                    if 'VERSION 3' in content:
                        return 'GPL-3.0'
                    elif 'VERSION 2' in content:
                        return 'GPL-2.0'
                    else:
                        return 'GPL'
                elif 'BSD' in content:
                    return 'BSD'
                else:
                    return 'Other'
            except:
                return 'Unknown'
    
    return 'None'

def display_repo_status_table(repo_dirs, json_output=False, base_dir=".", skip_pages_check=False):
    """
    Display the status of repositories in a table format with progress bar.
    """
    if not repo_dirs:
        if json_output:
            console.print_json(data=[])
        else:
            console.print("No repositories found.")
        return
    
    repo_data = []
    
    # Check if PyPI checking is enabled
    check_pypi = config.get('pypi', {}).get('check_by_default', True)
    
    # Temporarily suppress logging if JSON output is requested
    original_log_level = None
    if json_output:
        import logging
        original_log_level = logger.level
        logger.setLevel(logging.CRITICAL)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
            disable=json_output,  # Disable progress bar for JSON output
        ) as progress:
            
            task = progress.add_task("Scanning repositories...", total=len(repo_dirs))
            
            for repo_dir in repo_dirs:
                repo_path = os.path.join(base_dir, repo_dir)
                progress.update(task, description=f"Checking {repo_dir}...")
                
                # Get git status
                git_status = get_git_status(repo_path)
                if git_status is None:
                    git_status = {'status': 'error', 'branch': 'unknown'}
                
                # Get license info
                license_info = get_license_info(repo_path)
                
                # Get GitHub Pages URL (unless disabled)
                pages_url = None
                if not skip_pages_check:
                    pages_url = get_gh_pages_url(repo_path)
                    if pages_url:
                        stats["repos_with_pages"] += 1
                
                # Get PyPI information if enabled
                pypi_info = None
                if check_pypi:
                    pypi_data = detect_pypi_package(repo_path)
                    if pypi_data['has_packaging_files']:
                        stats["repos_with_packages"] += 1
                        
                    if pypi_data['is_published']:
                        stats["published_packages"] += 1
                        pypi_info = {
                            'package_name': pypi_data['package_name'],
                            'version': pypi_data['pypi_info']['version'],
                            'url': pypi_data['pypi_info']['url']
                        }
                        
                        # Check if package is outdated
                        if is_package_outdated(repo_path, pypi_data['package_name'], pypi_data['pypi_info']['version']):
                            stats["outdated_packages"] += 1
                    elif pypi_data['package_name']:
                        pypi_info = {
                            'package_name': pypi_data['package_name'],
                            'version': 'Not published',
                            'url': None
                        }
                
                repo_data.append({
                    'name': repo_dir,
                    'status': git_status['status'],
                    'branch': git_status['branch'],
                    'license': license_info,
                    'pages_url': pages_url,
                    'pypi_info': pypi_info
                })
                
                progress.advance(task)
    finally:
        # Restore original log level
        if original_log_level is not None:
            logger.setLevel(original_log_level)
    
    if json_output:
        console.print_json(data=repo_data)
        return
    
    # Create and display the table
    table = Table(title="Repository Status", box=box.ROUNDED)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Branch", style="yellow")
    table.add_column("License", style="green")
    
    if check_pypi:
        table.add_column("PyPI Package", style="blue")
        table.add_column("Version", style="bright_blue")
    
    if not skip_pages_check:
        table.add_column("Pages", style="bright_green")
    
    for repo in repo_data:
        row = [
            repo['name'],
            repo['status'],
            repo['branch'],
            repo['license']
        ]
        
        if check_pypi:
            if repo['pypi_info']:
                package_name = repo['pypi_info']['package_name']
                if repo['pypi_info']['url']:
                    package_name = f"[link={repo['pypi_info']['url']}]{package_name}[/link]"
                row.append(package_name)
                row.append(repo['pypi_info']['version'])
            else:
                row.extend(['N/A', 'N/A'])
        
        # Pages URL (only if not skipped)
        if not skip_pages_check:
            if repo['pages_url']:
                row.append(f"[link={repo['pages_url']}]Active[/link]")
            else:
                row.append("None")
        
        table.add_row(*row)
    
    console.print(table)
    
    # Print summary
    console.print(f"\n📊 Summary: {len(repo_dirs)} repositories")
    if check_pypi:
        console.print(f"📦 Packages: {stats['repos_with_packages']} with packaging files, {stats['published_packages']} published")
        if stats['outdated_packages'] > 0:
            console.print(f"⚠️  {stats['outdated_packages']} packages have newer versions on PyPI")
    if not skip_pages_check:
        console.print(f"📄 Pages: {stats['repos_with_pages']} with GitHub Pages")

def sample_repositories_for_social_media(repo_dirs, base_dir=".", sample_size=3):
    """
    Randomly sample repositories for social media posting.
    """
    posting_config = config.get('social_media', {}).get('posting', {})
    
    # Filter repositories based on configuration
    eligible_repos = []
    
    for repo_dir in repo_dirs:
        repo_path = os.path.join(base_dir, repo_dir)
        
        # Check if it's a valid git repository
        if not os.path.exists(os.path.join(repo_path, '.git')):
            continue
            
        # Get repository information
        pypi_data = detect_pypi_package(repo_path)
        license_info = get_license_info(repo_path)
        pages_url = get_gh_pages_url(repo_path)
        
        # Apply filters
        if posting_config.get('exclude_private', True):
            # Check if repo is private (basic check)
            # This would need more sophisticated GitHub API integration
            pass
        
        if posting_config.get('exclude_forks', True):
            # Check if repo is a fork (would need GitHub API)
            pass
        
        repo_info = {
            'name': repo_dir,
            'path': repo_path,
            'license': license_info,
            'pages_url': pages_url,
            'pypi_info': pypi_data,
            'has_package': pypi_data['has_packaging_files'],
            'is_published': pypi_data['is_published']
        }
        
        eligible_repos.append(repo_info)
    
    # Randomly sample from eligible repositories
    sample_size = min(sample_size, len(eligible_repos))
    sampled_repos = random.sample(eligible_repos, sample_size)
    
    return sampled_repos
