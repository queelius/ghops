"""
Unit tests for ghops.utils module
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.utils import (
    run_command, 
    find_git_repos, 
    get_git_status, 
    is_git_repo
)


class TestRunCommand(unittest.TestCase):
    """Test the run_command utility function"""
    
    def test_run_command_capture_output(self):
        """Test run_command with capture_output=True"""
        result = run_command("echo 'test'", capture_output=True)
        self.assertEqual(result, "test")
    
    def test_run_command_no_capture(self):
        """Test run_command with capture_output=False"""
        result = run_command("echo 'test'", capture_output=False)
        self.assertIsNone(result)
    
    def test_run_command_dry_run(self):
        """Test run_command with dry_run=True"""
        result = run_command("echo 'test'", dry_run=True, capture_output=True)
        self.assertEqual(result, "Dry run output")
    
    def test_run_command_failure(self):
        """Test run_command with failing command"""
        result = run_command("false", capture_output=True, check=False)
        self.assertEqual(result, "")
    
    def test_run_command_with_cwd(self):
        """Test run_command with different working directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command("pwd", cwd=temp_dir, capture_output=True)
            self.assertEqual(result.strip(), temp_dir)


class TestGitRepoDetection(unittest.TestCase):
    """Test git repository detection functions"""
    
    def setUp(self):
        """Set up test directories"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a fake git repo
        self.git_repo_dir = os.path.join(self.temp_dir, "git_repo")
        os.makedirs(self.git_repo_dir)
        os.makedirs(os.path.join(self.git_repo_dir, ".git"))
        
        # Create a non-git directory
        self.non_git_dir = os.path.join(self.temp_dir, "non_git")
        os.makedirs(self.non_git_dir)
        
        # Create nested git repo
        self.nested_git_dir = os.path.join(self.temp_dir, "parent", "nested_git")
        os.makedirs(self.nested_git_dir)
        os.makedirs(os.path.join(self.nested_git_dir, ".git"))
    
    def tearDown(self):
        """Clean up test directories"""
        shutil.rmtree(self.temp_dir)
    
    def test_is_git_repo_positive(self):
        """Test is_git_repo with actual git repository"""
        self.assertTrue(is_git_repo(self.git_repo_dir))
    
    def test_is_git_repo_negative(self):
        """Test is_git_repo with non-git directory"""
        self.assertFalse(is_git_repo(self.non_git_dir))
    
    def test_find_git_repos_non_recursive(self):
        """Test find_git_repos without recursion"""
        repos = find_git_repos(self.temp_dir, recursive=False)
        self.assertIn(self.git_repo_dir, repos)
        self.assertNotIn(self.nested_git_dir, repos)
    
    def test_find_git_repos_recursive(self):
        """Test find_git_repos with recursion"""
        repos = find_git_repos(self.temp_dir, recursive=True)
        self.assertIn(self.git_repo_dir, repos)
        self.assertIn(self.nested_git_dir, repos)


class TestGetGitStatus(unittest.TestCase):
    """Test the get_git_status function"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir("/")
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.utils.run_command')
    def test_get_git_status_clean_repo(self, mock_run_command):
        """Test get_git_status with clean repository"""
        mock_run_command.side_effect = [
            "main",              # git rev-parse --abbrev-ref HEAD
            "",                  # git status --porcelain
            "fatal: no upstream" # git rev-parse --abbrev-ref @{u}
        ]
        
        result = get_git_status(self.temp_dir)
        
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['branch'], 'main')
    
    @patch('ghops.utils.run_command')
    def test_get_git_status_modified_files(self, mock_run_command):
        """Test get_git_status with modified files"""
        mock_run_command.side_effect = [
            "main",                                      # git rev-parse --abbrev-ref HEAD
            " M file1.py\nM  file2.py\n?? new_file.py", # git status --porcelain
            "fatal: no upstream"                         # git rev-parse --abbrev-ref @{u}
        ]
        
        result = get_git_status(self.temp_dir)
        
        self.assertEqual(result['branch'], 'main')
        self.assertIn('modified', result['status'])
        self.assertIn('untracked', result['status'])
    
    @patch('ghops.utils.run_command')
    def test_get_git_status_error(self, mock_run_command):
        """Test get_git_status with command failure"""
        mock_run_command.side_effect = Exception("Git command failed")
        
        result = get_git_status(self.temp_dir)
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['branch'], 'unknown')
    
    @patch('ghops.utils.run_command')
    def test_get_git_status_various_changes(self, mock_run_command):
        """Test get_git_status with various types of changes"""
        mock_run_command.side_effect = [
            "feature-branch",                                               # git rev-parse --abbrev-ref HEAD
            "A  added.py\n D deleted.py\nM  modified.py\n?? untracked.py", # git status --porcelain
            "fatal: no upstream"                                            # git rev-parse --abbrev-ref @{u}
        ]
        
        result = get_git_status(self.temp_dir)
        
        self.assertEqual(result['branch'], 'feature-branch')
        status = result['status']
        self.assertIn('1 added', status)
        self.assertIn('1 deleted', status) 
        self.assertIn('1 modified', status)
        self.assertIn('1 untracked', status)


