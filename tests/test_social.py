"""
Unit tests for ghops.social module
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.social import (
    create_social_media_posts,
    execute_social_media_posts,
    format_post_content,
    post_to_twitter,
    post_to_linkedin,
    post_to_mastodon
)


class TestSocialMediaPosts(unittest.TestCase):
    """Test social media post generation and execution"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create fake repositories
        for i in range(3):
            repo_dir = os.path.join(self.temp_dir, f"test_repo_{i}")
            os.makedirs(repo_dir)
            os.makedirs(os.path.join(repo_dir, ".git"))
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.social.config')
    @patch('ghops.social.sample_repositories_for_social_media')
    def test_create_social_media_posts(self, mock_sample, mock_config):
        """Test social media post creation"""
        # Mock configuration with enabled platforms
        mock_config.get.return_value = {
            'platforms': {
                'twitter': {
                    'enabled': True,
                    'templates': {
                        'pypi_release': 'New release: {package_name} v{version}',
                        'github_pages': 'Updated docs: {pages_url}',
                        'random_highlight': 'Working on {repo_name}'
                    }
                }
            }
        }
        
        # Mock sampled repositories
        mock_sample.return_value = [
            {
                'name': 'test_repo_1',
                'license': 'MIT',
                'pages_url': 'https://user.github.io/test_repo_1/',
                'has_package': True,
                'is_published': True,
                'pypi_info': {
                    'package_name': 'test-package',
                    'is_published': True,
                    'pypi_info': {
                        'version': '1.0.0',
                        'url': 'https://pypi.org/project/test-package/'
                    }
                }
            },
            {
                'name': 'test_repo_2',
                'license': 'Apache-2.0',
                'pages_url': None,
                'has_package': False,
                'is_published': False,
                'pypi_info': None
            }
        ]
        
        repo_dirs = ['test_repo_1', 'test_repo_2']
        posts = create_social_media_posts(repo_dirs, self.temp_dir, 2)
        
        self.assertIsInstance(posts, list)
        self.assertGreater(len(posts), 0)
        
        # Check post structure
        for post in posts:
            self.assertIn('content', post)
            self.assertIn('platform', post)
            self.assertIn('repo_name', post)
    
    def test_format_post_content_basic(self):
        """Test post content formatting with basic template"""
        repo_info = {
            'name': 'awesome-project',
            'license': 'MIT',
            'pages_url': None,
            'has_package': False,
            'is_published': False,
            'pypi_info': None
        }
        
        template = "Check out {repo_name}! It's a {license} project. {repo_url}"
        content = format_post_content(template, repo_info)
        
        self.assertIn('awesome-project', content)
        self.assertIn('MIT', content)
        self.assertIn('github.com', content)
    
    def test_format_post_content_with_package(self):
        """Test post content formatting for repository with package"""
        repo_info = {
            'name': 'awesome-project',
            'license': 'MIT',
            'pages_url': 'https://user.github.io/awesome-project/',
            'has_package': True,
            'is_published': True,
            'pypi_info': {
                'package_name': 'awesome-package',
                'is_published': True,
                'pypi_info': {
                    'version': '1.0.0',
                    'url': 'https://pypi.org/project/awesome-package/'
                }
            }
        }
        
        template = "🚀 {package_name} v{version} is available! {pypi_url}"
        content = format_post_content(template, repo_info)
        
        self.assertIn('awesome-package', content)
        self.assertIn('1.0.0', content)
        self.assertIn('pypi.org', content)
    
    @patch('ghops.social.post_to_twitter')
    @patch('ghops.social.post_to_linkedin')
    @patch('ghops.social.post_to_mastodon')
    def test_execute_social_media_posts_dry_run(self, mock_mastodon, mock_linkedin, mock_twitter):
        """Test social media post execution in dry-run mode"""
        posts = [
            {
                'content': 'Test post content',
                'platforms': ['twitter', 'linkedin'],
                'repo_info': {'name': 'test_repo'}
            }
        ]
        
        result = execute_social_media_posts(posts, dry_run=True)
        
        # In dry-run mode, no actual posting should occur
        mock_twitter.assert_not_called()
        mock_linkedin.assert_not_called()
        mock_mastodon.assert_not_called()
        
        # Should return count of posts that would be executed
        self.assertEqual(result, 2)  # 2 platforms = 2 executions
    
    @patch('ghops.social.post_to_twitter')
    @patch('ghops.social.post_to_linkedin')
    @patch('ghops.social.post_to_mastodon')
    @patch('ghops.social.config')
    def test_execute_social_media_posts_real(self, mock_config, mock_mastodon, mock_linkedin, mock_twitter):
        """Test social media post execution in real mode"""
        mock_twitter.return_value = True
        mock_linkedin.return_value = True
        
        # Mock config to enable platforms
        mock_config.get.return_value = {
            'platforms': {
                'twitter': {'enabled': True},
                'linkedin': {'enabled': True}
            }
        }
        
        posts = [
            {
                'content': 'Test post content',
                'platforms': ['twitter', 'linkedin'],
                'repo_info': {'name': 'test_repo'}
            }
        ]
        
        result = execute_social_media_posts(posts, dry_run=False)
        
        # Should call posting functions
        mock_twitter.assert_called_once()
        mock_linkedin.assert_called_once()
        mock_mastodon.assert_not_called()  # Not in platforms list
        
        self.assertEqual(result, 2)  # 2 platforms = 2 executions


class TestSocialMediaAPIs(unittest.TestCase):
    """Test social media API functions"""
    
    def test_post_to_twitter_stub(self):
        """Test Twitter posting stub"""
        result = post_to_twitter("Test tweet content", {})
        
        # Since it's a stub, should return True
        self.assertTrue(result)
    
    def test_post_to_linkedin_stub(self):
        """Test LinkedIn posting stub"""
        result = post_to_linkedin("Test LinkedIn content", {})
        
        # Since it's a stub, should return True
        self.assertTrue(result)
    
    def test_post_to_mastodon_stub(self):
        """Test Mastodon posting stub"""
        result = post_to_mastodon("Test Mastodon content", {})
        
        # Since it's a stub, should return True
        self.assertTrue(result)


class TestPostContentFormatting(unittest.TestCase):
    """Test post content formatting variations"""
    
    def test_missing_variable_handling(self):
        """Test handling of missing variables in template"""
        repo_info = {
            'name': 'test-repo',
            'license': 'MIT'
        }
        
        # Template with missing variable
        template = "Check out {repo_name}! Version {version} is awesome!"
        
        # Should handle gracefully (may return None or partial content)
        content = format_post_content(template, repo_info)
        
        # The exact behavior depends on implementation
        # This test verifies the function doesn't crash
        self.assertIsNotNone(content)
    
    def test_content_with_pages_url(self):
        """Test content formatting with GitHub Pages URL"""
        repo_info = {
            'name': 'docs-site',
            'license': 'MIT',
            'pages_url': 'https://user.github.io/docs-site/'
        }
        
        template = "📖 Documentation for {repo_name}: {pages_url}"
        content = format_post_content(template, repo_info)
        
        self.assertIn('docs-site', content)
        self.assertIn('github.io', content)


if __name__ == '__main__':
    unittest.main()
