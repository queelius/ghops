"""
Shared utility functions for ghops.
"""
import subprocess
import os
from pathlib import Path
from .config import logger
import configparser
import json

JsonValue = str | int | float | bool | None | dict[str, 'JsonValue'] | list['JsonValue']

def run_command(command, cwd=".", dry_run=False, capture_output=False, check=True, log_stderr=True):
    """
    Runs a shell command and logs the output.

    Args:
        command (str): The command to run.
        cwd (str): The working directory.
        dry_run (bool): If True, log the command without executing.
        capture_output (bool): If True, return stdout.
        check (bool): If True, raise CalledProcessError on non-zero exit codes.
        log_stderr (bool): If False, do not log stderr as an error.

    Returns:
        str: The command's stdout if capture_output is True, otherwise None.
    """
    if dry_run:
        logger.info(f"[Dry Run] Would run command in '{cwd}': {command}")
        return "Dry run output" if capture_output else None

    try:
        logger.debug(f"Running command in '{cwd}': {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,  # Disable check here to handle output manually
            encoding='utf-8'
        )

        # Log stdout at the appropriate level
        if result.stdout and result.stdout.strip():
            # For certain commands, stdout is informational, not an error
            if command.startswith("git pull") and "already up to date" in result.stdout.lower():
                logger.info(result.stdout.strip())
            else:
                logger.debug(result.stdout.strip())

        # Log stderr only if the command failed
        if result.returncode != 0:
            if log_stderr and result.stderr and result.stderr.strip():
                logger.error(result.stderr.strip())
            # If check is True, re-raise the exception
            if check:
                raise subprocess.CalledProcessError(
                    result.returncode, command, output=result.stdout, stderr=result.stderr
                )

        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        if log_stderr:
            logger.error(f"Command failed with exit code {e.returncode}: {command}")
            if e.stderr:
                logger.error(f"Stderr: {e.stderr.strip()}")
            if e.stdout:
                logger.error(f"Stdout: {e.stdout.strip()}")
        if check:
            raise
        return e.stdout.strip() if capture_output else None
    except Exception as e:
        logger.error(f"An unexpected error occurred while running command '{command}': {e}")
        if check:
            raise
        return None

def is_git_repo(path):
    """Check if a given path is a Git repository."""
    return os.path.isdir(os.path.join(path, '.git'))

def find_git_repos(base_dirs, recursive=False):
    """Find all git repositories in a given directory or list of directories."""
    repos = set()
    if isinstance(base_dirs, str):
        base_dirs = [base_dirs]

    for base_dir in base_dirs:
        # If the base_dir itself is a repo, and we are not in recursive mode, add it.
        if is_git_repo(base_dir) and not recursive:
            repos.add(base_dir)
            continue # Continue to next base_dir, don't search inside

        # If recursive, walk the directory tree.
        if recursive:
            for root, dirs, _ in os.walk(base_dir):
                if '.git' in dirs:
                    repos.add(root)
                    # Once we find a .git dir, don't go deeper into that subdirectory
                    dirs[:] = [d for d in dirs if d != '.git']
                # Prune common directories to speed up search
                dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', '.venv', 'venv', 'env']]
        # If not recursive, just check the immediate subdirectories.
        else:
            try:
                for item in os.listdir(base_dir):
                    item_path = os.path.join(base_dir, item)
                    if os.path.isdir(item_path) and is_git_repo(item_path):
                        repos.add(item_path)
            except FileNotFoundError:
                logger.warning(f"Directory not found: {base_dir}")

    return sorted(list(repos))

def get_remote_url(repo_path):
    git_config = Path(repo_path) / ".git" / "config"
    if not git_config.exists():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(git_config)
        if parser.has_section('remote "origin"'):
            url = parser.get('remote "origin"', 'url', fallback=None)
            if url:
                # Normalize for deduplication
                return url.rstrip("/").replace(".git", "")
    except Exception:
        return None
    return None

def get_git_status(repo_path):
    """
    Get the git status of a repository.

    Args:
        repo_path (str): Path to the Git repository.

    Returns:
        dict: A dictionary containing 'status' and 'branch' information, or None if an error occurs.
    """
    try:
        # Get current branch
        branch_output = run_command("git rev-parse --abbrev-ref HEAD", repo_path, capture_output=True)
        branch = branch_output.strip() if branch_output else "unknown"
        
        # Get status (porcelain format for clean parsing)
        status_output = run_command("git status --porcelain", repo_path, capture_output=True)
        
        if status_output is None:
            return None
            
        # Parse status
        if not status_output.strip():
            status = "clean"
        else:
            # Count different types of changes
            lines = status_output.strip().split('\n')
            modified = sum(1 for line in lines if line.startswith(' M') or line.startswith('M'))
            added = sum(1 for line in lines if line.startswith('A'))
            deleted = sum(1 for line in lines if line.startswith(' D') or line.startswith('D'))
            untracked = sum(1 for line in lines if line.startswith('??'))
            
            status_parts = []
            if modified > 0:
                status_parts.append(f"{modified} modified")
            if added > 0:
                status_parts.append(f"{added} added")
            if deleted > 0:
                status_parts.append(f"{deleted} deleted")
            if untracked > 0:
                status_parts.append(f"{untracked} untracked")
            
            status = ", ".join(status_parts) if status_parts else "changes"
        
        return {
            'status': status,
            'branch': branch
        }
        
    except Exception as e:
        # Return a safe default if there's any error
        return {
            'status': 'error',
            'branch': 'unknown'
        }

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

def find_git_repos_from_config(repo_dirs_config, recursive=False):
    """
    Find git repositories from configuration directories.
    
    Args:
        repo_dirs_config (list): List of directory paths from configuration
        recursive (bool): Whether to search recursively
    
    Returns:
        list: List of git repository paths
    """
    if not repo_dirs_config:
        return []
    
    # Expand home directory paths
    expanded_dirs = []
    for dir_path in repo_dirs_config:
        if dir_path.startswith("~"):
            expanded_dirs.append(os.path.expanduser(dir_path))
        else:
            expanded_dirs.append(dir_path)
    
    return find_git_repos(expanded_dirs, recursive=recursive)

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
