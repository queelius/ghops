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
    content = content.replace('{{owner}}', metadata.get('owner', ''))
    
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


def post_to_twitter(content: str, config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Post content to Twitter/X.
    
    Args:
        content: Post content
        config: Twitter configuration
        dry_run: If True, don't actually post
        
    Returns:
        Result dictionary with status and details
    """
    result = {
        'platform': 'twitter',
        'status': 'success',
        'details': {}
    }
    
    if dry_run:
        result['details']['dry_run'] = True
        result['details']['content'] = content
        return result
    
    try:
        # Check for required credentials
        api_key = config.get('api_key') or config.get('consumer_key')
        api_secret = config.get('api_secret') or config.get('consumer_secret')
        access_token = config.get('access_token')
        access_token_secret = config.get('access_token_secret')
        
        if not all([api_key, api_secret, access_token, access_token_secret]):
            result['status'] = 'error'
            result['error'] = 'Missing Twitter API credentials'
            return result
        
        # Use tweepy for Twitter API
        try:
            import tweepy
        except ImportError:
            result['status'] = 'error'
            result['error'] = 'tweepy not installed. Run: pip install tweepy'
            return result
        
        # Authenticate
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        
        # Create API object
        api = tweepy.API(auth)
        
        # Post tweet
        tweet = api.update_status(content)
        
        result['details']['tweet_id'] = tweet.id_str
        result['details']['url'] = f"https://twitter.com/user/status/{tweet.id_str}"
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


def post_to_linkedin(content: str, config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Post content to LinkedIn.
    
    Args:
        content: Post content
        config: LinkedIn configuration
        dry_run: If True, don't actually post
        
    Returns:
        Result dictionary with status and details
    """
    result = {
        'platform': 'linkedin',
        'status': 'success',
        'details': {}
    }
    
    if dry_run:
        result['details']['dry_run'] = True
        result['details']['content'] = content
        return result
    
    try:
        # Check for required credentials
        access_token = config.get('access_token')
        person_urn = config.get('person_urn') or config.get('author_urn')
        
        if not all([access_token, person_urn]):
            result['status'] = 'error'
            result['error'] = 'Missing LinkedIn API credentials (access_token and person_urn required)'
            return result
        
        import requests
        
        # LinkedIn API endpoint
        url = "https://api.linkedin.com/v2/ugcPosts"
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0'
        }
        
        # Prepare post data
        post_data = {
            "author": f"urn:li:person:{person_urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        # Make the request
        response = requests.post(url, headers=headers, json=post_data)
        
        if response.status_code == 201:
            result['details']['post_id'] = response.headers.get('x-linkedin-id')
            result['details']['response'] = response.json()
        else:
            result['status'] = 'error'
            result['error'] = f"LinkedIn API error: {response.status_code} - {response.text}"
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


def post_to_mastodon(content: str, config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Post content to Mastodon.
    
    Args:
        content: Post content
        config: Mastodon configuration
        dry_run: If True, don't actually post
        
    Returns:
        Result dictionary with status and details
    """
    result = {
        'platform': 'mastodon',
        'status': 'success',
        'details': {}
    }
    
    if dry_run:
        result['details']['dry_run'] = True
        result['details']['content'] = content
        return result
    
    try:
        # Check for required credentials
        instance_url = config.get('instance_url', 'https://mastodon.social')
        access_token = config.get('access_token')
        
        if not access_token:
            result['status'] = 'error'
            result['error'] = 'Missing Mastodon access token'
            return result
        
        import requests
        
        # Mastodon API endpoint
        url = f"{instance_url}/api/v1/statuses"
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Prepare post data
        post_data = {
            'status': content,
            'visibility': config.get('visibility', 'public')
        }
        
        # Make the request
        response = requests.post(url, headers=headers, json=post_data)
        
        if response.status_code == 200:
            data = response.json()
            result['details']['toot_id'] = data.get('id')
            result['details']['url'] = data.get('url')
        else:
            result['status'] = 'error'
            result['error'] = f"Mastodon API error: {response.status_code} - {response.text}"
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


# Platform posting functions
PLATFORM_POSTERS = {
    'twitter': post_to_twitter,
    'linkedin': post_to_linkedin,
    'mastodon': post_to_mastodon
}