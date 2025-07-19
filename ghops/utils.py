"""
Shared utility functions for ghops.
"""
import subprocess
import os
from pathlib import Path
import re
import json
from .config import logger
import configparser
import json

JsonValue = str | int | float | bool | None | dict[str, 'JsonValue'] | list['JsonValue']

def get_git_remote_url(repo_path, remote_name="origin"):
    """
    Gets the URL of a specific remote for a Git repository.

    Args:
        repo_path (str): Path to the Git repository.
        remote_name (str): The name of the remote (e.g., 'origin').

    Returns:
        str: The URL of the remote, or None if not found.
    """
    try:
        return run_command(
            f"git config --get remote.{remote_name}.url",
            cwd=repo_path,
            capture_output=True,
            check=False,
            log_stderr=False
        )
    except Exception:
        return None

def parse_repo_url(url):
    """
    Parses a GitHub URL to extract the owner and repository name.
    Handles HTTPS and SSH formats.

    Args:
        url (str): The GitHub repository URL.

    Returns:
        tuple: A tuple (owner, repo) or (None, None) if parsing fails.
    """
    if not url:
        return None, None

    # HTTPS: https://github.com/owner/repo.git
    https_match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if https_match:
        return https_match.groups()

    # SSH: git@github.com:owner/repo.git
    ssh_match = re.search(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.groups()

    return None, None


def get_remote_url(repo_path: str) -> str | None:
    """
    Get the remote URL for a git repository.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        Remote URL or None if not found
    """
    return get_git_remote_url(repo_path, "origin")


def get_github_repo_info(owner: str, repo: str) -> dict[str, JsonValue] | None:
    """
    Get repository information from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        
    Returns:
        Repository data or None if failed
    """
    try:
        # Use gh CLI to get full repo info
        output = run_command(
            f'gh api repos/{owner}/{repo}',
            capture_output=True,
            check=False,
            log_stderr=False
        )
        
        if output:
            return json.loads(output)
    except:
        pass
    return None


def check_github_repo_status(owner, repo):
    """
    Checks if a GitHub repository exists, its visibility (Public/Private), and if it's a fork.

    Args:
        owner (str): The repository owner.
        repo (str): The repository name.

    Returns:
        dict: A dict with 'exists' (bool), 'visibility' (str), and 'is_fork' (bool).
    """
    if not owner or not repo:
        return {'exists': False, 'visibility': 'N/A', 'is_fork': False}
    try:
        command = f"gh repo view {owner}/{repo} --json name,visibility,isFork"
        result = run_command(command, capture_output=True, check=False, log_stderr=False)

        if result:
            try:
                data = json.loads(result)
                return {
                    'exists': True,
                    'visibility': data.get('visibility', 'Unknown').capitalize(),
                    'is_fork': data.get('isFork', False)
                }
            except json.JSONDecodeError:
                return {'exists': False, 'visibility': 'N/A', 'is_fork': False}
        else:
            return {'exists': False, 'visibility': 'N/A', 'is_fork': False}
    except Exception as e:
        logger.debug(f"Failed to check GitHub status for {owner}/{repo}: {e}")
        return {'exists': False, 'visibility': 'Error', 'is_fork': False}


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
        branch_output = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_path, capture_output=True, check=False)
        branch = branch_output.strip() if branch_output else "unknown"
        
        # Get status (porcelain format for clean parsing)
        status_output = run_command("git status --porcelain", cwd=repo_path, capture_output=True, check=False)
        
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
        
        # Get ahead/behind counts
        ahead = 0
        behind = 0
        
        # Check if we have an upstream branch
        upstream_check = run_command(
            "git rev-parse --abbrev-ref @{u}", 
            cwd=repo_path, 
            capture_output=True, 
            check=False,
            log_stderr=False
        )
        
        if upstream_check and not upstream_check.startswith("fatal:"):
            # Get ahead/behind counts
            rev_list_output = run_command(
                "git rev-list --left-right --count HEAD...@{u}",
                cwd=repo_path,
                capture_output=True,
                check=False,
                log_stderr=False
            )
            if rev_list_output:
                parts = rev_list_output.strip().split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
        
        return {
            'status': status,
            'branch': branch,
            'current_branch': branch,  # For backward compatibility
            'ahead': ahead,
            'behind': behind
        }
        
    except Exception as e:
        # Return a safe default if there's any error
        logger.debug(f"Failed to get git status for {repo_path}: {e}")
        return {
            'status': 'error',
            'branch': 'unknown',
            'current_branch': 'unknown',
            'ahead': 0,
            'behind': 0
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
    
    Supports patterns:
    - ~/github - search just this directory
    - ~/github/* - search immediate subdirectories
    - ~/github/** - search recursively (overrides recursive param)
    
    Args:
        repo_dirs_config (list): List of directory paths from configuration
        recursive (bool): Whether to search recursively (can be overridden by ** pattern)
    
    Returns:
        list: List of git repository paths
    """
    if not repo_dirs_config:
        return []
    
    # Expand home directory and glob patterns
    expanded_dirs = []
    recursive_dirs = {}  # Track which dirs should be searched recursively
    
    for dir_path in repo_dirs_config:
        # First expand ~ to home directory
        expanded_path = os.path.expanduser(dir_path)
        
        # Check if this uses ** pattern for recursive search
        force_recursive = '**' in dir_path
        
        # Handle ** pattern by using recursive glob
        import glob
        if force_recursive and expanded_path.endswith('/**'):
            # For patterns ending with /**, search the parent directory recursively
            parent_path = expanded_path[:-3]  # Remove /**
            if os.path.isdir(parent_path):
                expanded_dirs.append(parent_path)
                recursive_dirs[parent_path] = True
        else:
            # Standard glob expansion
            glob_results = glob.glob(expanded_path)
            
            if glob_results:
                # If glob found matches, add all of them
                for match in glob_results:
                    if os.path.isdir(match):
                        expanded_dirs.append(match)
                        if force_recursive:
                            recursive_dirs[match] = True
            else:
                # If no glob matches, check if it's a direct path
                if os.path.isdir(expanded_path):
                    expanded_dirs.append(expanded_path)
                    if force_recursive:
                        recursive_dirs[expanded_path] = True
                else:
                    logger.warning(f"Directory not found: {expanded_path}")
    
    # Find git repos in all expanded directories
    all_repos = []
    for dir_path in expanded_dirs:
        # Use pattern-specific recursive setting if available, otherwise use parameter
        search_recursive = recursive_dirs.get(dir_path, recursive)
        all_repos.extend(find_git_repos(dir_path, recursive=search_recursive))
    
    return all_repos

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


def detect_github_pages_locally(repo_path):
    """
    Try to detect if GitHub Pages is likely enabled based on local repository structure.
    Returns a dict with detection info or None if no evidence found.
    """
    indicators = {
        'has_gh_pages_branch': False,
        'has_pages_workflow': False,
        'has_jekyll_config': False,
        'has_docs_folder': False,
        'has_cname': False,
        'likely_enabled': False
    }
    
    try:
        # Check for gh-pages branch
        branches_result = run_command(
            "git branch -a",
            cwd=repo_path,
            capture_output=True,
            check=False,
            log_stderr=False
        )
        if branches_result and 'gh-pages' in branches_result:
            indicators['has_gh_pages_branch'] = True
        
        # Check for GitHub Actions workflow that deploys to Pages
        workflows_path = Path(repo_path) / '.github' / 'workflows'
        if workflows_path.exists():
            for workflow_file in workflows_path.glob('*.yml'):
                try:
                    content = workflow_file.read_text()
                    if 'pages' in content.lower() and ('deploy' in content.lower() or 'publish' in content.lower()):
                        indicators['has_pages_workflow'] = True
                        break
                except:
                    pass
        
        # Check for Jekyll config
        if (Path(repo_path) / '_config.yml').exists():
            indicators['has_jekyll_config'] = True
        
        # Check for docs folder (common for documentation sites)
        if (Path(repo_path) / 'docs').exists():
            indicators['has_docs_folder'] = True
            # Check if docs has index.html or index.md
            docs_path = Path(repo_path) / 'docs'
            if (docs_path / 'index.html').exists() or (docs_path / 'index.md').exists():
                indicators['has_docs_folder'] = True
        
        # Check for CNAME file (custom domain)
        if (Path(repo_path) / 'CNAME').exists():
            indicators['has_cname'] = True
        
        # Determine if Pages is likely enabled
        if (indicators['has_gh_pages_branch'] or 
            indicators['has_pages_workflow'] or 
            indicators['has_jekyll_config'] or
            indicators['has_cname']):
            indicators['likely_enabled'] = True
        
        # If we found evidence, return the indicators
        if indicators['likely_enabled']:
            # Try to construct likely URL
            remote_url = get_remote_url(repo_path)
            if remote_url:
                owner, repo_name = parse_repo_url(remote_url)
                if owner and repo_name:
                    # Check if CNAME exists for custom domain
                    cname_path = Path(repo_path) / 'CNAME'
                    if cname_path.exists():
                        try:
                            custom_domain = cname_path.read_text().strip()
                            indicators['pages_url'] = f"https://{custom_domain}"
                        except:
                            indicators['pages_url'] = f"https://{owner}.github.io/{repo_name}"
                    else:
                        indicators['pages_url'] = f"https://{owner}.github.io/{repo_name}"
            
            return indicators
    
    except Exception as e:
        logger.debug(f"Error detecting GitHub Pages for {repo_path}: {e}")
    
    return None
