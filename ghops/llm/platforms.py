"""
Platform integrations for publishing LLM-generated content.

Supports posting to various platforms:
- dev.to (Forem API)
- Twitter (future)
- LinkedIn (future)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import os
import logging

logger = logging.getLogger(__name__)


class PublishingPlatform(ABC):
    """Abstract base class for publishing platforms."""

    @abstractmethod
    def publish(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish content to the platform.

        Args:
            content: The content to publish (markdown, plaintext, etc.)
            metadata: Platform-specific metadata (title, tags, etc.)

        Returns:
            Dict with publication result (url, id, status, etc.)
        """
        pass

    @abstractmethod
    def create_draft(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft (unpublished) post.

        Args:
            content: The content to save as draft
            metadata: Platform-specific metadata

        Returns:
            Dict with draft result (url, id, status, etc.)
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this platform.

        Returns:
            Dict with platform details (name, endpoint, user, etc.)
        """
        pass


class DevToPlatform(PublishingPlatform):
    """
    dev.to (Forem) platform integration.

    Uses the Forem API to publish articles to dev.to.
    Requires a dev.to API key.

    API Docs: https://developers.forem.com/api/v1
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize dev.to platform.

        Args:
            api_key: dev.to API key (or use DEVTO_API_KEY env var)
                    Get one at: https://dev.to/settings/extensions
        """
        self.api_key = api_key or os.getenv('DEVTO_API_KEY')
        if not self.api_key:
            raise ValueError(
                "dev.to API key required. "
                "Set DEVTO_API_KEY environment variable or pass api_key parameter. "
                "Get your key at: https://dev.to/settings/extensions"
            )

        self.base_url = "https://dev.to/api"
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Verify API key works
        self._verify_connection()

    def _verify_connection(self):
        """Verify API key is valid."""
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/users/me",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            user_data = response.json()
            self.username = user_data.get('username', 'unknown')
            logger.info(f"Connected to dev.to as @{self.username}")

        except Exception as e:
            logger.error(f"Failed to connect to dev.to: {e}")
            raise ConnectionError(
                f"Cannot connect to dev.to API. "
                f"Check your API key. Error: {e}"
            )

    def publish(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish an article to dev.to.

        Args:
            content: Article content in Markdown
            metadata: Article metadata:
                - title: str (required) - Article title
                - tags: List[str] (optional) - Up to 4 tags
                - canonical_url: str (optional) - Canonical URL
                - series: str (optional) - Series name
                - published: bool (default True) - Publish immediately

        Returns:
            Dict with:
                - url: str - Article URL on dev.to
                - id: int - Article ID
                - status: str - 'published' or 'draft'
        """
        import requests

        # Build article payload
        article = {
            "title": metadata.get('title', 'Untitled'),
            "body_markdown": content,
            "published": metadata.get('published', True),
        }

        # Add optional fields
        if 'tags' in metadata:
            # dev.to allows up to 4 tags
            tags = metadata['tags'][:4]
            article['tags'] = tags

        if 'canonical_url' in metadata:
            article['canonical_url'] = metadata['canonical_url']

        if 'series' in metadata:
            article['series'] = metadata['series']

        if 'description' in metadata:
            article['description'] = metadata['description']

        # Make request
        try:
            response = requests.post(
                f"{self.base_url}/articles",
                headers=self.headers,
                json={"article": article},
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            article_url = result.get('url', f"https://dev.to/{self.username}")

            return {
                'url': article_url,
                'id': result.get('id'),
                'status': 'published' if article['published'] else 'draft',
                'platform': 'devto'
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to publish to dev.to: {e}")
            raise RuntimeError(f"dev.to API error: {e}")

    def create_draft(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft article on dev.to.

        Args:
            content: Article content in Markdown
            metadata: Article metadata (same as publish)

        Returns:
            Dict with draft result
        """
        # Force published=False
        metadata = metadata.copy()
        metadata['published'] = False

        return self.publish(content, metadata)

    def update_article(self, article_id: int, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing article.

        Args:
            article_id: The article ID to update
            content: New article content
            metadata: Updated metadata

        Returns:
            Dict with update result
        """
        import requests

        article = {
            "title": metadata.get('title'),
            "body_markdown": content,
            "published": metadata.get('published', True),
        }

        # Add optional fields
        if 'tags' in metadata:
            article['tags'] = metadata['tags'][:4]

        if 'canonical_url' in metadata:
            article['canonical_url'] = metadata['canonical_url']

        if 'series' in metadata:
            article['series'] = metadata['series']

        try:
            response = requests.put(
                f"{self.base_url}/articles/{article_id}",
                headers=self.headers,
                json={"article": article},
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            return {
                'url': result.get('url'),
                'id': result.get('id'),
                'status': 'updated',
                'platform': 'devto'
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update article {article_id}: {e}")
            raise RuntimeError(f"dev.to API error: {e}")

    def get_info(self) -> Dict[str, Any]:
        """Get platform information."""
        return {
            'platform': 'devto',
            'base_url': self.base_url,
            'username': getattr(self, 'username', 'unknown'),
            'supports_markdown': True,
            'supports_drafts': True,
            'max_tags': 4
        }

    def __repr__(self):
        username = getattr(self, 'username', 'unknown')
        return f"DevToPlatform(username='@{username}')"


def extract_title_from_markdown(content: str) -> Optional[str]:
    """
    Extract title from markdown content (first H1).

    Args:
        content: Markdown content

    Returns:
        Title string or None
    """
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('# '):
            return stripped[2:].strip()

    return None


def extract_tags_from_content(content: str, context: Any) -> List[str]:
    """
    Extract relevant tags from content and context.

    Args:
        content: Generated content
        context: ContentContext with project info

    Returns:
        List of tags (up to 4 for dev.to)
    """
    tags = []

    # Add language tag
    if hasattr(context, 'language') and context.language:
        lang = context.language.lower()
        tags.append(lang)

    # Add project-specific tags from topics
    if hasattr(context, 'topics') and context.topics:
        # Filter topics to common dev.to tags
        common_tags = ['python', 'javascript', 'typescript', 'rust', 'go',
                      'webdev', 'opensource', 'tutorial', 'productivity',
                      'devops', 'github', 'git', 'cli', 'automation']

        for topic in context.topics:
            topic_lower = topic.lower()
            if topic_lower in common_tags and topic_lower not in tags:
                tags.append(topic_lower)

    # Add generic tags if we don't have enough
    if len(tags) < 2:
        if hasattr(context, 'version'):
            tags.append('release')

    if len(tags) < 3:
        tags.append('opensource')

    return tags[:4]  # dev.to max is 4


class BlueskyPlatform(PublishingPlatform):
    """
    Bluesky (AT Protocol) platform integration.

    Uses the AT Protocol to post to Bluesky social network.
    Requires a handle and app password.

    API Docs: https://docs.bsky.app/
    """

    def __init__(self, handle: Optional[str] = None, app_password: Optional[str] = None):
        """
        Initialize Bluesky platform.

        Args:
            handle: Bluesky handle (e.g., "user.bsky.social")
            app_password: App password (not your main password!)
                         Generate at: Settings → App Passwords
        """
        self.handle = handle or os.getenv('BLUESKY_HANDLE')
        self.app_password = app_password or os.getenv('BLUESKY_APP_PASSWORD')

        if not self.handle or not self.app_password:
            raise ValueError(
                "Bluesky handle and app_password required. "
                "Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables "
                "or pass handle and app_password parameters. "
                "Generate app password at: https://bsky.app/settings/app-passwords"
            )

        # Initialize AT Protocol client
        try:
            from atproto import Client
        except ImportError:
            raise ImportError(
                "atproto package not installed. "
                "Install with: pip install atproto"
            )

        self.client = Client()
        self._login()

    def _login(self):
        """Login to Bluesky."""
        try:
            self.client.login(self.handle, self.app_password)
            logger.info(f"Connected to Bluesky as @{self.handle}")
        except Exception as e:
            logger.error(f"Failed to login to Bluesky: {e}")
            raise ConnectionError(
                f"Cannot login to Bluesky as @{self.handle}. "
                f"Check your handle and app password. Error: {e}"
            )

    def publish(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish a post to Bluesky.

        Args:
            content: Post content (max 300 chars)
            metadata: Post metadata (currently unused for Bluesky)

        Returns:
            Dict with publication result
        """
        try:
            # Bluesky has a 300 character limit
            if len(content) > 300:
                content = content[:297] + "..."
                logger.warning(f"Content truncated to 300 chars for Bluesky")

            # Send post
            response = self.client.send_post(text=content)

            return {
                'url': f"https://bsky.app/profile/{self.handle}/post/{response.uri.split('/')[-1]}",
                'id': response.uri,
                'status': 'published',
                'platform': 'bluesky'
            }

        except Exception as e:
            logger.error(f"Failed to publish to Bluesky: {e}")
            raise RuntimeError(f"Bluesky API error: {e}")

    def create_draft(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bluesky doesn't support drafts, so this just returns a message.

        Args:
            content: Post content
            metadata: Post metadata

        Returns:
            Dict indicating drafts aren't supported
        """
        return {
            'status': 'error',
            'message': 'Bluesky does not support drafts. Use publish instead.',
            'platform': 'bluesky'
        }

    def get_info(self) -> Dict[str, Any]:
        """Get platform information."""
        return {
            'platform': 'bluesky',
            'handle': self.handle,
            'max_length': 300,
            'supports_drafts': False,
            'supports_markdown': False
        }

    def __repr__(self):
        return f"BlueskyPlatform(handle='@{self.handle}')"


class MastodonPlatform(PublishingPlatform):
    """
    Mastodon platform integration.

    Works with any Mastodon instance or compatible service (Pleroma, etc.).
    Requires an instance URL and access token.

    API Docs: https://docs.joinmastodon.org/api/
    """

    def __init__(self, instance_url: Optional[str] = None,
                 access_token: Optional[str] = None):
        """
        Initialize Mastodon platform.

        Args:
            instance_url: Mastodon instance URL (e.g., "https://mastodon.social")
            access_token: Access token for your account
                         Generate at: Settings → Development → New Application
        """
        self.instance_url = instance_url or os.getenv('MASTODON_INSTANCE_URL')
        self.access_token = access_token or os.getenv('MASTODON_ACCESS_TOKEN')

        if not self.instance_url or not self.access_token:
            raise ValueError(
                "Mastodon instance_url and access_token required. "
                "Set MASTODON_INSTANCE_URL and MASTODON_ACCESS_TOKEN environment variables "
                "or pass instance_url and access_token parameters. "
                "Generate token at: https://YOUR_INSTANCE/settings/applications"
            )

        # Initialize Mastodon client
        try:
            from mastodon import Mastodon
        except ImportError:
            raise ImportError(
                "Mastodon.py package not installed. "
                "Install with: pip install Mastodon.py"
            )

        self.client = Mastodon(
            access_token=self.access_token,
            api_base_url=self.instance_url
        )

        # Verify connection
        self._verify_connection()

    def _verify_connection(self):
        """Verify we can connect to Mastodon."""
        try:
            account = self.client.account_verify_credentials()
            self.username = account['username']
            logger.info(f"Connected to Mastodon as @{self.username}@{self.instance_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Mastodon: {e}")
            raise ConnectionError(
                f"Cannot connect to Mastodon at {self.instance_url}. "
                f"Check your access token. Error: {e}"
            )

    def publish(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish a post (toot) to Mastodon.

        Args:
            content: Post content (max 500 chars by default)
            metadata: Post metadata:
                - visibility: str (public, unlisted, private, direct)
                - sensitive: bool (mark as sensitive)
                - spoiler_text: str (content warning)

        Returns:
            Dict with publication result
        """
        try:
            # Get instance config for char limit
            instance = self.client.instance()
            max_chars = instance.get('max_toot_chars', 500)

            # Truncate if needed
            if len(content) > max_chars:
                content = content[:max_chars-3] + "..."
                logger.warning(f"Content truncated to {max_chars} chars for Mastodon")

            # Build status params
            status_params = {
                'status': content,
                'visibility': metadata.get('visibility', 'public'),
            }

            if 'sensitive' in metadata:
                status_params['sensitive'] = metadata['sensitive']

            if 'spoiler_text' in metadata:
                status_params['spoiler_text'] = metadata['spoiler_text']

            # Post status
            status = self.client.status_post(**status_params)

            return {
                'url': status['url'],
                'id': status['id'],
                'status': 'published',
                'platform': 'mastodon'
            }

        except Exception as e:
            logger.error(f"Failed to publish to Mastodon: {e}")
            raise RuntimeError(f"Mastodon API error: {e}")

    def create_draft(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft by posting with 'private' visibility.

        Args:
            content: Post content
            metadata: Post metadata

        Returns:
            Dict with draft result
        """
        # Mastodon doesn't have true drafts, but we can post as 'private'
        metadata = metadata.copy()
        metadata['visibility'] = 'private'

        result = self.publish(content, metadata)
        result['status'] = 'draft'

        return result

    def get_info(self) -> Dict[str, Any]:
        """Get platform information."""
        try:
            instance = self.client.instance()
            max_chars = instance.get('max_toot_chars', 500)
        except:
            max_chars = 500

        return {
            'platform': 'mastodon',
            'instance_url': self.instance_url,
            'username': getattr(self, 'username', 'unknown'),
            'max_length': max_chars,
            'supports_drafts': True,  # via private visibility
            'supports_markdown': False
        }

    def __repr__(self):
        username = getattr(self, 'username', 'unknown')
        return f"MastodonPlatform(username='@{username}@{self.instance_url}')"


def get_publishing_platform(config: Dict[str, Any]) -> PublishingPlatform:
    """
    Factory function to get configured publishing platform.

    Args:
        config: Configuration dict with llm/platform settings

    Returns:
        Configured publishing platform instance

    Example config:
        {
            "llm": {
                "publishing": {
                    "default_platform": "devto",
                    "platforms": {
                        "devto": {
                            "api_key": "..."
                        }
                    }
                }
            }
        }
    """
    llm_config = config.get('llm', {})
    publishing_config = llm_config.get('publishing', {})

    platform_name = publishing_config.get('default_platform', 'devto')
    platform_config = publishing_config.get('platforms', {}).get(platform_name, {})

    if platform_name == 'devto':
        return DevToPlatform(
            api_key=platform_config.get('api_key')
        )
    elif platform_name == 'bluesky':
        return BlueskyPlatform(
            handle=platform_config.get('handle'),
            app_password=platform_config.get('app_password')
        )
    elif platform_name == 'mastodon':
        return MastodonPlatform(
            instance_url=platform_config.get('instance_url'),
            access_token=platform_config.get('access_token')
        )
    else:
        raise ValueError(
            f"Unknown publishing platform: {platform_name}. "
            f"Supported platforms: devto, bluesky, mastodon"
        )
