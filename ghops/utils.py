"""
Shared utility functions for ghops.
"""
import subprocess
import os
from pathlib import Path
from .config import logger

def run_command(command, cwd=".", dry_run=False, capture_output=False, check=True):
    """
    Runs a shell command and logs the output.

    Args:
        command (str): The command to run.
        cwd (str): The working directory.
        dry_run (bool): If True, log the command without executing.
        capture_output (bool): If True, return stdout.
        check (bool): If True, raise CalledProcessError on non-zero exit codes.

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
            check=check,
            encoding='utf-8'
        )
        if result.stdout.strip():
            logger.debug(result.stdout.strip())
        if result.stderr.strip():
            logger.error(result.stderr.strip())
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {command}")
        logger.error(f"Stderr: {e.stderr.strip()}")
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
        str: The git status output, or None if an error occurs.
    """
    return run_command("git status --porcelain", repo_path, capture_output=True)

def is_git_repo(repo_path):
    """
    Checks if a directory is a Git repository.

    Args:
        repo_path (str): The directory path to check.

    Returns:
        bool: True if the directory is a Git repository, False otherwise.
    """
    return (Path(repo_path) / ".git").is_dir()
