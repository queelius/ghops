"""
Social media content generation for ghops.
"""

from typing import Dict, Any, Optional
import random
import hashlib


def generate_social_content(metadata: Dict[str, Any], platform: str, 
                           platform_config: Dict[str, Any]) -> Optional[str]:
    """
    Generate social media content for a repository.
    
    Args:
        metadata: Repository metadata
        platform: Platform name (twitter, linkedin, etc.)
        platform_config: Platform configuration
        
    Returns:
        Generated content string or None
    """
    # Get repository info
    repo_name = metadata.get('name', 'Unknown')
    description = metadata.get('description', '')
    stars = metadata.get('stargazers_count', 0)
    language = metadata.get('language', 'Unknown')
    topics = metadata.get('topics', [])
    homepage = metadata.get('homepage', '')
    
    # Get template from config or use default
    template = platform_config.get('template', get_default_template(platform))
    
    # Replace placeholders
    content = template
    content = content.replace('{{repo_name}}', repo_name)
    content = content.replace('{{description}}', description or f"A {language} project")
    content = content.replace('{{stars}}', str(stars))
    content = content.replace('{{language}}', language)
    content = content.replace('{{topics}}', ', '.join(topics[:3]) if topics else language)
    content = content.replace('{{url}}', homepage or f"https://github.com/{metadata.get('owner', '')}/{repo_name}")
    
    # Add hashtags
    hashtags = generate_hashtags(metadata, platform_config)
    content = content.replace('{{hashtags}}', ' '.join(hashtags))
    
    # Platform-specific length limits
    if platform == 'twitter':
        max_length = 280
        if len(content) > max_length:
            # Truncate with ellipsis
            content = content[:max_length-3] + '...'
    
    return content


def get_default_template(platform: str) -> str:
    """Get default template for a platform."""
    templates = {
        'twitter': "🚀 Check out {{repo_name}}! {{description}} ⭐ {{stars}} stars {{hashtags}} {{url}}",
        'linkedin': "Excited to share {{repo_name}}! {{description}}\n\n🔧 Built with {{language}}\n⭐ {{stars}} stars on GitHub\n\n{{hashtags}}\n\n{{url}}",
        'mastodon': "📦 {{repo_name}}: {{description}}\n\n{{hashtags}}\n\n{{url}}"
    }
    return templates.get(platform, "Check out {{repo_name}}: {{description}} {{url}}")


def generate_hashtags(metadata: Dict[str, Any], platform_config: Dict[str, Any]) -> list:
    """Generate hashtags for a repository."""
    hashtags = []
    
    # Language hashtag
    language = metadata.get('language', '').lower()
    if language:
        hashtags.append(f"#{language}")
    
    # Topic hashtags
    topics = metadata.get('topics', [])
    for topic in topics[:2]:  # Limit to 2 topics
        hashtags.append(f"#{topic.replace('-', '').replace('_', '')}")
    
    # Common hashtags from config
    common_hashtags = platform_config.get('hashtags', ['#opensource', '#github'])
    hashtags.extend(common_hashtags[:2])  # Limit common hashtags
    
    # Deduplicate
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique_hashtags.append(tag)
    
    return unique_hashtags[:5]  # Limit total hashtags


def generate_social_media_post(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generate a social media post from repository metadata.
    
    This is a legacy function for backward compatibility.
    """
    from .config import load_config
    
    config = load_config()
    platforms = config.get('social_media', {}).get('platforms', {})
    
    post_data = {
        'repo_name': metadata.get('name'),
        'repo_path': metadata.get('path'),
        'platforms': {}
    }
    
    for platform_name, platform_config in platforms.items():
        if platform_config.get('enabled', False):
            content = generate_social_content(metadata, platform_name, platform_config)
            if content:
                post_data['platforms'][platform_name] = content
    
    return post_data if post_data['platforms'] else None