"""
Core business logic for ghops.

All functions in this module are pure and side-effect-free.
They take data, process it, and return data (usually dicts or lists).
No printing, no direct file system access (unless reading is the core function).
"""

import json
import random
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from ghops.config import logger, stats, load_config
from ghops import reporting, social
from ghops.reporting import sample_repositories_for_social_media

from .pypi import detect_pypi_package, is_package_outdated
from .utils import find_git_repos, find_git_repos_from_config, get_remote_url, get_license_info, get_gh_pages_url, get_git_status, run_command


def list_repos(source, directory, recursive, dedup, dedup_details):
    """
    Core logic for listing repositories.
    """
    repo_paths = []
    if source == "directory":
        if not directory:
            raise ValueError("Directory must be specified when source is 'directory'")
        search_path = os.path.expanduser(directory)
        repo_paths = find_git_repos(search_path, recursive)
    else:  # source == "config"
        config = load_config()
        config_dirs = config.get("general", {}).get("repository_directories", ["~/github"])
        for conf_dir in config_dirs:
            search_path = os.path.expanduser(conf_dir)
            # When using config, we search non-recursively by default, respecting the --recursive flag
            repo_paths.extend(find_git_repos(search_path, recursive))

    # Remove duplicates that might arise from overlapping config paths
    repos = sorted(list(set(repo_paths)))

    if not repos:
        return {"status": "no_repos_found", "repos": []}

    if dedup or dedup_details:
        return _deduplicate_repos(repos, dedup_details)
    else:
        return {"status": "success", "repos": sorted([str(Path(repo).resolve()) for repo in repos])}


def _deduplicate_repos(repo_paths, include_details):
    """
    Deduplicates a list of repository paths based on their remote origin URL.
    """
    remotes = {}
    for repo_path in repo_paths:
        remote_url = get_remote_url(repo_path)
        if remote_url:
            if remote_url not in remotes:
                remotes[remote_url] = []
            # Use the original, unresolved path
            remotes[remote_url].append(repo_path)

    if not include_details:
        unique_repos = [paths[0] for paths in remotes.values()]
        return {"status": "success", "repos": sorted(unique_repos)}
    else:
        # Analyze for real duplicates vs. links
        detailed_remotes = {}
        for url, paths in remotes.items():
            # Group paths by the inode of their real path to find links
            inodes = {}
            for path_str in paths:
                try:
                    # Use the real path to get the inode
                    real_path = Path(path_str).resolve()
                    inode = real_path.stat().st_ino
                    if inode not in inodes:
                        # Store the real path as the primary and a list for all original paths
                        inodes[inode] = {"primary": str(real_path), "links": []}
                    # Add the original path to the list
                    inodes[inode]["links"].append(path_str)
                except FileNotFoundError:
                    continue # Ignore broken symlinks or other path issues

            # Reconstruct the locations list from the inode grouping
            grouped_paths = []
            for inode, data in inodes.items():
                # Sort the original paths for consistent output
                sorted_links = sorted(data["links"])
                if len(sorted_links) > 1:
                    # More than one path points to this inode
                    grouped_paths.append({
                        "type": "linked",
                        "primary": data["primary"],
                        "links": sorted_links
                    })
                else:
                    # Only one path for this inode
                    grouped_paths.append({
                        "type": "unique",
                        "path": sorted_links[0]
                    })
            
            # A true duplicate exists if there's more than one inode group for a single remote URL
            is_true_duplicate = len(grouped_paths) > 1
            
            detailed_remotes[url] = {
                "is_duplicate": is_true_duplicate,
                "locations": sorted(grouped_paths, key=lambda x: x.get('primary', x.get('path')))
            }

        return {
            "status": "success_details",
            "details": dict(sorted(detailed_remotes.items()))
        }




