#!/usr/bin/env python3

import smtplib
import json
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from pathlib import Path

from .config import logger, stats, load_config
from .utils import find_git_repos

def sample_repositories_for_social_media(repo_dirs: List[str], sample_size: int) -> List[Dict]:
    """
    Sample repositories for social media posting, prioritizing those with recent PyPI updates.
    """
    from .core import get_repo_status_stream # Local import to avoid circular dependency
    config = load_config()
    eligible_repos = []
    
    # Get status for all repos to check for PyPI info
    repo_status_list = list(get_repo_status_stream(repo_dirs))

    for repo_info in repo_status_list:
        # Rule 1: Must have a setup.py or pyproject.toml
        pypi_info = repo_info.get('pypi_info')
        if not pypi_info or not pypi_info.get('has_setup') or not pypi_info.get('is_published'):
            continue
            
        # Rule 3: Last post for this repo was more than configured days ago
        # (This requires tracking post history, which is a future enhancement)
        
        eligible_repos.append(repo_info)

    if not eligible_repos:
        return []

    # Prioritize repos with recent PyPI updates
    # This is a simplified heuristic. A more robust solution would be to check the date of the last version.
    eligible_repos.sort(key=lambda r: r.get('pypi_info', {}).get('is_outdated', True), reverse=True)

    # Sample from the top candidates
    return random.sample(eligible_repos, min(sample_size, len(eligible_repos)))

def generate_repository_report(repo_dirs: List[str]) -> Dict:
    """Generate a comprehensive report about repository status."""
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_repositories": len(repo_dirs),
        "stats": dict(stats),
        "repositories": []
    }
    
    # Get detailed info for a sample of repos
    sampled_repos = sample_repositories_for_social_media(repo_dirs, min(10, len(repo_dirs)))
    
    for repo_info in sampled_repos:
        repo_summary = {
            "name": repo_info["name"],
            "has_package": repo_info.get("has_package", False),
            "is_published": repo_info.get("is_published", False),
            "license": repo_info.get("license", "Unknown"),
            "pages_url": repo_info.get("pages_url"),
            "last_commit": repo_info.get("last_commit"),
            "status": repo_info.get("status", "Unknown")
        }
        
        if repo_info.get("pypi_info") and repo_info["pypi_info"].get("is_published"):
            pypi_info = repo_info["pypi_info"]["pypi_info"]
            repo_summary["pypi"] = {
                "package_name": repo_info["pypi_info"]["package_name"],
                "version": pypi_info["version"],
                "upload_time": pypi_info.get("upload_time")
            }
        
        report["repositories"].append(repo_summary)
    
    # Add summary statistics
    report["summary"] = {
        "repositories_with_packages": sum(1 for r in report["repositories"] if r["has_package"]),
        "published_packages": sum(1 for r in report["repositories"] if r["is_published"]),
        "repositories_with_pages": sum(1 for r in report["repositories"] if r["pages_url"]),
        "different_licenses": len(set(r["license"] for r in report["repositories"] if r["license"] != "Unknown"))
    }
    
    return report

def format_report_as_text(report: Dict) -> str:
    """Format the repository report as readable text."""
    
    text = f"""# Repository Report - {datetime.fromisoformat(report['timestamp']).strftime('%Y-%m-%d %H:%M')}

## Summary
- Total Repositories: {report['total_repositories']}
- Repositories with Packages: {report['summary']['repositories_with_packages']}
- Published Packages: {report['summary']['published_packages']}
- Repositories with GitHub Pages: {report['summary']['repositories_with_pages']}
- Different Licenses Found: {report['summary']['different_licenses']}

## Recent Activity Statistics
"""
    
    if report["stats"]:
        for key, value in report["stats"].items():
            if value > 0:
                text += f"- {key.replace('_', ' ').title()}: {value}\n"
    
    text += "\n## Sample Repository Details\n"
    
    for repo in report["repositories"]:
        text += f"\n### {repo['name']}\n"
        text += f"- License: {repo['license']}\n"
        text += f"- Status: {repo['status']}\n"
        
        if repo['has_package']:
            text += "- 📦 Has Python Package\n"
        if repo['is_published']:
            text += f"- 🚀 Published to PyPI"
            if 'pypi' in repo:
                text += f" ({repo['pypi']['package_name']} v{repo['pypi']['version']})"
            text += "\n"
        if repo['pages_url']:
            text += f"- 📖 GitHub Pages: {repo['pages_url']}\n"
        if repo['last_commit']:
            text += f"- Last Commit: {repo['last_commit']}\n"
    
    return text

