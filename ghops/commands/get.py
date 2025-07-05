"""
Handles the 'get' command for cloning GitHub repositories.
Supports cloning individual repositories by URL or bulk cloning from users/organizations.
"""
import os
from pathlib import Path
import click
from ghops.config import load_config
from ..utils import run_command
from ..config import logger, stats
from .license import add_license_to_repo

def get_github_repos(users, ignore_list, limit, dry_run, base_dir, visibility="all", 
                     add_license=False, license_type="mit", author_name=None, author_email=None, 
                     license_year=None, force_license=False):
    """
    Fetches repositories from GitHub users/orgs and clones them.

    Args:
        users (list): List of GitHub users or organizations.
        ignore_list (list): List of repository names to ignore.
        limit (int): Maximum number of repositories to fetch per user/org.
        dry_run (bool): If True, simulate actions without making changes.
        base_dir (str): Base directory to clone repositories into.
        visibility (str): Repository visibility ('all', 'public', 'private').
        add_license (bool): If True, add LICENSE files to cloned repositories.
        license_type (str): Type of license to add (default: 'mit').
        author_name (str, optional): Author name for license customization.
        author_email (str, optional): Author email for license customization.
        license_year (str, optional): Copyright year for license customization.
        force_license (bool): If True, overwrite existing LICENSE files.
    """
    # Ensure the base directory exists
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(base_dir)

    total_users = len(users)
    for user_idx, user in enumerate(users, 1):
        user_display = user if user else "authenticated user"
        logger.info(f"[{user_idx}/{total_users}] Fetching repositories for {user_display}...")
        user_query = user if user else ""
        repos_output = run_command(
            f'gh repo list {user_query} --limit {limit} --json nameWithOwner --jq ".[].nameWithOwner"',
            capture_output=True,
            dry_run=dry_run)

        if not repos_output:
            logger.warning(f"No repositories found for {user_display}.")
            continue

        repos = repos_output.split("\n")
        total_repos = len(repos)
        logger.info(f"Found {total_repos} repositories for {user_display}")
        
        for repo_idx, repo in enumerate(repos, 1):
            repo_name = repo.split("/")[-1]
            logger.info(f"  [{repo_idx}/{total_repos}] Processing {repo_name}...")
            
            if repo_name in ignore_list:
                logger.info(f"  Skipping ignored repo: {repo_name}")
                stats["skipped"] += 1
                continue

            repo_url = f"https://github.com/{repo}.git"
            clone_out = run_command(f'git clone "{repo_url}"', dry_run=dry_run, capture_output=True)
            if clone_out is not None:
                stats["cloned"] += 1
                
                # Add LICENSE file if requested
                if add_license:
                    repo_dir = Path(base_dir) / repo_name
                    if repo_dir.exists():
                        add_license_to_repo(
                            str(repo_dir),
                            license_key=license_type,
                            author_name=author_name,
                            author_email=author_email,
                            year=license_year,
                            dry_run=dry_run,
                            force=force_license
                        )
            else:
                logger.error(f"  Failed to clone repository: {repo}")
                stats["skipped"] += 1

@click.command("get")
@click.argument("repo_url_or_user", required=False)
@click.option(
    "--users",
    multiple=True,
    help="GitHub usernames to clone from. If not provided, uses authenticated user.",
)
@click.option(
    "--dir",
    "target_dir",
    default=".",
    help="Target directory for cloning repositories.",
)
@click.option(
    "--ignore",
    "ignore_repos",
    multiple=True,
    help="Repository names to skip during cloning.",
)
@click.option(
    "--license",
    "license_type",
    help="Add license files during cloning (e.g., 'mit', 'apache-2.0').",
)
@click.option(
    "--license-name",
    "author_name",
    help="Author name for license customization.",
)
@click.option(
    "--license-email",
    "author_email",
    help="Author email for license customization.",
)
@click.option(
    "--license-year",
    "license_year",
    help="Copyright year for license customization.",
)
@click.option(
    "--force-license",
    is_flag=True,
    help="Overwrite existing LICENSE files.",
)
@click.option(
    "--limit",
    default=100,
    help="Maximum number of repositories to fetch per user.",
)
@click.option(
    "--visibility",
    default="all",
    type=click.Choice(["all", "public", "private"]),
    help="Repository visibility filter.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview operations without making changes.",
)
def get_repo_handler(repo_url_or_user, users, target_dir, ignore_repos, license_type, author_name, 
                    author_email, license_year, force_license, limit, visibility, dry_run):
    """Clone repositories from GitHub users/organizations or a specific repository URL."""
    config = load_config()
    
    # Convert target_dir to absolute path
    target_dir = os.path.expanduser(target_dir)
    
    # Prepare license parameters
    add_license = bool(license_type)
    
    # If license is requested but no author info provided, try to get from config
    if add_license:
        if not author_name:
            author_name = config.get("general", {}).get("git_user_name", "")
        if not author_email:
            author_email = config.get("general", {}).get("git_user_email", "")
    
    # Check if repo_url_or_user is a URL or a single repository
    if repo_url_or_user:
        if repo_url_or_user.startswith(("http://", "https://", "git@")):
            # It's a URL - clone single repository
            logger.info(f"Cloning single repository: {repo_url_or_user}")
            if dry_run:
                logger.info("DRY RUN: No actual changes will be made")
            
            # Ensure target directory exists
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            os.chdir(target_dir)
            
            # Clone the repository
            clone_result = run_command(f'git clone "{repo_url_or_user}"', dry_run=dry_run, capture_output=True)
            if clone_result is not None:
                stats["cloned"] += 1
                logger.info("✅ Repository cloned successfully")
                
                # Add license if requested
                if add_license:
                    repo_name = repo_url_or_user.split("/")[-1].replace(".git", "")
                    repo_dir = Path(target_dir) / repo_name
                    if repo_dir.exists():
                        from .license import add_license_to_repo
                        add_license_to_repo(
                            str(repo_dir),
                            license_key=license_type,
                            author_name=author_name,
                            author_email=author_email,
                            year=license_year,
                            dry_run=dry_run,
                            force=force_license
                        )
            else:
                logger.error(f"Failed to clone repository: {repo_url_or_user}")
                stats["skipped"] += 1
        else:
            # It's a username - add to users list
            users = list(users) + [repo_url_or_user]
    
    # If users are specified (either via --users or as argument), clone from users
    if users:
        logger.info(f"Starting repository cloning from users: {', '.join(users)}")
        if dry_run:
            logger.info("DRY RUN: No actual changes will be made")
        
        get_github_repos(
            users=list(users),
            ignore_list=list(ignore_repos),
            limit=limit,
            dry_run=dry_run,
            base_dir=target_dir,
            visibility=visibility,
            add_license=add_license,
            license_type=license_type,
            author_name=author_name,
            author_email=author_email,
            license_year=license_year,
            force_license=force_license
        )
    elif not repo_url_or_user:
        # No users specified and no URL - use authenticated user
        logger.info("No users specified, using authenticated user")
        if dry_run:
            logger.info("DRY RUN: No actual changes will be made")
        
        get_github_repos(
            users=[""],  # Empty string means authenticated user
            ignore_list=list(ignore_repos),
            limit=limit,
            dry_run=dry_run,
            base_dir=target_dir,
            visibility=visibility,
            add_license=add_license,
            license_type=license_type,
            author_name=author_name,
            author_email=author_email,
            license_year=license_year,
            force_license=force_license
        )
    
    logger.info(f"Cloning completed. Cloned: {stats['cloned']}, Skipped: {stats['skipped']}")
