"""
Shared utility functions for ghops.
"""
import subprocess
import os
from pathlib import Path
import re
import json
from .config import logger

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

def find_git_repos(base_dir, recursive):
    """
    Finds all git repositories in the given directory.

    Args:
        base_dir (str): Base directory to search.
        recursive (bool): If True, search recursively.

    Returns:
        list: List of paths to Git repositories.
    """
    git_repos = []
    if recursive:
        for root, dirs, files in os.walk(base_dir):
            if ".git" in dirs:
                git_repos.append(root)
                # Prevent descending into subdirectories of a git repo
                dirs[:] = [d for d in dirs if d != ".git"]
    else:
        for entry in os.scandir(base_dir):
            if entry.is_dir() and is_git_repo(entry.path):
                git_repos.append(entry.path)
    return git_repos

def get_git_status(repo_path):
    """
    Gets the git status for a given repository.

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

def is_git_repo(repo_path):
    """
    Checks if a directory is a Git repository.

    Args:
        repo_path (str): The directory path to check.

    Returns:
        bool: True if the directory is a Git repository, False otherwise.
    """
    return (Path(repo_path) / ".git").is_dir()


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