if __name__ == '__main__':
    unittest.main()

import pytest
from ghops.utils import find_git_repos


@pytest.fixture
def mock_git_repos(fs):
    """Create a mock file system with git repositories."""
    fs.create_dir("/test/repo1/.git")
    fs.create_dir("/test/repo2/.git")
    fs.create_dir("/test/not_a_repo/subdir")
    fs.create_dir("/test/level2/repo3/.git")
    fs.create_dir("/test_single_repo/.git")
    fs.create_dir("/test_single_repo/subdir/repo4/.git")


def test_find_git_repos_single_dir_no_recursion(mock_git_repos):
    # Test with a single directory, no recursion
    repos = find_git_repos("/test", recursive=False)
    assert sorted(repos) == ["/test/repo1", "/test/repo2"]


def test_find_git_repos_single_dir_recursive(mock_git_repos):
    # Test with a single directory, with recursion
    repos = find_git_repos("/test", recursive=True)
    assert sorted(repos) == ["/test/level2/repo3", "/test/repo1", "/test/repo2"]


def test_find_git_repos_list_of_dirs(mock_git_repos):
    # Test with a list of directories
    repos = find_git_repos(["/test", "/test_single_repo"], recursive=True)
    assert sorted(repos) == [
        "/test/level2/repo3",
        "/test/repo1",
        "/test/repo2",
        "/test_single_repo",
        "/test_single_repo/subdir/repo4",
    ]


def test_find_git_repos_base_dir_is_repo(mock_git_repos):
    # Test when the base directory itself is a repo
    # Without recursion, should only find the base
    repos = find_git_repos("/test_single_repo", recursive=False)
    assert repos == ["/test_single_repo"]

    # With recursion, should find both the parent and the nested repo
    repos_recursive = find_git_repos("/test_single_repo", recursive=True)
    assert sorted(repos_recursive) == ["/test_single_repo", "/test_single_repo/subdir/repo4"]


def test_find_git_repos_empty(fs):
    # Test with no git repos in the specified path
    fs.create_dir("/empty_dir/subdir")
    repos = find_git_repos("/empty_dir", recursive=True)
    assert repos == []


def test_find_git_repos_nonexistent_dir(mock_git_repos):
    # Test with a non-existent directory
    repos = find_git_repos("/nonexistent")
    assert repos == []


def test_find_git_repos_handles_string_and_list_input(mock_git_repos):
    # The function should handle both a single string and a list of strings
    repos_str = find_git_repos("/test", recursive=True)
    repos_list = find_git_repos(["/test"], recursive=True)
    assert sorted(repos_str) == sorted(repos_list)
    assert sorted(repos_str) == ["/test/level2/repo3", "/test/repo1", "/test/repo2"]
