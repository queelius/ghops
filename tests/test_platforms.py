"""
Tests for llm/platforms.py module.

Tests the platform integrations including:
- BlueskyPlatform (AT Protocol)
- MastodonPlatform (Mastodon API)
- Platform initialization and authentication
- Publishing and draft creation
- Character limit handling
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from ghops.llm.platforms import (
    DevToPlatform,
    get_publishing_platform,
    extract_title_from_markdown,
    extract_tags_from_content
)

# Try to import actual dependencies, skip tests if not installed
try:
    import atproto
    HAS_BLUESKY = True
except (ImportError, ModuleNotFoundError):
    HAS_BLUESKY = False

try:
    import mastodon
    HAS_MASTODON = True
except (ImportError, ModuleNotFoundError):
    HAS_MASTODON = False

# Import platform classes if available (they use lazy imports of the dependencies)
if HAS_BLUESKY:
    from ghops.llm.platforms import BlueskyPlatform
if HAS_MASTODON:
    from ghops.llm.platforms import MastodonPlatform


@pytest.mark.skipif(not HAS_BLUESKY, reason="Bluesky dependencies not installed (atproto)")
class TestBlueskyPlatform:
    """Test BlueskyPlatform integration."""

    @patch('atproto.Client')
    def test_initialization_success(self, mock_client_class):
        """Test successful Bluesky platform initialization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='test-password'
        )

        assert platform.handle == 'user.bsky.social'
        assert platform.app_password == 'test-password'
        mock_client.login.assert_called_once_with('user.bsky.social', 'test-password')

    @patch('ghops.llm.platforms.Client')
    def test_initialization_from_env(self, mock_client_class, monkeypatch):
        """Test initialization from environment variables."""
        monkeypatch.setenv('BLUESKY_HANDLE', 'env.bsky.social')
        monkeypatch.setenv('BLUESKY_APP_PASSWORD', 'env-password')

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform()

        assert platform.handle == 'env.bsky.social'
        assert platform.app_password == 'env-password'

    def test_initialization_missing_credentials(self):
        """Test that missing credentials raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            BlueskyPlatform(handle=None, app_password=None)

        assert 'handle and app_password required' in str(exc_info.value)

    def test_initialization_missing_handle(self):
        """Test that missing handle raises ValueError."""
        with pytest.raises(ValueError):
            BlueskyPlatform(handle=None, app_password='password')

    @patch('ghops.llm.platforms.Client')
    def test_login_failure(self, mock_client_class):
        """Test that login failures raise ConnectionError."""
        mock_client = MagicMock()
        mock_client.login.side_effect = Exception("Invalid credentials")
        mock_client_class.return_value = mock_client

        with pytest.raises(ConnectionError) as exc_info:
            BlueskyPlatform(
                handle='user.bsky.social',
                app_password='wrong-password'
            )

        assert 'Cannot login to Bluesky' in str(exc_info.value)

    @patch('ghops.llm.platforms.Client')
    def test_publish_short_post(self, mock_client_class):
        """Test publishing a short post."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.uri = 'at://did:plc:user/app.bsky.feed.post/abc123'
        mock_client.send_post.return_value = mock_response
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='password'
        )

        result = platform.publish('Test post content', {})

        assert result['status'] == 'published'
        assert result['platform'] == 'bluesky'
        assert 'abc123' in result['url']
        mock_client.send_post.assert_called_once_with(text='Test post content')

    @patch('ghops.llm.platforms.Client')
    def test_publish_truncates_long_content(self, mock_client_class):
        """Test that content over 300 chars is truncated."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.uri = 'at://did:plc:user/app.bsky.feed.post/abc123'
        mock_client.send_post.return_value = mock_response
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='password'
        )

        long_content = 'A' * 400  # 400 characters
        result = platform.publish(long_content, {})

        # Should be truncated to 300 chars (297 + "...")
        call_args = mock_client.send_post.call_args
        posted_text = call_args[1]['text']
        assert len(posted_text) == 300
        assert posted_text.endswith('...')

    @patch('ghops.llm.platforms.Client')
    def test_publish_failure(self, mock_client_class):
        """Test publish error handling."""
        mock_client = MagicMock()
        mock_client.send_post.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='password'
        )

        with pytest.raises(RuntimeError) as exc_info:
            platform.publish('Test post', {})

        assert 'Bluesky API error' in str(exc_info.value)

    @patch('ghops.llm.platforms.Client')
    def test_create_draft_not_supported(self, mock_client_class):
        """Test that Bluesky doesn't support drafts."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='password'
        )

        result = platform.create_draft('Draft content', {})

        assert result['status'] == 'error'
        assert 'does not support drafts' in result['message']

    @patch('ghops.llm.platforms.Client')
    def test_get_info(self, mock_client_class):
        """Test getting platform info."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        platform = BlueskyPlatform(
            handle='user.bsky.social',
            app_password='password'
        )

        info = platform.get_info()

        assert info['platform'] == 'bluesky'
        assert info['handle'] == 'user.bsky.social'
        assert info['max_length'] == 300
        assert info['supports_drafts'] is False
        assert info['supports_markdown'] is False


@pytest.mark.skipif(not HAS_MASTODON, reason="Mastodon dependencies not installed (Mastodon.py)")
class TestMastodonPlatform:
    """Test MastodonPlatform integration."""

    @patch('ghops.llm.platforms.Mastodon')
    def test_initialization_success(self, mock_mastodon_class):
        """Test successful Mastodon platform initialization."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='test-token'
        )

        assert platform.instance_url == 'https://mastodon.social'
        assert platform.access_token == 'test-token'
        assert platform.username == 'testuser'

    @patch('ghops.llm.platforms.Mastodon')
    def test_initialization_from_env(self, mock_mastodon_class, monkeypatch):
        """Test initialization from environment variables."""
        monkeypatch.setenv('MASTODON_INSTANCE_URL', 'https://mastodon.example')
        monkeypatch.setenv('MASTODON_ACCESS_TOKEN', 'env-token')

        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'envuser'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform()

        assert platform.instance_url == 'https://mastodon.example'
        assert platform.access_token == 'env-token'

    def test_initialization_missing_credentials(self):
        """Test that missing credentials raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MastodonPlatform(instance_url=None, access_token=None)

        assert 'instance_url and access_token required' in str(exc_info.value)

    @patch('ghops.llm.platforms.Mastodon')
    def test_connection_verification_failure(self, mock_mastodon_class):
        """Test connection verification failure."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.side_effect = Exception("Invalid token")
        mock_mastodon_class.return_value = mock_client

        with pytest.raises(ConnectionError) as exc_info:
            MastodonPlatform(
                instance_url='https://mastodon.social',
                access_token='invalid-token'
            )

        assert 'Cannot connect to Mastodon' in str(exc_info.value)

    @patch('ghops.llm.platforms.Mastodon')
    def test_publish_short_post(self, mock_mastodon_class):
        """Test publishing a short post."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.return_value = {
            'id': '123456',
            'url': 'https://mastodon.social/@testuser/123456'
        }
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        result = platform.publish('Test toot content', {})

        assert result['status'] == 'published'
        assert result['platform'] == 'mastodon'
        assert result['id'] == '123456'
        assert 'mastodon.social' in result['url']

    @patch('ghops.llm.platforms.Mastodon')
    def test_publish_with_visibility(self, mock_mastodon_class):
        """Test publishing with custom visibility."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.return_value = {'id': '123', 'url': 'https://example.com/123'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        platform.publish('Private toot', {'visibility': 'private'})

        call_args = mock_client.status_post.call_args
        assert call_args[1]['visibility'] == 'private'

    @patch('ghops.llm.platforms.Mastodon')
    def test_publish_truncates_long_content(self, mock_mastodon_class):
        """Test that content over instance limit is truncated."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.return_value = {'id': '123', 'url': 'https://example.com/123'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        long_content = 'A' * 600  # 600 characters, over 500 limit
        platform.publish(long_content, {})

        call_args = mock_client.status_post.call_args
        posted_text = call_args[1]['status']
        assert len(posted_text) == 500
        assert posted_text.endswith('...')

    @patch('ghops.llm.platforms.Mastodon')
    def test_publish_with_content_warning(self, mock_mastodon_class):
        """Test publishing with content warning (spoiler text)."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.return_value = {'id': '123', 'url': 'https://example.com/123'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        platform.publish(
            'Sensitive content',
            {'spoiler_text': 'CW: Tech', 'sensitive': True}
        )

        call_args = mock_client.status_post.call_args
        assert call_args[1]['spoiler_text'] == 'CW: Tech'
        assert call_args[1]['sensitive'] is True

    @patch('ghops.llm.platforms.Mastodon')
    def test_create_draft(self, mock_mastodon_class):
        """Test creating a draft (private visibility)."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.return_value = {'id': '123', 'url': 'https://example.com/123'}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        result = platform.create_draft('Draft toot', {})

        # Should post as private
        call_args = mock_client.status_post.call_args
        assert call_args[1]['visibility'] == 'private'
        assert result['status'] == 'draft'

    @patch('ghops.llm.platforms.Mastodon')
    def test_publish_failure(self, mock_mastodon_class):
        """Test publish error handling."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_client.status_post.side_effect = Exception("API error")
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        with pytest.raises(RuntimeError) as exc_info:
            platform.publish('Test toot', {})

        assert 'Mastodon API error' in str(exc_info.value)

    @patch('ghops.llm.platforms.Mastodon')
    def test_get_info(self, mock_mastodon_class):
        """Test getting platform info."""
        mock_client = MagicMock()
        mock_client.account_verify_credentials.return_value = {'username': 'testuser'}
        mock_client.instance.return_value = {'max_toot_chars': 500}
        mock_mastodon_class.return_value = mock_client

        platform = MastodonPlatform(
            instance_url='https://mastodon.social',
            access_token='token'
        )

        info = platform.get_info()

        assert info['platform'] == 'mastodon'
        assert info['instance_url'] == 'https://mastodon.social'
        assert info['username'] == 'testuser'
        assert info['max_length'] == 500
        assert info['supports_drafts'] is True
        assert info['supports_markdown'] is False