def send_email_report(report: Dict, email_config: Dict) -> bool:
    """Send repository report via email."""
    
    if not email_config.get("enabled", False):
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_config['from_email']
        msg['To'] = email_config['to_email']
        msg['Subject'] = f"GitHub Repository Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Format report as text
        body = format_report_as_text(report)
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        if email_config.get('use_tls', True):
            server.starttls()
        
        if email_config['username'] and email_config['password']:
            server.login(email_config['username'], email_config['password'])
        
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email report sent successfully to {email_config['to_email']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email report: {e}")
        return False

def send_error_alert(error_msg: str, email_config: Dict) -> bool:
    """Send error alert via email."""
    
    if not email_config.get("enabled", False) or not email_config.get("error_alerts", True):
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['from_email']
        msg['To'] = email_config['to_email']
        msg['Subject'] = f"ghops Service Error Alert - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        body = f"""An error occurred in the ghops service:

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Error: {error_msg}

Please check the service logs for more details.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        if email_config.get('use_tls', True):
            server.starttls()
        
        if email_config['username'] and email_config['password']:
            server.login(email_config['username'], email_config['password'])
        
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Error alert sent to {email_config['to_email']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send error alert: {e}")
        return False

def should_send_report(service_config: Dict) -> bool:
    """Check if it's time to send a periodic report."""
    
    reporting_config = service_config.get("reporting", {})
    if not reporting_config.get("enabled", True):
        return False
    
    # Check if we have a last report timestamp
    last_report_file = Path.home() / '.ghops_last_report'
    interval_hours = reporting_config.get("interval_hours", 24)
    
    if not last_report_file.exists():
        return True
    
    try:
        with open(last_report_file, 'r') as f:
            last_report_time = datetime.fromisoformat(f.read().strip())
        
        time_since_last = datetime.now() - last_report_time
        return time_since_last.total_seconds() >= (interval_hours * 3600)
        
    except Exception as e:
        logger.warning(f"Could not read last report timestamp: {e}")
        return True

def update_last_report_time():
    """Update the timestamp of the last report."""
    last_report_file = Path.home() / '.ghops_last_report'
    try:
        with open(last_report_file, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        logger.warning(f"Could not update last report timestamp: {e}")

def generate_and_send_report(service_config: Dict) -> bool:
    """Generate and send repository report if needed."""
    
    if not should_send_report(service_config):
        return False
    
    try:
        config = load_config()
        # Get repository directories from config
        repo_dirs_config = config.get("general", {}).get("repository_directories", ["~/github"])
        repo_dirs = find_git_repos(repo_dirs_config, recursive=False)
        
        if not repo_dirs:
            logger.warning("No repositories found for reporting")
            return False
        
        # Generate report
        report = generate_repository_report(repo_dirs)
        
        # Display report to console
        print("\n📊 Repository Report")
        print(format_report_as_text(report))
        
        # Send email if configured
        email_config = service_config.get("notifications", {}).get("email", {})
        if email_config.get("enabled", False) and email_config.get("daily_summary", True):
            send_email_report(report, email_config)
        
        # Update last report timestamp
        update_last_report_time()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate repository report: {e}")
        
        # Send error alert if configured
        email_config = service_config.get("notifications", {}).get("email", {})
        send_error_alert(str(e), email_config)
        
        return False