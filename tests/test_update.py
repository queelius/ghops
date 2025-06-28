"""
Unit tests for ghops.commands.update module
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.commands.update import (
    pull_repo,
    commit_changes,
    push_repo,
    update_repo,
    update_all_repos,
    handle_merge_conflicts
)


class TestUpdateCommand(unittest.TestCase):
    """Test the update command functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Create test repository structure
        self.test_repo = os.path.join(self.temp_dir, "test_repo")
        os.makedirs(self.test_repo)
        os.makedirs(os.path.join(self.test_repo, ".git"))
        
        # Create a test file to modify
        self.test_file = os.path.join(self.test_repo, "test.txt")
        with open(self.test_file, 'w') as f:
            f.write("Initial content")
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.commands.update.run_command')
    def test_pull_repo_success(self, mock_run_command):
        """Test successful repository pull"""
        mock_run_command.return_value = "Pull successful"
        
        pull_repo(self.test_repo, dry_run=False)
        
        mock_run_command.assert_called_once_with(
            "git pull --rebase --autostash",
            self.test_repo,
            False,
            capture_output=True
        )
    
    @patch('ghops.commands.update.run_command')
    def test_pull_repo_dry_run(self, mock_run_command):
        """Test repository pull in dry run mode"""
        mock_run_command.return_value = "Dry run output"
        
        pull_repo(self.test_repo, dry_run=True)
        
        mock_run_command.assert_called_once_with(
            "git pull --rebase --autostash",
            self.test_repo,
            True,
            capture_output=True
        )
    
    @patch('ghops.commands.update.run_command')
    def test_pull_repo_no_changes(self, mock_run_command):
        """Test pull when no changes are available"""
        mock_run_command.return_value = None
        
        pull_repo(self.test_repo, dry_run=False)
        
        mock_run_command.assert_called_once()
    
    @patch('ghops.commands.update.get_git_status')
    @patch('ghops.commands.update.run_command')
    def test_commit_changes_success(self, mock_run_command, mock_get_status):
        """Test successful commit of changes"""
        mock_get_status.return_value = "modified: test.txt"
        mock_run_command.side_effect = ["Add successful", "Commit successful"]
        
        commit_changes(self.test_repo, "Test commit", dry_run=False)
        
        # Should call git add and git commit
        self.assertEqual(mock_run_command.call_count, 2)
    
    @patch('ghops.commands.update.get_git_status')
    @patch('ghops.commands.update.run_command')
    def test_commit_changes_no_changes(self, mock_run_command, mock_get_status):
        """Test commit when no changes exist"""
        mock_get_status.return_value = None
        
        commit_changes(self.test_repo, "Test commit", dry_run=False)
        
        # Should not call git commands if no changes
        mock_run_command.assert_not_called()
    
    @patch('ghops.commands.update.get_git_status')
    @patch('ghops.commands.update.run_command')
    def test_commit_changes_dry_run(self, mock_run_command, mock_get_status):
        """Test commit in dry run mode"""
        mock_get_status.return_value = "modified: test.txt"
        mock_run_command.side_effect = ["Add output", "Commit output"]
        
        commit_changes(self.test_repo, "Test commit", dry_run=True)
        
        # Verify dry_run parameter is passed
        for call in mock_run_command.call_args_list:
            self.assertTrue(call[0][2])  # dry_run parameter
    
    @patch('ghops.commands.update.run_command')
    def test_push_repo_success(self, mock_run_command):
        """Test successful push of changes"""
        mock_run_command.return_value = "Push successful"
        
        push_repo(self.test_repo, dry_run=False)
        
        mock_run_command.assert_called_once_with(
            "git push",
            self.test_repo,
            False,
            capture_output=True
        )
    
    @patch('ghops.commands.update.run_command')
    def test_push_repo_dry_run(self, mock_run_command):
        """Test push in dry run mode"""
        mock_run_command.return_value = "Dry run output"
        
        push_repo(self.test_repo, dry_run=True)
        
        mock_run_command.assert_called_once_with(
            "git push",
            self.test_repo,
            True,
            capture_output=True
        )
    
    @patch('ghops.commands.update.run_command')
    def test_push_repo_failure(self, mock_run_command):
        """Test push failure"""
        mock_run_command.return_value = None
        
        push_repo(self.test_repo, dry_run=False)
        
        mock_run_command.assert_called_once()
    
    @patch('ghops.commands.update.run_command')
    def test_handle_merge_conflicts_abort(self, mock_run_command):
        """Test merge conflict resolution with abort strategy"""
        mock_run_command.side_effect = ["conflicted file", None]
        
        handle_merge_conflicts(self.test_repo, "abort", dry_run=False)
        
        # Should check for conflicts and abort merge
        self.assertEqual(mock_run_command.call_count, 2)
        mock_run_command.assert_any_call("git ls-files -u", self.test_repo, capture_output=True)
        mock_run_command.assert_any_call("git merge --abort", self.test_repo, False)
    
    @patch('ghops.commands.update.run_command')
    def test_handle_merge_conflicts_no_conflicts(self, mock_run_command):
        """Test when no merge conflicts exist"""
        mock_run_command.return_value = ""
        
        handle_merge_conflicts(self.test_repo, "abort", dry_run=False)
        
        # Should only check for conflicts
        mock_run_command.assert_called_once_with("git ls-files -u", self.test_repo, capture_output=True)
    
    @patch('ghops.commands.update.push_repo')
    @patch('ghops.commands.update.handle_merge_conflicts')
    @patch('ghops.commands.update.pull_repo')
    @patch('ghops.commands.update.commit_changes')
    def test_update_repo_full_cycle(self, mock_commit, mock_pull, mock_conflicts, mock_push):
        """Test full update cycle for a single repository"""
        update_repo(
            repo_path=self.test_repo,
            auto_commit=True,
            commit_message="Test commit",
            auto_resolve_conflicts="abort",
            prompt=False,
            dry_run=False
        )
        
        # Should call all operations in order
        mock_commit.assert_called_once_with(self.test_repo, "Test commit", False)
        mock_pull.assert_called_once_with(self.test_repo, False)
        mock_conflicts.assert_called_once_with(self.test_repo, "abort", False)
        mock_push.assert_called_once_with(self.test_repo, False)
    
    @patch('ghops.commands.update.push_repo')
    @patch('ghops.commands.update.handle_merge_conflicts')
    @patch('ghops.commands.update.pull_repo')
    @patch('ghops.commands.update.commit_changes')
    def test_update_repo_no_auto_commit(self, mock_commit, mock_pull, mock_conflicts, mock_push):
        """Test update without auto commit"""
        update_repo(
            repo_path=self.test_repo,
            auto_commit=False,
            commit_message="Test commit",
            auto_resolve_conflicts=None,
            prompt=False,
            dry_run=False
        )
        
        # Should not call commit or conflict resolution
        mock_commit.assert_not_called()
        mock_pull.assert_called_once()
        mock_conflicts.assert_not_called()
        mock_push.assert_called_once()
    
    @patch('ghops.commands.update.find_git_repos')
    @patch('ghops.commands.update.update_repo')
    def test_update_all_repos_basic(self, mock_update_repo, mock_find_repos):
        """Test basic update of all repositories"""
        # Mock finding repositories
        mock_find_repos.return_value = [
            os.path.join(self.temp_dir, 'repo1'),
            os.path.join(self.temp_dir, 'repo2')
        ]
        
        update_all_repos(
            auto_commit=False,
            commit_message="Test",
            auto_resolve_conflicts=None,
            prompt=False,
            ignore_list=[],
            dry_run=False,
            base_dir=self.temp_dir,
            recursive=True
        )
        
        # Should call update_repo for each repository
        self.assertEqual(mock_update_repo.call_count, 2)
        mock_find_repos.assert_called_once_with(self.temp_dir, True)
    
    @patch('ghops.commands.update.find_git_repos')
    @patch('ghops.commands.update.update_repo')
    def test_update_all_repos_with_ignore_list(self, mock_update_repo, mock_find_repos):
        """Test update with ignored repositories"""
        # Mock finding repositories
        mock_find_repos.return_value = [
            os.path.join(self.temp_dir, 'repo1'),
            os.path.join(self.temp_dir, 'ignored_repo'),
            os.path.join(self.temp_dir, 'repo2')
        ]
        
        update_all_repos(
            auto_commit=False,
            commit_message="Test",
            auto_resolve_conflicts=None,
            prompt=False,
            ignore_list=['ignored_repo'],
            dry_run=False,
            base_dir=self.temp_dir,
            recursive=True
        )
        
        # Should call update_repo only for non-ignored repositories
        self.assertEqual(mock_update_repo.call_count, 2)
        
        # Verify the correct repositories were processed
        called_repos = [call[0][0] for call in mock_update_repo.call_args_list]  # positional args
        self.assertIn(os.path.join(self.temp_dir, 'repo1'), called_repos)
        self.assertIn(os.path.join(self.temp_dir, 'repo2'), called_repos)
        self.assertNotIn(os.path.join(self.temp_dir, 'ignored_repo'), called_repos)
    
    @patch('ghops.commands.update.find_git_repos')
    @patch('ghops.commands.update.add_license_to_repo')
    @patch('ghops.commands.update.update_repo')
    def test_update_all_repos_with_license(self, mock_update_repo, mock_add_license, mock_find_repos):
        """Test update with license addition"""
        # Mock finding repositories
        mock_find_repos.return_value = [os.path.join(self.temp_dir, 'repo1')]
        
        update_all_repos(
            auto_commit=False,
            commit_message="Test",
            auto_resolve_conflicts=None,
            prompt=False,
            ignore_list=[],
            dry_run=False,
            base_dir=self.temp_dir,
            recursive=True,
            add_license=True,
            license_type="mit",
            author_name="Test Author"
        )
        
        # Should call add_license_to_repo
        mock_add_license.assert_called_once()
        mock_update_repo.assert_called_once()
    
    @patch('ghops.commands.update.find_git_repos')
    def test_update_all_repos_no_repositories(self, mock_find_repos):
        """Test update when no repositories are found"""
        mock_find_repos.return_value = []
        
        # Should not raise an exception
        update_all_repos(
            auto_commit=False,
            commit_message="Test",
            auto_resolve_conflicts=None,
            prompt=False,
            ignore_list=[],
            dry_run=False,
            base_dir=self.temp_dir,
            recursive=True
        )
        
        mock_find_repos.assert_called_once()


if __name__ == '__main__':
    unittest.main()
