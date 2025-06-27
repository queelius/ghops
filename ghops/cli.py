#!/usr/bin/env python3

import argparse
from rich.table import Table

from .config import console, logger, stats
from .utils import find_git_repos
from .commands.get import get_github_repos
from .commands.update import update_all_repos
from .commands.status import display_repo_status_table
from .commands.license import list_licenses, show_license_template

def reset_stats():
    """
    Resets the summary statistics.
    """
    global stats
    stats = {
        "cloned": 0,
        "skipped": 0,
        "updated": 0,
        "committed": 0,
        "pulled": 0,
        "pushed": 0,
        "conflicts": 0,
        "conflicts_resolved": 0,
        "licenses_added": 0,
        "licenses_skipped": 0
    }

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
    parser = argparse.ArgumentParser(description="Manage multiple GitHub repositories.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'get' command
    parser_get = subparsers.add_parser("get", help="Clone repositories from GitHub.")
    parser_get.add_argument("users", nargs="*", help="GitHub users or organizations to fetch from.")
    parser_get.add_argument("-d", "--dir", default=".", help="Directory to clone into.")
    parser_get.add_argument("-l", "--limit", type=int, default=100, help="Max number of repos to fetch.")
    parser_get.add_argument("-i", "--ignore", nargs="*", default=[], help="Repositories to ignore.")
    parser_get.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes.")
    parser_get.add_argument("--add-license", action="store_true", help="Add a LICENSE file to cloned repos.")
    parser_get.add_argument("--license", default="mit", help="License to use (e.g., mit, gpl-3.0)." )
    parser_get.add_argument("--author", help="Author name for the license.")
    parser_get.add_argument("--email", help="Author email for the license.")
    parser_get.add_argument("--year", help="Year for the license.")
    parser_get.add_argument("-f", "--force", action="store_true", help="Force overwrite of existing LICENSE file.")

    # 'update' command
    parser_update = subparsers.add_parser("update", help="Update local repositories.")
    parser_update.add_argument("-d", "--dir", default=".", help="Directory to search for repos.")
    parser_update.add_argument("-r", "--recursive", action="store_true", help="Search for repos recursively.")
    parser_update.add_argument("-i", "--ignore", nargs="*", default=[], help="Repositories to ignore.")
    parser_update.add_argument("--auto-commit", action="store_true", help="Automatically commit changes before pulling.")
    parser_update.add_argument("--commit-message", default="Auto-commit by ghops", help="Commit message for auto-commits.")
    parser_update.add_argument("--auto-resolve-conflicts", choices=["ours", "theirs", "abort"], help="How to resolve merge conflicts.")
    parser_update.add_argument("--prompt", action="store_true", help="Prompt before pushing changes.")
    parser_update.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes.")
    parser_update.add_argument("--add-license", action="store_true", help="Add a LICENSE file to cloned repos.")
    parser_update.add_argument("--license", default="mit", help="License to use (e.g., mit, gpl-3.0)." )
    parser_update.add_argument("--author", help="Author name for the license.")
    parser_update.add_argument("--email", help="Author email for the license.")
    parser_update.add_argument("--year", help="Year for the license.")
    parser_update.add_argument("-f", "--force", action="store_true", help="Force overwrite of existing LICENSE file.")

    # 'status' command
    parser_status = subparsers.add_parser("status", help="Show status of local repositories.")
    parser_status.add_argument("-d", "--dir", default=".", help="Directory to search for repos.")
    parser_status.add_argument("-r", "--recursive", action="store_true", help="Search for repos recursively.")
    parser_status.add_argument("--json", action="store_true", help="Output in JSON format.")
    parser_status.add_argument("--license-details", action="store_true", help="Show detailed license information.")
    parser_status.add_argument("--show-pages", action="store_true", help="Show GitHub Pages URL.")

    # 'license' command
    parser_license = subparsers.add_parser("license", help="Manage LICENSE files.")
    license_group = parser_license.add_mutually_exclusive_group(required=True)
    license_group.add_argument("--list", action="store_true", help="List available licenses.")
    license_group.add_argument("--show", help="Show a specific license template.")
    parser_license.add_argument("--json", action="store_true", help="Output in JSON format.")

    args = parser.parse_args()

    if args.command == "get":
        get_github_repos(
            users=args.users,
            ignore_list=args.ignore,
            limit=args.limit,
            dry_run=args.dry_run,
            base_dir=args.dir,
            add_license=args.add_license,
            license_type=args.license,
            author_name=args.author,
            author_email=args.email,
            license_year=args.year,
            force_license=args.force
        )
    elif args.command == "update":
        update_all_repos(
            auto_commit=args.auto_commit,
            commit_message=args.commit_message,
            auto_resolve_conflicts=args.auto_resolve_conflicts,
            prompt=args.prompt,
            ignore_list=args.ignore,
            dry_run=args.dry_run,
            base_dir=args.dir,
            recursive=args.recursive,
            add_license=args.add_license,
            license_type=args.license,
            author_name=args.author,
            author_email=args.email,
            license_year=args.year,
            force_license=args.force
        )
    elif args.command == "status":
        repo_dirs = find_git_repos(args.dir, args.recursive)
        display_repo_status_table(repo_dirs, args.json, args.dir, args.license_details, args.show_pages)
    elif args.command == "license":
        if args.list:
            list_licenses(args.json)
        elif args.show:
            show_license_template(args.show, args.json)

    display_summary()

if __name__ == "__main__":
    main()
