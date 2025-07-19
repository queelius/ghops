from .config import load_config, logger
from . import reporting
from . import social
from .utils import find_git_repos_from_config

def run_service_once(dry_run=False):
    """
    Runs a single cycle of the automated service.
    This includes generating reports and posting to social media.
    """
    config = load_config()
    service_config = config.get("service", {})
    results = {"reporting": {"sent": False}, "social_media": {"posts": []}}

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
    social_config = service_config.get("social_media", {})
    if social_config.get("enabled", True):
        logger.info("Running social media part of the service.")
        repo_dirs_config = config.get("general", {}).get("repository_directories", ["~/github"])
        repo_dirs = find_git_repos_from_config(repo_dirs_config, recursive=True)
        
        if repo_dirs:
            # For now, let's just post about one repository as a demonstration.
            # A more sophisticated strategy could be implemented here.
            repo_to_post = repo_dirs[0]
            platforms = social_config.get("platforms", ["twitter"])
            post_format = social_config.get("format", "New commit in {repo_name}: {commit_subject}")
            
            logger.info(f"Selected repository for social media post: {repo_to_post}")

            post_result = social.post_to_social_media(repo_to_post, platforms, post_format, dry_run)
            results["social_media"]["posts"].append(post_result)
        else:
            logger.warning("No repositories found for social media posting.")

    results["status"] = "completed"
    return results
