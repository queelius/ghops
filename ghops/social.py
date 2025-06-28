#!/usr/bin/env python3

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from .config import logger, config, console, stats
from .commands.status import sample_repositories_for_social_media

def format_post_content(template: str, repo_info: Dict, platform: str = "twitter") -> str:
    """Format a social media post using template and repository information."""
    
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
    
    # Sample repositories
    sampled_repos = sample_repositories_for_social_media(repo_dirs, base_dir, sample_size)
    
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

def execute_social_media_posts(posts: List[Dict], dry_run: bool = False) -> int:
    """Execute social media posts."""
    
    if not posts:
        console.print("No posts to execute.")
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
            
            if not platform_config.get('enabled', False) and not dry_run:
                logger.warning(f"Platform {platform_name} is not enabled")
                continue
            
            console.print(f"\n📱 Posting to {platform_name.title()}:")
            console.print(f"   Repository: {post.get('repo_info', {}).get('name', 'Unknown')}")
            console.print(f"   Content: {post['content']}")
            
            if dry_run:
                console.print("   [yellow]DRY RUN - Not actually posting[/yellow]")
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
                    console.print("   ✅ Posted successfully!")
                    successful_posts += 1
                    stats["social_posts"] += 1
                else:
                    console.print("   ❌ Failed to post")
                    
            except Exception as e:
                logger.error(f"Error posting to {platform_name}: {e}")
                console.print("   ❌ Failed to post")
    
    return successful_posts