def get_repo_status_stream(repo_dirs, skip_pages_check=False, skip_pypi_check=False):
    """
    Core logic for getting the status of multiple repositories with streaming output.
    Yields individual repository status as they are processed.
    """
    if not repo_dirs:
        return

    config = load_config()
    check_pypi = config.get('pypi', {}).get('check_by_default', True) and not skip_pypi_check

    for repo_dir in repo_dirs:
        # Get git status
        git_status = get_git_status(repo_dir)
        if git_status is None:
            git_status = {'status': 'error', 'branch': 'unknown'}

        # Get license info
        license_info = get_license_info(repo_dir)

        # Get GitHub presence info
        github_info = get_github_presence(repo_dir)

        # Get GitHub Pages URL (unless disabled)
        pages_url = None
        if not skip_pages_check:
            pages_url = get_gh_pages_url(repo_dir)
            if pages_url:
                stats["repos_with_pages"] += 1

        # Get PyPI information if enabled
        pypi_info = None
        if check_pypi:
            pypi_data = detect_pypi_package(repo_dir)
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
                if is_package_outdated(repo_dir, pypi_data['package_name'], pypi_data['pypi_info']['version']):
                    stats["outdated_packages"] += 1
            elif pypi_data['package_name']:
                pypi_info = {
                    'package_name': pypi_data['package_name'],
                    'version': 'Not published',
                    'url': None
                }

        yield {
            'name': os.path.basename(repo_dir),
            'status': git_status['status'],
            'branch': git_status['branch'],
            'license': license_info,
            'github': github_info,
            'pages_url': pages_url,
            'pypi_info': pypi_info
        }


def get_repo(name: str, config: dict) -> dict | None:
    """
    Finds a repository by name in the configured directories.

    Args:
        name (str): The name of the repository to find.
        config (dict): The application configuration.

    Returns:
        dict | None: A dictionary with repository details or None if not found.
    """
    repo_dirs = config.get("general", {}).get("repository_directories", [])
    all_repos = find_git_repos(repo_dirs, recursive=True)

    for repo_path in all_repos:
        repo_name = os.path.basename(repo_path)
        if repo_name == name:
            return {
                "name": repo_name,
                "path": repo_path,
                "remote_url": get_remote_url(repo_path),
                "license": get_license_info(repo_path).get("spdx_id"),
                "gh_pages_url": get_gh_pages_url(repo_path),
            }
    return None


def update_repo(repo_path: str, auto_commit: bool, commit_message: str, dry_run: bool) -> dict:
    """
    Updates a single repository: pulls, optionally commits, and pushes.

    Args:
        repo_path (str): The path to the repository.
        auto_commit (bool): Whether to automatically commit changes.
        commit_message (str): The commit message to use.
        dry_run (bool): If True, simulate actions without making changes.

    Returns:
        dict: A summary of the operations performed.
    """
    summary = {
        "pulled": False,
        "committed": False,
        "pushed": False,
        "error": None
    }

    try:
        pull_output = run_command("git pull --rebase --autostash", repo_path, dry_run, capture_output=True)
        if pull_output and "already up to date" not in pull_output.lower():
            summary["pulled"] = True

        if auto_commit:
            status_output = run_command("git status --porcelain", repo_path, capture_output=True)
            if status_output and status_output.strip():
                run_command("git add -A", repo_path, dry_run)
                run_command(f'git commit -m "{commit_message}"', repo_path, dry_run)
                summary["committed"] = True

        push_output = run_command("git push", repo_path, dry_run, capture_output=True)
        if push_output and "everything up-to-date" not in push_output.lower():
            summary["pushed"] = True

    except Exception as e:
        summary["error"] = str(e)

    return summary


def get_available_licenses() -> list[dict] | None:
    """Fetches available licenses from the GitHub API."""
    try:
        licenses_json = run_command("gh api /licenses", capture_output=True)
        return json.loads(licenses_json) if licenses_json else None
    except (json.JSONDecodeError, Exception):
        return None


def get_license_template(license_key: str) -> dict | None:
    """Fetches a specific license template from the GitHub API."""
    try:
        template_json = run_command(f"gh api /licenses/{license_key}", capture_output=True)
        return json.loads(template_json) if template_json else None
    except (json.JSONDecodeError, Exception):
        return None


