"""Tests for social.py module."""

import pytest
from ghops.social import (
    generate_social_content,
    generate_hashtags,
    get_default_template,
    post_to_twitter,
    post_to_linkedin,
    post_to_mastodon
)


class TestSocialContent:
    """Test social media content generation."""
    
    @pytest.fixture
    def sample_repo(self):
        """Sample repository metadata."""
        return {
            'name': 'test-project',
            'description': 'A test project for unit testing',
            'language': 'Python',
            'stargazers_count': 100,
            'topics': ['testing', 'python', 'automation'],
            'owner': 'testuser',
            'homepage': 'https://example.com/test-project'
        }
    
    @pytest.fixture
    def platform_config(self):
        """Sample platform configuration."""
        return {
            'enabled': True,
            'hashtags': ['#opensource', '#coding']
        }
    
    def test_get_default_template(self):
        """Test default template retrieval."""
        # Known platforms
        twitter_template = get_default_template('twitter')
        assert '{{repo_name}}' in twitter_template
        assert '{{stars}}' in twitter_template
        
        linkedin_template = get_default_template('linkedin')
        assert '{{repo_name}}' in linkedin_template
        assert '{{language}}' in linkedin_template
        
        mastodon_template = get_default_template('mastodon')
        assert '{{repo_name}}' in mastodon_template
        
        # Unknown platform
        unknown_template = get_default_template('unknown')
        assert '{{repo_name}}' in unknown_template
    
    def test_generate_hashtags(self, sample_repo, platform_config):
        """Test hashtag generation."""
        hashtags = generate_hashtags(sample_repo, platform_config)
        
        # Should include language hashtag
        assert '#python' in hashtags
        
        # Should include topic hashtags (without hyphens)
        assert any('#testing' in tag for tag in hashtags)
        
        # Should include common hashtags
        assert '#opensource' in hashtags
        
        # Should be limited to 5 hashtags
        assert len(hashtags) <= 5
        
        # Should be unique
        assert len(hashtags) == len(set(hashtags))
    
    def test_generate_social_content_twitter(self, sample_repo, platform_config):
        """Test Twitter content generation."""
        content = generate_social_content(sample_repo, 'twitter', platform_config)
        
        # Should contain repo name and description
        assert 'test-project' in content
        assert 'test project for unit testing' in content
        
        # Should contain stars
        assert '100' in content
        
        # Should contain hashtags
        assert '#' in content
        
        # Should be within Twitter length limit
        assert len(content) <= 280
    
    def test_generate_social_content_linkedin(self, sample_repo, platform_config):
        """Test LinkedIn content generation."""
        content = generate_social_content(sample_repo, 'linkedin', platform_config)
        
        # Should contain repo details
        assert 'test-project' in content
        assert 'Python' in content
        assert '100 stars' in content
        
        # LinkedIn allows longer content
        assert len(content) > 100
    
    def test_generate_social_content_custom_template(self, sample_repo):
        """Test content generation with custom template."""
        custom_config = {
            'enabled': True,
            'template': 'Check out {{repo_name}} by {{owner}}!'
        }
        
        content = generate_social_content(sample_repo, 'custom', custom_config)
        assert content == 'Check out test-project by testuser!'
    
    def test_generate_social_content_missing_fields(self):
        """Test content generation with missing fields."""
        minimal_repo = {
            'name': 'minimal-repo'
        }
        
        config = {'enabled': True}
        content = generate_social_content(minimal_repo, 'twitter', config)
        
        # Should handle missing fields gracefully
        assert 'minimal-repo' in content
        assert 'Unknown' in content  # Default for missing language
        assert '0' in content  # Default for missing stars


class TestSocialPosting:
    """Test social media posting functions."""
    
    def test_post_to_twitter_dry_run(self):
        """Test Twitter posting in dry run mode."""
        result = post_to_twitter("Test content", {}, dry_run=True)
        
        assert result['platform'] == 'twitter'
        assert result['status'] == 'success'
        assert result['details']['dry_run'] is True
        assert result['details']['content'] == "Test content"
    
    def test_post_to_twitter_missing_credentials(self):
        """Test Twitter posting with missing credentials."""
        result = post_to_twitter("Test content", {}, dry_run=False)
        
        assert result['platform'] == 'twitter'
        assert result['status'] == 'error'
        assert 'Missing Twitter API credentials' in result['error']
    
    def test_post_to_linkedin_dry_run(self):
        """Test LinkedIn posting in dry run mode."""
        result = post_to_linkedin("Test content", {}, dry_run=True)
        
        assert result['platform'] == 'linkedin'
        assert result['status'] == 'success'
        assert result['details']['dry_run'] is True
        assert result['details']['content'] == "Test content"
    
    def test_post_to_linkedin_missing_credentials(self):
        """Test LinkedIn posting with missing credentials."""
        result = post_to_linkedin("Test content", {}, dry_run=False)
        
        assert result['platform'] == 'linkedin'
        assert result['status'] == 'error'
        assert 'Missing LinkedIn API credentials' in result['error']
    
    def test_post_to_mastodon_dry_run(self):
        """Test Mastodon posting in dry run mode."""
        result = post_to_mastodon("Test content", {}, dry_run=True)
        
        assert result['platform'] == 'mastodon'
        assert result['status'] == 'success'
        assert result['details']['dry_run'] is True
        assert result['details']['content'] == "Test content"
    
    def test_post_to_mastodon_missing_credentials(self):
        """Test Mastodon posting with missing credentials."""
        result = post_to_mastodon("Test content", {}, dry_run=False)
        
        assert result['platform'] == 'mastodon'
        assert result['status'] == 'error'
        assert 'Missing Mastodon access token' in result['error']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])