class TestDevToPlatform:
    """Test DevToPlatform integration (already exists, add edge cases)."""

    @patch('requests.post')
    @patch('requests.get')
    def test_publish_with_all_metadata(self, mock_get, mock_post):
        """Test publishing with all optional metadata."""
        # Mock API responses
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'username': 'testuser'}
        )
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {
                'id': 12345,
                'url': 'https://dev.to/testuser/article-12345'
            }
        )

        platform = DevToPlatform(api_key='test-key')

        result = platform.publish(
            content='# Test Article\n\nContent here',
            metadata={
                'title': 'Test Article',
                'tags': ['python', 'testing', 'ci', 'devops'],
                'canonical_url': 'https://example.com/article',
                'series': 'Testing Series',
                'description': 'A test article',
                'published': True
            }
        )

        assert result['status'] == 'published'
        assert result['platform'] == 'devto'

        # Verify API call
        call_args = mock_post.call_args
        article_data = call_args[1]['json']['article']
        assert article_data['title'] == 'Test Article'
        assert len(article_data['tags']) == 4
        assert article_data['canonical_url'] == 'https://example.com/article'


class TestPlatformFactory:
    """Test get_publishing_platform factory function."""

    @patch('ghops.llm.platforms.DevToPlatform')
    def test_get_devto_platform(self, mock_platform_class):
        """Test getting DevToPlatform from config."""
        config = {
            'llm': {
                'publishing': {
                    'default_platform': 'devto',
                    'platforms': {
                        'devto': {'api_key': 'test-key'}
                    }
                }
            }
        }

        get_publishing_platform(config)

        mock_platform_class.assert_called_once_with(api_key='test-key')

    @patch('ghops.llm.platforms.BlueskyPlatform')
    def test_get_bluesky_platform(self, mock_platform_class):
        """Test getting BlueskyPlatform from config."""
        config = {
            'llm': {
                'publishing': {
                    'default_platform': 'bluesky',
                    'platforms': {
                        'bluesky': {
                            'handle': 'user.bsky.social',
                            'app_password': 'password'
                        }
                    }
                }
            }
        }

        get_publishing_platform(config)

        mock_platform_class.assert_called_once_with(
            handle='user.bsky.social',
            app_password='password'
        )

    @patch('ghops.llm.platforms.MastodonPlatform')
    def test_get_mastodon_platform(self, mock_platform_class):
        """Test getting MastodonPlatform from config."""
        config = {
            'llm': {
                'publishing': {
                    'default_platform': 'mastodon',
                    'platforms': {
                        'mastodon': {
                            'instance_url': 'https://mastodon.social',
                            'access_token': 'token'
                        }
                    }
                }
            }
        }

        get_publishing_platform(config)

        mock_platform_class.assert_called_once_with(
            instance_url='https://mastodon.social',
            access_token='token'
        )

    def test_get_unknown_platform(self):
        """Test that unknown platform raises ValueError."""
        config = {
            'llm': {
                'publishing': {
                    'default_platform': 'unknown',
                    'platforms': {}
                }
            }
        }

        with pytest.raises(ValueError) as exc_info:
            get_publishing_platform(config)

        assert 'Unknown publishing platform' in str(exc_info.value)


