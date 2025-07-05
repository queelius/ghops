import click
from ghops.config import load_config
from ghops.utils import find_git_repos, get_remote_url, run_command
import json
import os
import sys
from pathlib import Path


def get_repo_metadata(repo_path, remote_url):
    """Get basic repository metadata including GitHub information if available."""
    repo_name = os.path.basename(str(Path(repo_path).resolve()))
    
    metadata = {
        "name": repo_name,
        "path": str(Path(repo_path).resolve()),
        "remote_url": remote_url,
        "github": None
    }
    
    # If it's a GitHub repo, try to get basic info
    if remote_url and ("github.com" in remote_url or "github" in remote_url.lower()):
        try:
            # Use GitHub CLI to get basic repo info (stars, description, etc.)
            repo_info = run_command(
                "gh repo view --json name,stargazerCount,description,primaryLanguage,isPrivate,isFork,forkCount", 
                cwd=repo_path, 
                capture_output=True, 
                check=False,
                log_stderr=False
            )
            if repo_info and repo_info.strip():
                github_data = json.loads(repo_info)
                primary_lang = github_data.get("primaryLanguage")
                metadata["github"] = {
                    "stars": github_data.get("stargazerCount", 0),
                    "forks": github_data.get("forkCount", 0),
                    "description": github_data.get("description", ""),
                    "language": primary_lang.get("name") if primary_lang else None,
                    "is_private": github_data.get("isPrivate", False),
                    "is_fork": github_data.get("isFork", False)
                }
        except (json.JSONDecodeError, Exception):
            # If GitHub CLI fails, just mark as GitHub repo without details
            metadata["github"] = {
                "stars": None,
                "forks": None,
                "description": None,
                "language": None,
                "is_private": None,
                "is_fork": None
            }
    
    return metadata


@click.command("list")
@click.option("--dir", help="Directory to search (overrides config)")
@click.option("--recursive", is_flag=True, help="Search subdirectories for git repos")
@click.option("--dedup", is_flag=True, help="Deduplicate repos by remote origin URL")
@click.option(
    "--dedup-details",
    is_flag=True,
    help="Show all paths for each unique remote (implies --dedup)",
)
def list_repos_handler(dir, recursive, dedup, dedup_details):
    """
    List available repositories. Outputs JSONL (one JSON object per line) for immediate feedback.
    Use 'jq -s .' to convert to JSON array if needed.
    """
    config = load_config()
    
    # Warn about memory usage for deduplication
    if dedup or dedup_details:
        print("Warning: Deduplication requires tracking seen repositories in memory.", file=sys.stderr)
        if dedup_details:
            print("Warning: Detailed deduplication analysis uses additional memory for inode tracking.", file=sys.stderr)
        print("", file=sys.stderr)  # Empty line for readability
    
    # Get repository paths
    repo_paths = []
    if dir:
        search_path = os.path.expanduser(dir)
        repo_paths = find_git_repos(search_path, recursive)
    else:
        config_dirs = config.get("general", {}).get("repository_directories", ["~/github"])
        for conf_dir in config_dirs:
            search_path = os.path.expanduser(conf_dir)
            repo_paths.extend(find_git_repos(search_path, recursive))

    # Remove duplicates that might arise from overlapping config paths
    repos = sorted(list(set(repo_paths)))

    if not repos:
        print(json.dumps({"status": "no_repos_found", "path": None, "remote_url": None}), flush=True)
        return

    if dedup or dedup_details:
        # Stream deduplicated repos
        _stream_deduplicated_repos(repos, dedup_details)
    else:
        # Stream all repos with enhanced metadata
        for repo_path in repos:
            remote_url = get_remote_url(repo_path)
            metadata = get_repo_metadata(repo_path, remote_url)
            print(json.dumps(metadata), flush=True)


def _stream_deduplicated_repos(repo_paths, include_details):
    """Stream deduplicated repositories as JSONL with enhanced metadata."""
    remotes = {}
    for repo_path in repo_paths:
        remote_url = get_remote_url(repo_path)
        if remote_url:
            if remote_url not in remotes:
                remotes[remote_url] = []
            remotes[remote_url].append(repo_path)

    if not include_details:
        # Stream unique repos (first occurrence of each remote) with metadata
        for remote_url, paths in remotes.items():
            primary_path = paths[0]
            metadata = get_repo_metadata(primary_path, remote_url)
            metadata["duplicate_count"] = len(paths)
            metadata["duplicate_paths"] = [str(Path(p).resolve()) for p in paths[1:]] if len(paths) > 1 else []
            print(json.dumps(metadata), flush=True)
    else:
        # Stream detailed deduplication info with metadata
        for remote_url, paths in remotes.items():
            # Group paths by inode to detect links vs true duplicates
            inodes = {}
            for path_str in paths:
                try:
                    real_path = Path(path_str).resolve()
                    inode = real_path.stat().st_ino
                    if inode not in inodes:
                        inodes[inode] = {"primary": str(real_path), "links": []}
                    inodes[inode]["links"].append(path_str)
                except FileNotFoundError:
                    continue

            # Stream each inode group with metadata
            for inode, data in inodes.items():
                sorted_links = sorted(data["links"])
                is_duplicate = len(inodes) > 1  # True duplicate if multiple inodes for same remote
                
                metadata = get_repo_metadata(sorted_links[0], remote_url)
                metadata.update({
                    "primary_path": data["primary"],
                    "all_paths": sorted_links,
                    "is_linked": len(sorted_links) > 1,
                    "is_true_duplicate": is_duplicate
                })
                print(json.dumps(metadata), flush=True)