def add_license_to_repo(repo_path: str, license_key: str, author_name: str, author_email: str, year: str, force: bool, dry_run: bool) -> dict:
    """
    Adds a LICENSE file to a repository.

    Args:
        repo_path (str): Path to the repository.
        license_key (str): License key (e.g., 'mit').
        author_name (str): Author's name.
        author_email (str): Author's email.
        year (str): Copyright year.
        force (bool): If True, overwrite existing LICENSE file.
        dry_run (bool): If True, simulate actions.

    Returns:
        dict: A status dictionary.
    """
    license_file = Path(repo_path) / "LICENSE"
    if license_file.exists() and not force:
        return {"status": "skipped", "reason": f"LICENSE file already exists in {repo_path}"}

    template_data = get_license_template(license_key)
    if not template_data:
        return {"status": "error", "message": f"Could not fetch license template for '{license_key}'."}

    template = template_data.get("body", "")

    # Customize the template
    if not year:
        year = str(datetime.now().year)
    
    # Always replace year since we always have it
    template = template.replace("[year]", year)
    
    # Replace author info only if provided
    if author_name:
        template = template.replace("[fullname]", author_name)
    if author_email:
        template = template.replace("[email]", author_email)

    if dry_run:
        return {"status": "success_dry_run", "path": str(license_file)}
    else:
        try:
            with open(license_file, "w") as f:
                f.write(template)
            return {"status": "success", "path": str(license_file)}
        except IOError as e:
            return {"status": "error", "message": f"Failed to write LICENSE file: {e}"
}


def get_license_info(repo_path: str) -> Dict:
    """Get license information for a repository."""
    try:
        # First try to get license info using the GitHub CLI
        # Suppress stderr since this commonly fails for local repos
        license_info_json = run_command("gh repo view --json licenseInfo 2>/dev/null", cwd=repo_path, capture_output=True, check=False)
        if license_info_json and license_info_json.strip():
            try:
                license_data = json.loads(license_info_json)
                if license_data and isinstance(license_data, dict):
                    license_info = license_data.get("licenseInfo", {})
                    if license_info and isinstance(license_info, dict):
                        return {
                            "spdx_id": license_info.get("spdxId"),
                            "name": license_info.get("name"),
                            "url": license_info.get("url"),
                        }
            except json.JSONDecodeError:
                pass  # Fall through to local license detection
        
        # Fallback: try to detect license from local LICENSE file
        license_file_info = detect_local_license(repo_path)
        if license_file_info:
            return license_file_info
            
        return {"spdx_id": None, "name": "N/A", "url": None}
    except Exception as e:
        # Don't log errors for missing repositories - this is common for local repos
        return {"spdx_id": None, "name": "N/A", "url": None}


def detect_local_license(repo_path: str) -> Dict | None:
    """Detect license from local LICENSE file."""
    from pathlib import Path
    
    license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt"]
    repo_path_obj = Path(repo_path)
    
    for license_file in license_files:
        license_path = repo_path_obj / license_file
        if license_path.exists():
            try:
                content = license_path.read_text(encoding='utf-8')[:500]  # First 500 chars
                license_name = detect_license_from_content(content)
                return {
                    "spdx_id": None,
                    "name": license_name,
                    "url": None
                }
            except Exception:
                pass
    
    return None


def detect_license_from_content(content: str) -> str:
    """Detect license type from file content."""
    content_lower = content.lower()
    
    if "mit license" in content_lower or "mit " in content_lower:
        return "MIT License"
    elif "apache license" in content_lower and "2.0" in content_lower:
        return "Apache License 2.0"
    elif "gnu general public license" in content_lower and "version 3" in content_lower:
        return "GNU General Public License v3.0"
    elif "gnu general public license" in content_lower and "version 2" in content_lower:
        return "GNU General Public License v2.0"
    elif "bsd" in content_lower and "3-clause" in content_lower:
        return "BSD 3-Clause License"
    elif "bsd" in content_lower and "2-clause" in content_lower:
        return "BSD 2-Clause License"
    elif "unlicense" in content_lower:
        return "The Unlicense"
    elif "creative commons" in content_lower:
        return "Creative Commons License"
    else:
        return "Other"


