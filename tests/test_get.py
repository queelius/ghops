"""
Unit tests for ghops.commands.get module
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.commands.get import get_github_repos


class TestGetCommand(unittest.TestCase):
    """Test the get command functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.commands.get.run_command')
    @patch('ghops.commands.get.add_license_to_repo')
    def test_get_github_repos_basic(self, mock_add_license, mock_run_command):
        """Test basic repository cloning"""
        # Mock GitHub CLI response
        mock_run_command.side_effect = [
            "user/repo1\nuser/repo2",  # gh repo list response
            "Cloning into 'repo1'...",  # git clone response
            "Cloning into 'repo2'...",  # git clone response
        ]
        
        get_github_repos(
            users=['testuser'],
            ignore_list=[],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir
        )
        
        # Verify GitHub CLI was called
        self.assertEqual(mock_run_command.call_count, 3)
        
        # Check first call (gh repo list)
        first_call = mock_run_command.call_args_list[0]
        self.assertIn('gh repo list testuser', first_call[0][0])
        
        # Check git clone calls
        clone_calls = [call[0][0] for call in mock_run_command.call_args_list[1:]]
        self.assertIn('git clone "https://github.com/user/repo1.git"', clone_calls)
        self.assertIn('git clone "https://github.com/user/repo2.git"', clone_calls)
    
    @patch('ghops.commands.get.run_command')
    def test_get_github_repos_with_ignore_list(self, mock_run_command):
        """Test repository cloning with ignore list"""
        # Mock GitHub CLI response
        mock_run_command.side_effect = [
            "user/repo1\nuser/ignored-repo\nuser/repo2",  # gh repo list response
            "Cloning into 'repo1'...",  # git clone response
            "Cloning into 'repo2'...",  # git clone response
        ]
        
        get_github_repos(
            users=['testuser'],
            ignore_list=['ignored-repo'],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir
        )
        
        # Should have 3 calls: 1 for gh repo list, 2 for git clone (ignoring one)
        self.assertEqual(mock_run_command.call_count, 3)
        
        # Verify ignored repo was not cloned
        clone_calls = [call[0][0] for call in mock_run_command.call_args_list[1:]]
        self.assertNotIn('git clone "https://github.com/user/ignored-repo.git"', clone_calls)
    
    @patch('ghops.commands.get.run_command')
    def test_get_github_repos_dry_run(self, mock_run_command):
        """Test repository cloning in dry run mode"""
        # Mock GitHub CLI response
        mock_run_command.side_effect = [
            "user/repo1\nuser/repo2",  # gh repo list response
            "Dry run output",  # git clone dry run response
            "Dry run output",  # git clone dry run response
        ]
        
        get_github_repos(
            users=['testuser'],
            ignore_list=[],
            limit=10,
            dry_run=True,
            base_dir=self.temp_dir
        )
        
        # Verify all calls were made with dry_run=True
        for call in mock_run_command.call_args_list:
            if 'dry_run' in call[1]:
                self.assertTrue(call[1]['dry_run'])
    
    @patch('ghops.commands.get.run_command')
    def test_get_github_repos_no_repos_found(self, mock_run_command):
        """Test behavior when no repositories are found"""
        # Mock empty GitHub CLI response
        mock_run_command.return_value = ""
        
        get_github_repos(
            users=['nonexistentuser'],
            ignore_list=[],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir
        )
        
        # Should only call gh repo list, no git clone calls
        self.assertEqual(mock_run_command.call_count, 1)
    
    @patch('ghops.commands.get.run_command')
    @patch('ghops.commands.get.add_license_to_repo')
    @patch('pathlib.Path.exists')
    def test_get_github_repos_with_license(self, mock_exists, mock_add_license, mock_run_command):
        """Test repository cloning with license addition"""
        # Mock path exists for license addition
        mock_exists.return_value = True
        
        # Mock GitHub CLI and git responses
        mock_run_command.side_effect = [
            "user/repo1",  # gh repo list response
            "Cloning into 'repo1'...",  # git clone response
        ]
        
        get_github_repos(
            users=['testuser'],
            ignore_list=[],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir,
            add_license=True,
            license_type='mit',
            author_name='Test Author',
            author_email='test@example.com'
        )
        
        # Verify license was added
        mock_add_license.assert_called_once()
        call_args = mock_add_license.call_args
        self.assertEqual(call_args[1]['license_key'], 'mit')
        self.assertEqual(call_args[1]['author_name'], 'Test Author')
        self.assertEqual(call_args[1]['author_email'], 'test@example.com')
    
    @patch('ghops.commands.get.run_command')
    def test_get_github_repos_clone_failure(self, mock_run_command):
        """Test behavior when git clone fails"""
        # Mock GitHub CLI response and failed git clone
        mock_run_command.side_effect = [
            "user/repo1",  # gh repo list response
            None,  # git clone failure (returns None)
        ]
        
        get_github_repos(
            users=['testuser'],
            ignore_list=[],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir
        )
        
        # Should handle the failure gracefully
        self.assertEqual(mock_run_command.call_count, 2)
    
    @patch('ghops.commands.get.run_command')
    def test_get_github_repos_multiple_users(self, mock_run_command):
        """Test repository cloning for multiple users"""
        # Mock responses for multiple users
        mock_run_command.side_effect = [
            "user1/repo1",  # gh repo list for user1
            "Cloning into 'repo1'...",  # git clone for repo1
            "user2/repo2",  # gh repo list for user2
            "Cloning into 'repo2'...",  # git clone for repo2
        ]
        
        get_github_repos(
            users=['user1', 'user2'],
            ignore_list=[],
            limit=10,
            dry_run=False,
            base_dir=self.temp_dir
        )
        
        # Should have calls for both users
        self.assertEqual(mock_run_command.call_count, 4)
        
        # Verify calls for both users
        calls = [call[0][0] for call in mock_run_command.call_args_list]
        self.assertTrue(any('user1' in call for call in calls))
        self.assertTrue(any('user2' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
