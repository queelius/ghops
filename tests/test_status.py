"""
Unit tests for ghops.commands.status module
"""
import unittest
import tempfile
import os
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from ghops.commands.status import (
    get_gh_pages_url,
    get_license_info,
    display_repo_status_table,
    sample_repositories_for_social_media
)


class TestGetLicenseInfo(unittest.TestCase):
    """Test license detection functionality"""
    
    def setUp(self):
        """Set up test directory"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.temp_dir)
    
    def test_mit_license_detection(self):
        """Test MIT license detection"""
        license_content = "MIT License\n\nCopyright (c) 2023 Test"
        license_path = Path(self.temp_dir) / "LICENSE"
        license_path.write_text(license_content)
        
        result = get_license_info(self.temp_dir)
        self.assertEqual(result, 'MIT')
    
    def test_apache_license_detection(self):
        """Test Apache license detection"""
        license_content = "Apache License\nVersion 2.0"
        license_path = Path(self.temp_dir) / "LICENSE.txt"
        license_path.write_text(license_content)
        
        result = get_license_info(self.temp_dir)
        self.assertEqual(result, 'Apache-2.0')
    
    def test_gpl_license_detection(self):
        """Test GPL license detection"""
        license_content = "GNU GENERAL PUBLIC LICENSE\nVersion 3"
        license_path = Path(self.temp_dir) / "LICENSE.md"
        license_path.write_text(license_content)
        
        result = get_license_info(self.temp_dir)
        self.assertEqual(result, 'GPL-3.0')
    
    def test_no_license_file(self):
        """Test when no license file exists"""
        result = get_license_info(self.temp_dir)
        self.assertEqual(result, 'None')
    
    def test_unknown_license(self):
        """Test unknown license content"""
        license_content = "Some Custom License"
        license_path = Path(self.temp_dir) / "LICENSE"
        license_path.write_text(license_content)
        
        result = get_license_info(self.temp_dir)
        self.assertEqual(result, 'Other')


class TestGetGHPagesUrl(unittest.TestCase):
    """Test GitHub Pages URL detection"""
    
    def setUp(self):
        """Set up test directory"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.commands.status.run_command')
    def test_github_pages_https_remote(self, mock_run_command):
        """Test GitHub Pages detection with HTTPS remote"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main\norigin/gh-pages"  # branches with gh-pages
        ]
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_github_pages_ssh_remote(self, mock_run_command):
        """Test GitHub Pages detection with SSH remote"""
        mock_run_command.side_effect = [
            "git@github.com:user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main\norigin/gh-pages"  # branches with gh-pages
        ]
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_no_github_pages(self, mock_run_command):
        """Test when no GitHub Pages detected"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main"  # no gh-pages branch
        ]
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertIsNone(result)
    
    @patch('ghops.commands.status.run_command')
    def test_docs_folder_detection(self, mock_run_command):
        """Test GitHub Pages detection via docs folder"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main"  # no gh-pages branch
        ]
        
        # Create docs folder with index.html
        docs_dir = Path(self.temp_dir) / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.html").write_text("<html></html>")
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_jekyll_config_detection(self, mock_run_command):
        """Test GitHub Pages detection via Jekyll config"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main"  # no gh-pages branch
        ]
        
        # Create Jekyll config file
        config_file = Path(self.temp_dir) / "_config.yml"
        config_file.write_text("title: My Site")
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_mkdocs_config_detection(self, mock_run_command):
        """Test GitHub Pages detection via MkDocs config"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main"  # no gh-pages branch
        ]
        
        # Create MkDocs config file
        config_file = Path(self.temp_dir) / "mkdocs.yml"
        config_file.write_text("site_name: My Docs")
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_package_json_with_pages_script(self, mock_run_command):
        """Test GitHub Pages detection via package.json with pages script"""
        mock_run_command.side_effect = [
            "https://github.com/user/repo.git",  # remote URL
            None,  # gh command not available
            "origin/main"  # no gh-pages branch
        ]
        
        # Create package.json with pages script
        package_json = {
            "name": "test-project",
            "scripts": {
                "build": "npm run build",
                "deploy": "gh-pages -d build"
            }
        }
        package_file = Path(self.temp_dir) / "package.json"
        package_file.write_text(json.dumps(package_json))
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertEqual(result, "https://user.github.io/repo/")
    
    @patch('ghops.commands.status.run_command')
    def test_non_github_remote(self, mock_run_command):
        """Test with non-GitHub remote URL"""
        mock_run_command.return_value = "https://gitlab.com/user/repo.git"
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertIsNone(result)
    
    @patch('ghops.commands.status.run_command')
    def test_no_remote_url(self, mock_run_command):
        """Test when no remote URL is available"""
        mock_run_command.return_value = None
        
        result = get_gh_pages_url(self.temp_dir)
        self.assertIsNone(result)


class TestDisplayRepoStatusTable(unittest.TestCase):
    """Test repository status table display"""
    
    @patch('ghops.commands.status.get_git_status')
    @patch('ghops.commands.status.get_license_info')
    @patch('ghops.commands.status.get_gh_pages_url')
    @patch('ghops.commands.status.detect_pypi_package')
    @patch('ghops.commands.status.console')
    def test_display_repo_status_table_json(self, mock_console, mock_detect_pypi, 
                                          mock_pages, mock_license, mock_git_status):
        """Test JSON output format"""
        # Setup mocks
        mock_git_status.return_value = {'status': 'clean', 'branch': 'main'}
        mock_license.return_value = 'MIT'
        mock_pages.return_value = None
        mock_detect_pypi.return_value = {
            'has_packaging_files': False,
            'is_published': False,
            'package_name': None
        }
        
        repo_dirs = ['test_repo']
        display_repo_status_table(repo_dirs, json_output=True)
        
        # Verify JSON output was called
        mock_console.print_json.assert_called_once()
        call_args = mock_console.print_json.call_args[1]['data']
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]['name'], 'test_repo')
        self.assertEqual(call_args[0]['status'], 'clean')
        self.assertEqual(call_args[0]['branch'], 'main')
        self.assertEqual(call_args[0]['license'], 'MIT')
    
    @patch('ghops.commands.status.get_git_status')
    @patch('ghops.commands.status.get_license_info')
    @patch('ghops.commands.status.get_gh_pages_url')
    @patch('ghops.commands.status.detect_pypi_package')
    @patch('ghops.commands.status.console')
    def test_display_repo_status_no_repos(self, mock_console, mock_detect_pypi, 
                                        mock_pages, mock_license, mock_git_status):
        """Test handling of empty repository list"""
        display_repo_status_table([])
        
        # Should print "No repositories found"
        mock_console.print.assert_called_with("No repositories found.")


class TestSampleRepositoriesForSocialMedia(unittest.TestCase):
    """Test social media repository sampling"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create fake repositories
        for i in range(5):
            repo_dir = os.path.join(self.temp_dir, f"repo_{i}")
            os.makedirs(repo_dir)
            os.makedirs(os.path.join(repo_dir, ".git"))
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.commands.status.detect_pypi_package')
    @patch('ghops.commands.status.get_license_info')
    @patch('ghops.commands.status.get_gh_pages_url')
    def test_sample_repositories(self, mock_pages, mock_license, mock_detect_pypi):
        """Test repository sampling for social media"""
        # Setup mocks
        mock_detect_pypi.return_value = {
            'has_packaging_files': True,
            'is_published': True
        }
        mock_license.return_value = 'MIT'
        mock_pages.return_value = 'https://user.github.io/repo/'
        
        repo_dirs = [f"repo_{i}" for i in range(5)]
        sampled = sample_repositories_for_social_media(repo_dirs, self.temp_dir, 3)
        
        self.assertEqual(len(sampled), 3)
        for repo in sampled:
            self.assertIn('name', repo)
            self.assertIn('has_package', repo)
            self.assertIn('is_published', repo)
            self.assertTrue(repo['has_package'])
            self.assertTrue(repo['is_published'])
    
    @patch('ghops.commands.status.detect_pypi_package')
    @patch('ghops.commands.status.get_license_info')
    @patch('ghops.commands.status.get_gh_pages_url')
    def test_sample_more_than_available(self, mock_pages, mock_license, mock_detect_pypi):
        """Test sampling when requested size is larger than available repos"""
        mock_detect_pypi.return_value = {
            'has_packaging_files': False,
            'is_published': False
        }
        mock_license.return_value = 'None'
        mock_pages.return_value = None
        
        repo_dirs = ["repo_0", "repo_1"]
        sampled = sample_repositories_for_social_media(repo_dirs, self.temp_dir, 5)
        
        # Should return all available repos (2), not the requested 5
        self.assertEqual(len(sampled), 2)


if __name__ == '__main__':
    unittest.main()