def format_post_content(template: str, repo_info: Dict, platform: str = "twitter") -> str:
    """Format a social media post using template and repository information."""
    config = load_config()
    
    # Basic repository information
    variables = {
        'repo_name': repo_info['name'],
        'repo_url': f"https://github.com/{config.get('general', {}).get('github_username', 'username')}/{repo_info['name']}",
        'description': f"A {repo_info.get('license', 'open source')} project",
        'language': 'Python',  # Could be detected from repo
        'license': repo_info.get('license', 'Unknown')
    }
    
    # PyPI-specific information
    if repo_info.get('pypi_info') and repo_info['pypi_info'].get('is_published'):
        pypi_info = repo_info['pypi_info']['pypi_info']
        variables.update({
            'package_name': repo_info['pypi_info']['package_name'],
            'version': pypi_info['version'],
            'pypi_url': pypi_info['url'],
        })
    
    # GitHub Pages information
    if repo_info.get('pages_url'):
        variables['pages_url'] = repo_info['pages_url']
    
    try:
        return template.format(**variables)
    except KeyError as e:
        logger.warning(f"Missing variable {e} in template for {platform}")
        return template


def create_social_media_posts(repo_dirs: List[str], base_dir: str = ".", sample_size: int = 3) -> List[Dict]:
    """Create social media posts for sampled repositories."""
    config = load_config()
    # Sample repositories
    sampled_repos = sample_repositories_for_social_media(repo_dirs, sample_size)
    if not sampled_repos:
        logger.warning("No eligible repositories found for social media posting")
        return []
    
    posts = []
    platforms = config.get('social_media', {}).get('platforms', {})
    
    for repo_info in sampled_repos:
        for platform_name, platform_config in platforms.items():
            if not platform_config.get('enabled', False):
                continue
            
            templates = platform_config.get('templates', {})
            
            # Determine which template to use
            template_key = 'random_highlight'  # Default
            
            if repo_info['is_published'] and 'pypi_release' in templates:
                template_key = 'pypi_release'
            elif repo_info.get('pages_url') and 'github_pages' in templates:
                template_key = 'github_pages'
            
            if template_key in templates:
                content = format_post_content(templates[template_key], repo_info, platform_name)
                
                post = {
                    'platform': platform_name,
                    'content': content,
                    'repo_name': repo_info['name'],
                    'repo_info': repo_info,  # Include full repo info
                    'template_used': template_key,
                    'timestamp': datetime.now().isoformat()
                }
                
                posts.append(post)
    
    return posts


def post_to_twitter(content: str, credentials: Dict) -> bool:
    """Post content to Twitter/X (placeholder implementation)."""
    # This would require actual Twitter API integration
    logger.info(f"[TWITTER] Would post: {content}")
    return True


def post_to_linkedin(content: str, credentials: Dict) -> bool:
    """Post content to LinkedIn (placeholder implementation)."""
    # This would require actual LinkedIn API integration
    logger.info(f"[LINKEDIN] Would post: {content}")
    return True


def post_to_mastodon(content: str, credentials: Dict) -> bool:
    """Post content to Mastodon (placeholder implementation)."""
    # This would require actual Mastodon API integration
    logger.info(f"[MASTODON] Would post: {content}")
    return True


def validate_twitter_config(twitter_config):
    required = ["api_key", "api_secret", "access_token", "access_token_secret"]
    missing = [k for k in required if not twitter_config.get(k)]
    if missing:
        logger.error(
            f"Twitter config missing required fields: {', '.join(missing)}. "
            "Please set these in your ~/.ghopsrc under social_media.platforms.twitter."
        )
        return False
    return True


def validate_linkedin_config(linkedin_config):
    if not linkedin_config.get("access_token"):
        logger.error(
            "LinkedIn config missing required field: access_token. "
            "Please set this in your ~/.ghopsrc under social_media.platforms.linkedin."
        )
        return False
    return True


def validate_mastodon_config(mastodon_config):
    required = ["instance_url", "access_token"]
    missing = [k for k in required if not mastodon_config.get(k)]
    if missing:
        logger.error(
            f"Mastodon config missing required fields: {', '.join(missing)}. "
            "Please set these in your ~/.ghopsrc under social_media.platforms.mastodon."
        )
        return False
    return True


