#!/usr/bin/env python3

import argparse
from rich.table import Table
from rich.panel import Panel
import importlib.metadata

from .config import console, logger, stats, load_config, save_config, generate_config_example
from .utils import find_git_repos
from .commands.get import get_github_repos
from .commands.update import update_all_repos
from .commands.status import display_repo_status_table, sample_repositories_for_social_media
from .commands.license import list_licenses, show_license_template
from .social import create_social_media_posts, execute_social_media_posts

def reset_stats():
    """
    Resets the summary statistics.
    """
    stats.clear()
    stats.update({
        "cloned": 0,
        "skipped": 0,
        "updated": 0,
        "committed": 0,
        "pulled": 0,
        "pushed": 0,
        "conflicts": 0,
        "conflicts_resolved": 0,
        "licenses_added": 0,
        "licenses_skipped": 0,
        "repos_with_pages": 0,
        "repos_with_packages": 0,
        "published_packages": 0,
        "outdated_packages": 0,
        "social_posts": 0,
    })

def display_summary():
    """
    Displays the operation summary using a Rich table.
    """
    table = Table(title="Operation Summary")
    table.add_column("Action", style="cyan", justify="right")
    table.add_column("Count", style="magenta", justify="right")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").capitalize(), str(value))

    console.print(table)

def main():
    """
    Main function for the ghops script.
    """
    reset_stats()
    
    try:
        version = importlib.metadata.version("ghops")
    except importlib.metadata.PackageNotFoundError:
        version = "0.0.0-local"

    parser = argparse.ArgumentParser(description="GitHub Operations CLI Tool")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=False)

    # About command
    subparsers.add_parser("about", help="Show information about the author")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_action", help="Config actions")
    
    config_subparsers.add_parser("generate", help="Generate example configuration file")
    config_subparsers.add_parser("show", help="Show current configuration")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Clone GitHub repositories")
    get_parser.add_argument("-d", "--base-dir", dest="dir", default=".", help="Directory to clone repositories into")
    get_parser.add_argument("--license", default="mit", help="License to add to repositories")
    get_parser.add_argument("--license-name", help="Name for license file")
    get_parser.add_argument("--license-email", help="Email for license file")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update local repositories")
    update_parser.add_argument("-d", "--base-dir", dest="dir", default=".", help="Directory containing repositories")
    update_parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively for repositories")
    update_parser.add_argument("--license", help="License to add to repositories")
    update_parser.add_argument("--license-name", help="Name for license file")
    update_parser.add_argument("--license-email", help="Email for license file")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show repository status")
    status_parser.add_argument("-d", "--base-dir", dest="dir", default=".", help="Directory containing repositories")
    status_parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively for repositories")
    status_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    status_parser.add_argument("--no-pages-check", action="store_true", help="Skip GitHub Pages check for faster results")
    status_parser.add_argument("--no-pypi-check", action="store_true", help="Skip PyPI package detection")

    # License command
    license_parser = subparsers.add_parser("license", help="License operations")
    license_subparsers = license_parser.add_subparsers(dest="license_action", help="License actions")
    
    license_list_parser = license_subparsers.add_parser("list", help="List available licenses")
    
    license_show_parser = license_subparsers.add_parser("show", help="Show license template")
    license_show_parser.add_argument("license_key", help="License key to show")

    # Social command
    social_parser = subparsers.add_parser("social", help="Social media operations")
    social_subparsers = social_parser.add_subparsers(dest="social_action", help="Social actions")
    
    social_sample_parser = social_subparsers.add_parser("sample", help="Sample repositories for social media")
    social_sample_parser.add_argument("-d", "--base-dir", dest="dir", default=".", help="Directory containing repositories")
    social_sample_parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively")
    social_sample_parser.add_argument("--size", type=int, default=3, help="Number of repositories to sample")
    
    social_post_parser = social_subparsers.add_parser("post", help="Create and post social media content")
    social_post_parser.add_argument("-d", "--base-dir", dest="dir", default=".", help="Directory containing repositories")
    social_post_parser.add_argument("-r", "--recursive", action="store_true", help="Search recursively")
    social_post_parser.add_argument("--size", type=int, default=3, help="Number of repositories to sample")
    social_post_parser.add_argument("--dry-run", action="store_true", help="Show what would be posted without posting")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Handle about command
    if args.command == "about":
        about_text = """
[bold cyan]ghops[/bold cyan] - A GitHub Operations CLI Tool

[bold]Author:[/bold] Alex Towell <lex@metafunctor.com>
[italic]"The tools of production should be in the hands of those who use them."[/italic]
"""
        console.print(Panel(about_text, title="About", border_style="green"))
        return 0

    # Handle config commands
    if args.command == "config":
        if args.config_action == "generate":
            generate_config_example()
        elif args.config_action == "show":
            config = load_config()
            console.print_json(data=config)
        else:
            config_parser.print_help()
        return 0

    # Handle license commands
    if args.command == "license":
        if args.license_action == "list":
            list_licenses(False)
        elif args.license_action == "show":
            show_license_template(args.license_key, False)
        else:
            license_parser.print_help()
        return 0

    # Handle social media commands
    if args.command == "social":
        repo_dirs = find_git_repos(args.dir, args.recursive)
        
        if args.social_action == "sample":
            sampled_repos = sample_repositories_for_social_media(repo_dirs, args.dir, args.size)
            console.print(f"📊 Sampled {len(sampled_repos)} repositories:")
            for repo in sampled_repos:
                status_info = []
                if repo['has_package']:
                    status_info.append("📦 Has package")
                if repo['is_published']:
                    status_info.append("🚀 Published")
                if repo['pages_url']:
                    status_info.append("📄 Has pages")
                
                status_str = f" ({', '.join(status_info)})" if status_info else ""
                console.print(f"  • {repo['name']}{status_str}")
            
        elif args.social_action == "post":
            posts = create_social_media_posts(repo_dirs, args.dir, args.size)
            if posts:
                successful_posts = execute_social_media_posts(posts, args.dry_run)
                console.print(f"\n✅ Successfully processed {successful_posts}/{len(posts)} posts")
            else:
                console.print("No posts created")
        else:
            social_parser.print_help()
        return 0

    # Find repositories for main commands
    repo_dirs = find_git_repos(args.dir, getattr(args, 'recursive', False))

    if args.command == "get":
        get_github_repos(
            target_dir=args.dir,
            license_type=args.license,
            license_name=args.license_name,
            license_email=args.license_email
        )
        display_summary()

    elif args.command == "update":
        update_all_repos(
            repo_dirs=repo_dirs,
            auto_commit=getattr(args, 'auto_commit', False),
            commit_message=getattr(args, 'commit_message', 'Automated commit by ghops'),
            auto_resolve_conflicts=getattr(args, 'conflicts', 'abort'),
            prompt=getattr(args, 'prompt', False),
            ignore_list=getattr(args, 'ignore', []),
            dry_run=getattr(args, 'dry_run', False),
            add_license=bool(getattr(args, 'license', None)),
            license_type=getattr(args, 'license', 'mit'),
            author_name=getattr(args, 'license_name', None),
            author_email=getattr(args, 'license_email', None),
            license_year=getattr(args, 'license_year', None),
            force_license=getattr(args, 'force', False)
        )
        display_summary()

    elif args.command == "status":
        # Temporarily override config for this command if flags are provided
        original_config = load_config()
        if args.no_pypi_check:
            original_config['pypi']['check_by_default'] = False
        
        display_repo_status_table(
            repo_dirs, 
            args.json, 
            args.dir,
            skip_pages_check=args.no_pages_check
        )
        if not args.json:
            display_summary()

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
