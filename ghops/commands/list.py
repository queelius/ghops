import click
from ghops.config import load_config
from ghops.utils import find_git_repos, find_git_repos_from_config, get_remote_url, run_command, get_license_info, parse_repo_url
from ghops.pypi import detect_pypi_package
from ghops.render import render_list_table
import json
import os
import sys
from pathlib import Path


def get_repo_metadata(repo_path, remote_url, skip_github_info=False, skip_pages_check=False, preserve_symlinks=False):
    """Get basic repository metadata for discovery and filtering."""
    # For the name, always use the resolved path to get consistent names
    repo_name = os.path.basename(str(Path(repo_path).resolve()))
    
    # For the path, optionally preserve symlinks
    if preserve_symlinks:
        display_path = str(Path(repo_path).absolute())
    else:
        display_path = str(Path(repo_path).resolve())
    
    metadata = {
        "name": repo_name,
        "path": display_path,
        "remote_url": remote_url,
        "has_license": False,
        "has_package": False,
        "github": None
    }
    
    # Quick license check (just existence)
    license_files = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENCE', 'LICENCE.txt', 'LICENCE.md']
    for lf in license_files:
        if (Path(repo_path) / lf).exists():
            metadata["has_license"] = True
            break
    
    # Quick package check (just existence)
    package_files = ['pyproject.toml', 'setup.py', 'setup.cfg', 'package.json', 'Cargo.toml', 'go.mod']
    for pf in package_files:
        if (Path(repo_path) / pf).exists():
            metadata["has_package"] = True
            break
    
    # If it's a GitHub repo, try to get basic info (unless skipped)
    if not skip_github_info and remote_url and ("github.com" in remote_url or "github" in remote_url.lower()):
        # Cache imports removed
        from ..utils import parse_repo_url
        
        owner, repo_name_parsed = parse_repo_url(remote_url) if remote_url else (None, None)
        
        # Cache removed - go directly to GitHub CLI
        if owner and repo_name_parsed:
            try:
                # Use GitHub CLI to get basic repo info
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
                        "is_private": github_data.get("isPrivate", False),
                        "is_fork": github_data.get("isFork", False)
                    }
                    
                    # Cache call removed
                
                # Check for GitHub Pages
                if not skip_pages_check:
                    if owner and repo_name_parsed:
                        # Cache removed - go directly to GitHub API
                            pages_result = run_command(
                                f"gh api repos/{owner}/{repo_name_parsed}/pages",
                                capture_output=True,
                                check=False,
                                log_stderr=False
                            )
                            if pages_result:
                                try:
                                    pages_data = json.loads(pages_result)
                                    metadata["github"]["pages_url"] = pages_data.get('html_url')
                                    # Cache call removed
                                except json.JSONDecodeError:
                                    # Cache call removed
                                    pass
                            else:
                                # Cache call removed
                                pass
            except (json.JSONDecodeError, Exception):
                # If GitHub CLI fails, just mark as GitHub repo without details
                metadata["github"] = {
                    "is_private": None,
                    "is_fork": None
                }
    
    # If GitHub info was skipped or Pages check was not skipped, try local detection
    if skip_github_info or not skip_pages_check:
        from ..utils import detect_github_pages_locally
        pages_info = detect_github_pages_locally(repo_path)
        if pages_info and pages_info.get('likely_enabled'):
            if metadata.get("github") is None:
                metadata["github"] = {}
            # Only set pages_url if we don't already have it from API
            if not metadata["github"].get("pages_url"):
                metadata["github"]["pages_url"] = pages_info.get('pages_url')
    
    return metadata