def execute_social_media_posts(posts: List[Dict], dry_run: bool = False) -> int:
    """Execute social media posts."""
    config = load_config()
    
    if not posts:
        return 0
    
    platforms_config = config.get('social_media', {}).get('platforms', {})
    successful_posts = 0
    
    for post in posts:
        # Handle both 'platform' (single) and 'platforms' (multiple) keys
        platform_names = post.get('platforms', [post.get('platform')] if post.get('platform') else [])
        
        for platform_name in platform_names:
            if not platform_name:
                continue
            
            platform_config = platforms_config.get(platform_name, {})
            
            # Validate required config before posting
            if platform_name == 'twitter' and not validate_twitter_config(platform_config):
                continue
            if platform_name == 'linkedin' and not validate_linkedin_config(platform_config):
                continue
            if platform_name == 'mastodon' and not validate_mastodon_config(platform_config):
                continue
            
            if not platform_config.get('enabled', False) and not dry_run:
                logger.warning(f"Platform {platform_name} is not enabled")
                continue
            
            if dry_run:
                successful_posts += 1
                continue
            
            # Execute the actual post
            success = False
            try:
                if platform_name == 'twitter':
                    success = post_to_twitter(post['content'], platform_config)
                elif platform_name == 'linkedin':
                    success = post_to_linkedin(post['content'], platform_config)
                elif platform_name == 'mastodon':
                    success = post_to_mastodon(post['content'], platform_config)
                else:
                    logger.error(f"Unknown platform: {platform_name}")
                    continue
                
                if success:
                    successful_posts += 1
                    stats["social_posts"] += 1
                    
            except Exception as e:
                logger.error(f"Error posting to {platform_name}: {e}")
    
    return successful_posts

def run_service_once(dry_run=False):
    """
    Runs a single cycle of the automated service.
    This includes generating reports and posting to social media.
    """
    config = load_config()
    service_config = config.get("service", {})
    results = {"reporting": {"sent": False}, "social_media": {"posts": []}, "status": "started"}

    if not service_config.get("enabled", True):
        logger.info("Service is disabled in the configuration.")
        results["status"] = "disabled"
        return results

    # --- Reporting --- 
    if service_config.get("reporting", {}).get("enabled", True):
        logger.info("Running reporting part of the service.")
        if not dry_run:
            reporting_sent = reporting.generate_and_send_report(service_config)
            results["reporting"]["sent"] = reporting_sent
        else:
            logger.info("Dry run: would have generated and sent a report.")
            results["reporting"]["sent"] = "dry-run"

    # --- Social Media Posting ---
    social_config = config.get("social_media", {})
    if social_config.get("enabled", True):
        logger.info("Running social media part of the service.")
        repo_dirs_config = config.get("general", {}).get("repository_directories", ["~/github"])
        repo_dirs = find_git_repos_from_config(repo_dirs_config, recursive=True)
        
        if repo_dirs:
            posts = create_social_media_posts(repo_dirs, sample_size=social_config.get("sample_size", 1))
            if posts:
                logger.info(f"Generated {len(posts)} social media post(s).")
                post_results = execute_social_media_posts(posts, dry_run)
                results["social_media"]["posts"] = post_results
            else:
                logger.info("No eligible repositories found for social media posting this cycle.")
        else:
            logger.warning("No repositories found for social media posting.")

    results["status"] = "completed"
    return results

def get_github_presence(repo_path: str) -> Dict:
    """Check if repository has a presence on GitHub."""
    try:
        # Try to get basic repo info from GitHub CLI
        repo_info_json = run_command("gh repo view --json name,url,isPrivate,isFork 2>/dev/null", cwd=repo_path, capture_output=True, check=False)
        if repo_info_json and repo_info_json.strip():
            try:
                repo_data = json.loads(repo_info_json)
                if repo_data and isinstance(repo_data, dict) and repo_data.get("name"):
                    return {
                        "on_github": True,
                        "url": repo_data.get("url"),
                        "is_private": repo_data.get("isPrivate", False),
                        "is_fork": repo_data.get("isFork", False),
                        "name": repo_data.get("name")
                    }
            except json.JSONDecodeError:
                pass
        
        # Fallback: check if there's a GitHub remote URL
        remote_url = get_remote_url(repo_path)
        if remote_url and ("github.com" in remote_url or "github" in remote_url.lower()):
            return {
                "on_github": True,
                "url": remote_url,
                "is_private": None,  # Unknown without API access
                "is_fork": None,     # Unknown without API access
                "name": None         # Unknown without API access
            }
        
        return {
            "on_github": False,
            "url": None,
            "is_private": None,
            "is_fork": None,
            "name": None
        }
    except Exception:
        return {
            "on_github": False,
            "url": None,
            "is_private": None,
            "is_fork": None,
            "name": None
        }

