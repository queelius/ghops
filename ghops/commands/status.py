"""
Handles the 'status' command for displaying repository status.
"""
import os
import json
from rich.table import Table
from rich.json import JSON
from ..config import console, logger
from ..utils import find_git_repos, get_git_status, run_command

def get_license_info(repo_path):
    """
    Gets license information for a repository.

    Args:
        repo_path (str): Path to the repository.

    Returns:
        str: The license key (e.g., 'mit') or 'N/A' if no license is found.
    """
    license_path = os.path.join(repo_path, "LICENSE")
    if not os.path.exists(license_path):
        return "N/A"
    
    # This is a simple approach. A more robust solution could use a library
    # to identify the license from its content.
    # For now, we'll just check for the presence of the file.
    try:
        with open(license_path, 'r') as f:
            content = f.read().lower()
            if "mit license" in content:
                return "mit"
            elif "gnu general public license" in content:
                return "gpl"
            # Add more license checks here
    except Exception as e:
        logger.error(f"Could not read license file in {repo_path}: {e}")
    
    return "Unknown"

def get_gh_pages_url(repo_path):
    """
    Gets the GitHub Pages URL for a repository if it exists.

    Args:
        repo_path (str): Path to the repository.

    Returns:
        str: The GitHub Pages URL or 'N/A'.
    """
    remote_url = run_command("git config --get remote.origin.url", repo_path, capture_output=True)
    if not remote_url:
        return "N/A"

    # Extract owner/repo from URL (https://github.com/owner/repo.git)
    try:
        owner_repo = '/'.join(remote_url.split('/')[-2:]).replace('.git', '')
    except IndexError:
        return "N/A"

    # Use gh api to get pages info
    pages_info_json = run_command(f"gh api repos/{owner_repo}/pages", capture_output=True, check=False)
    if not pages_info_json:
        return "N/A"
    
    try:
        pages_info = json.loads(pages_info_json)
        if pages_info.get("status") == "built":
            return pages_info.get("html_url", "N/A")
    except json.JSONDecodeError:
        return "N/A"
        
    return "N/A"

def display_repo_status(repo_stats, summary_stats, keys, json_output):
    """
    Displays the repository status either in JSON or table format.

    Args:
        repo_stats (dict): Detailed statistics of each repository.
        summary_stats (dict): Aggregated summary statistics.
        keys (list): List of keys for the table columns.
        json_output (bool): If True, output in JSON format.
    """
    if json_output:
        summary_key = "summary"
        while summary_key in repo_stats:
            # use a different name to avoid collision
            summary_key = f"_{summary_key}_"

        repo_stats[summary_key] = summary_stats
        console.print(JSON(json.dumps(repo_stats, indent=2)))
    else:
        table = Table(title="Repo Status")
        table.add_column("Repo", style="cyan", justify="right")
        for key in keys:
            if key == "remote_url":
                table.add_column("URL", style="cyan", justify="left")
            elif key == "gh_pages_url":
                table.add_column("Pages URL", style="cyan", justify="left")
            else:
                table.add_column(key.replace("_", " ").capitalize(), justify="left")

        for repo, data in repo_stats.items():
            for key in keys:
                if key == "remote_url" and data[key]:
                    data[key] = f"[link={data[key]}]Link[/link]"
                elif key == "gh_pages_url" and data[key] and data[key] != "N/A":
                    data[key] = f"[link={data[key]}]Link[/link]"
                elif key == "path" and data[key]:
                    data[key] = f"[link=file://{data[key]}]{data[key]}[/link]"
                else:
                    data[key] = str(data[key]) if data[key] else ""

            row = [repo] + [data.get(key, "") for key in keys]
            table.add_row(*row)

        console.print(table)
        console.print("\n")
        console.print(f"[bold]Summary:[/bold]")
        summary_table = Table(show_header=False)
        for key, value in summary_stats.items():
            summary_table.add_row(key.replace("_", " ").capitalize(), str(value))
        console.print(summary_table)

def display_repo_status_table(repo_dirs, json_output, base_dir=".", license_details=False, show_pages=False):
    """
    Gathers and displays the status of all repositories.

    Args:
        repo_dirs (list): List of repository directories.
        json_output (bool): If True, output in JSON format.
        base_dir (str): Base directory for display purposes.
        license_details (bool): If True, show detailed license information.
        show_pages (bool): If True, show GitHub Pages URL.
    """
    if not repo_dirs:
        logger.warning(f"No Git repositories found in '{base_dir}'.")
        return

    repo_stats = {}
    summary_stats = {
        "total_repos": len(repo_dirs),
        "clean_repos": 0,
        "dirty_repos": 0,
        "repos_with_license": 0,
        "repos_without_license": 0,
        "license_types": {},
        "repos_with_pages": 0
    }

    keys = ["path", "status", "branch", "remote_url"]
    if license_details:
        keys.append("license")
    if show_pages:
        keys.append("gh_pages_url")

    for repo_path in repo_dirs:
        repo_name = os.path.basename(repo_path)
        status = get_git_status(repo_path)
        branch = run_command("git rev-parse --abbrev-ref HEAD", repo_path, capture_output=True)
        remote_url = run_command("git config --get remote.origin.url", repo_path, capture_output=True)
        license_info = get_license_info(repo_path)
        gh_pages_url = get_gh_pages_url(repo_path) if show_pages else "N/A"

        repo_stats[repo_name] = {
            "path": repo_path,
            "status": "Clean" if not status else "Dirty",
            "branch": branch,
            "remote_url": remote_url,
            "license": license_info,
            "gh_pages_url": gh_pages_url
        }

        if not status:
            summary_stats["clean_repos"] += 1
        else:
            summary_stats["dirty_repos"] += 1
        
        if license_info != "N/A":
            summary_stats["repos_with_license"] += 1
            if license_info in summary_stats["license_types"]:
                summary_stats["license_types"][license_info] += 1
            else:
                summary_stats["license_types"][license_info] = 1
        else:
            summary_stats["repos_without_license"] += 1

        if gh_pages_url != "N/A":
            summary_stats["repos_with_pages"] += 1

    display_repo_status(repo_stats, summary_stats, keys, json_output)