@click.command("list")
@click.option("--dir", help="Directory to search (overrides config)")
@click.option("--recursive", is_flag=True, help="Search subdirectories for git repos")
@click.option("--no-dedup", is_flag=True, help="Show all instances including duplicates and soft links")
@click.option("--no-github", is_flag=True, help="Skip GitHub API calls for faster listing")
@click.option("--no-pages", is_flag=True, help="Skip GitHub Pages check for faster results")
@click.option("-t", "--tag", "tag_filters", multiple=True, help="Filter by tags (e.g., org:torvalds, lang:python)")
@click.option("--all-tags", is_flag=True, help="Match all tags (default: match any)")
@click.option("--pretty", is_flag=True, help="Display as formatted table instead of JSONL")
def list_repos_handler(dir, recursive, no_dedup, no_github, no_pages, tag_filters, all_tags, pretty):
    """
    List available repositories with deduplication by default.
    
    Automatically detects and marks soft links vs true duplicates.
    Outputs JSONL (one JSON object per line) for immediate feedback.
    Use 'jq -s .' to convert to JSON array if needed.
    """
    config = load_config()
    
    # Get repository paths
    repo_paths = []
    if dir:
        search_path = os.path.expanduser(dir)
        repo_paths = find_git_repos(search_path, recursive)
    else:
        config_dirs = config.get("general", {}).get("repository_directories", ["~/github"])
        repo_paths = find_git_repos_from_config(config_dirs, recursive)

    # Remove duplicates that might arise from overlapping config paths
    repos = sorted(list(set(repo_paths)))

    if not repos:
        print(json.dumps({"status": "no_repos_found", "path": None, "remote_url": None}), flush=True)
        return
    
    # Apply tag filtering if specified
    if tag_filters:
        from ..tags import filter_tags
        from ..commands.catalog import get_repositories_by_tags
        
        # Get filtered repos
        filtered_repos = list(get_repositories_by_tags(tag_filters, config, all_tags))
        filtered_paths = {str(Path(r["path"]).resolve()) for r in filtered_repos}
        
        # Filter the discovered repos
        repos = [r for r in repos if str(Path(r).resolve()) in filtered_paths]
        
        if not repos:
            error_msg = {
                "status": "no_matching_repos",
                "filters": tag_filters,
                "match_all": all_tags
            }
            if pretty:
                from rich.console import Console
                console = Console()
                filter_desc = " AND ".join(tag_filters) if all_tags else " OR ".join(tag_filters)
                console.print(f"[yellow]No repositories found matching: {filter_desc}[/yellow]")
            else:
                print(json.dumps(error_msg), flush=True)
            return

    if pretty:
        # Collect all repos and render as table
        all_repos = []
        if no_dedup:
            # Show all instances without deduplication
            for repo_path in repos:
                remote_url = get_remote_url(repo_path)
                metadata = get_repo_metadata(repo_path, remote_url, skip_github_info=no_github, skip_pages_check=no_pages, preserve_symlinks=True)
                all_repos.append(metadata)
        else:
            # Default: Collect deduplicated repos with detail
            all_repos = list(_collect_deduplicated_repos(repos, include_details=True, skip_github_info=no_github, skip_pages_check=no_pages))
        
        # Render as table
        render_list_table(all_repos)
    else:
        # Stream JSONL output (default)
        if no_dedup:
            # Stream all instances without deduplication
            for repo_path in repos:
                remote_url = get_remote_url(repo_path)
                metadata = get_repo_metadata(repo_path, remote_url, skip_github_info=no_github, skip_pages_check=no_pages, preserve_symlinks=True)
                print(json.dumps(metadata), flush=True)
        else:
            # Default: Stream deduplicated repos with details
            _stream_deduplicated_repos(repos, include_details=True, skip_github_info=no_github, skip_pages_check=no_pages)


def _collect_deduplicated_repos(repo_paths, include_details, skip_github_info=False, skip_pages_check=False):
    """Collect deduplicated repositories with basic metadata (generator)."""
    remotes = {}
    for repo_path in repo_paths:
        remote_url = get_remote_url(repo_path)
        if remote_url:
            if remote_url not in remotes:
                remotes[remote_url] = []
            remotes[remote_url].append(repo_path)

    if not include_details:
        # Yield unique repos (first occurrence of each remote) with metadata
        for remote_url, paths in remotes.items():
            primary_path = paths[0]
            metadata = get_repo_metadata(primary_path, remote_url, skip_github_info, skip_pages_check)
            metadata["duplicate_count"] = len(paths)
            metadata["duplicate_paths"] = [str(Path(p).resolve()) for p in paths[1:]] if len(paths) > 1 else []
            yield metadata
    else:
        # Yield detailed deduplication info with metadata
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

            # Yield each inode group with metadata
            for inode, data in inodes.items():
                sorted_links = sorted(data["links"])
                is_duplicate = len(inodes) > 1  # True duplicate if multiple inodes for same remote
                
                metadata = get_repo_metadata(sorted_links[0], remote_url, skip_github_info, skip_pages_check)
                metadata.update({
                    "primary_path": data["primary"],
                    "all_paths": sorted_links,
                    "is_linked": len(sorted_links) > 1,
                    "is_true_duplicate": is_duplicate
                })
                yield metadata


def _stream_deduplicated_repos(repo_paths, include_details, skip_github_info=False, skip_pages_check=False):
    """Stream deduplicated repositories as JSONL with basic metadata."""
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
            metadata = get_repo_metadata(primary_path, remote_url, skip_github_info, skip_pages_check)
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
                
                metadata = get_repo_metadata(sorted_links[0], remote_url, skip_github_info, skip_pages_check)
                metadata.update({
                    "primary_path": data["primary"],
                    "all_paths": sorted_links,
                    "is_linked": len(sorted_links) > 1,
                    "is_true_duplicate": is_duplicate
                })
                print(json.dumps(metadata), flush=True)