def list_repos_stream(source, directory, recursive, dedup, dedup_details):
    """
    Streaming version of list_repos that yields repositories one by one.
    
    For deduplication, maintains an in-memory hash table of seen remote URLs
    or paths, which can be memory-intensive for large repository sets.
    """
    repo_paths = []
    if source == "directory":
        if not directory:
            raise ValueError("Directory must be specified when source is 'directory'")
        search_path = os.path.expanduser(directory)
        repo_paths = find_git_repos(search_path, recursive)
    else:  # source == "config"
        config = load_config()
        config_dirs = config.get("general", {}).get("repository_directories", ["~/github"])
        for conf_dir in config_dirs:
            search_path = os.path.expanduser(conf_dir)
            repo_paths.extend(find_git_repos(search_path, recursive))

    # Remove duplicates that might arise from overlapping config paths
    repos = sorted(list(set(repo_paths)))

    if not repos:
        return

    if dedup or dedup_details:
        # Memory-intensive operation - track seen remotes/inodes
        if dedup_details:
            seen_remotes = {}  # url -> list of {path, inode, type}
            seen_inodes = {}   # inode -> path
            
            for repo_path in repos:
                try:
                    remote_url = get_remote_url(repo_path)
                    real_path = Path(repo_path).resolve()
                    inode = real_path.stat().st_ino
                    
                    if remote_url:
                        if remote_url not in seen_remotes:
                            seen_remotes[remote_url] = []
                        
                        # Determine if this is a link to an existing repo
                        is_link = inode in seen_inodes
                        entry = {
                            "path": repo_path,
                            "real_path": str(real_path),
                            "inode": inode,
                            "type": "linked" if is_link else "unique",
                            "remote_url": remote_url
                        }
                        
                        if is_link:
                            entry["linked_to"] = seen_inodes[inode]
                        else:
                            seen_inodes[inode] = repo_path
                            
                        seen_remotes[remote_url].append(entry)
                except (FileNotFoundError, OSError):
                    continue
            
            # Yield detailed results
            for remote_url, entries in seen_remotes.items():
                if len(entries) > 1:
                    # Multiple entries for same remote
                    primary = next((e for e in entries if e["type"] == "unique"), entries[0])
                    links = [e["path"] for e in entries if e["path"] != primary["path"]]
                    
                    yield {
                        "type": "duplicate_group",
                        "remote_url": remote_url,
                        "primary": primary["path"],
                        "duplicates": links,
                        "is_linked": any(e["type"] == "linked" for e in entries)
                    }
                else:
                    # Single entry
                    yield {
                        "type": "unique",
                        "path": entries[0]["path"],
                        "remote_url": remote_url
                    }
        else:
            # Simple dedup - just track seen remote URLs
            seen_remotes = set()
            
            for repo_path in repos:
                try:
                    remote_url = get_remote_url(repo_path)
                    if remote_url:
                        if remote_url not in seen_remotes:
                            seen_remotes.add(remote_url)
                            yield {
                                "type": "unique",
                                "path": repo_path,
                                "remote_url": remote_url
                            }
                        # Skip duplicates silently
                    else:
                        # No remote URL, yield anyway
                        yield {
                            "type": "unique", 
                            "path": repo_path,
                            "remote_url": None
                        }
                except Exception:
                    # Yield problematic repos too
                    yield {
                        "type": "unique",
                        "path": repo_path, 
                        "remote_url": None
                    }
    else:
        # No deduplication - simple streaming
        for repo_path in repos:
            yield {
                "type": "repository",
                "path": str(Path(repo_path).resolve())
            }