class TestUtilityFunctions:
    """Test utility functions for content extraction."""

    def test_extract_title_from_markdown(self):
        """Test extracting title from markdown content."""
        content = """# My Great Article

        This is the content of the article.

        ## Section 1
        More content here.
        """

        title = extract_title_from_markdown(content)
        assert title == 'My Great Article'

    def test_extract_title_no_h1(self):
        """Test extracting title when no H1 exists."""
        content = """## Section Title

        Content without H1.
        """

        title = extract_title_from_markdown(content)
        assert title is None

    def test_extract_title_with_whitespace(self):
        """Test title extraction handles whitespace."""
        content = """

        #   Title with Spaces

        Content here.
        """

        title = extract_title_from_markdown(content)
        assert title == 'Title with Spaces'

    def test_extract_tags_from_content(self):
        """Test extracting tags from content and context."""
        context = MagicMock()
        context.language = 'Python'
        context.topics = ['testing', 'automation', 'ci']

        tags = extract_tags_from_content('Some content', context)

        assert 'python' in tags
        assert len(tags) <= 4  # dev.to max

    def test_extract_tags_with_version(self):
        """Test that 'release' tag is added when version present."""
        context = MagicMock()
        context.language = None
        context.topics = []
        context.version = '1.0.0'

        tags = extract_tags_from_content('Content', context)

        assert 'release' in tags or 'opensource' in tags


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
