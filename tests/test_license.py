"""
Unit tests for ghops.commands.license module
"""
import unittest
import tempfile
import os
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.commands.license import (
    list_licenses,
    show_license_template,
    add_license_to_repo
)


class TestLicenseCommands(unittest.TestCase):
    """Test the license command functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Create test repository structure
        self.test_repo = os.path.join(self.temp_dir, "test_repo")
        os.makedirs(self.test_repo)
        os.makedirs(os.path.join(self.test_repo, ".git"))
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    @patch('ghops.commands.license.run_command')
    def test_list_licenses_success(self, mock_run_command):
        """Test successful listing of licenses"""
        mock_response = json.dumps([
            {"key": "mit", "name": "MIT License"},
            {"key": "apache-2.0", "name": "Apache License 2.0"},
            {"key": "gpl-3.0", "name": "GNU General Public License v3.0"}
        ])
        mock_run_command.return_value = mock_response
        
        # Note: This function doesn't return anything, it prints to console
        # We're just testing it doesn't raise an exception
        list_licenses(json_output=True)
        
        mock_run_command.assert_called_once_with("gh api /licenses", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_list_licenses_command_failure(self, mock_run_command):
        """Test listing licenses when command fails"""
        mock_run_command.return_value = None
        
        # Should not raise exception on command failure
        list_licenses(json_output=True)
        
        mock_run_command.assert_called_once_with("gh api /licenses", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_list_licenses_table_output(self, mock_run_command):
        """Test listing licenses with table output"""
        mock_response = json.dumps([
            {"key": "mit", "name": "MIT License"}
        ])
        mock_run_command.return_value = mock_response
        
        # Should not raise exception with table output
        list_licenses(json_output=False)
        
        mock_run_command.assert_called_once_with("gh api /licenses", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_show_license_template_success(self, mock_run_command):
        """Test successful showing of a license template"""
        mock_response = json.dumps({
            "key": "mit",
            "name": "MIT License",
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        # Should not raise exception
        show_license_template("mit", json_output=True)
        
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_show_license_template_command_failure(self, mock_run_command):
        """Test showing license when command fails"""
        mock_run_command.return_value = None
        
        # Should not raise exception on command failure
        show_license_template("invalid", json_output=True)
        
        mock_run_command.assert_called_once_with("gh api /licenses/invalid", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_show_license_template_table_output(self, mock_run_command):
        """Test showing license template with table output"""
        mock_response = json.dumps({
            "key": "mit",
            "name": "MIT License",
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        # Should not raise exception with table output
        show_license_template("mit", json_output=False)
        
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_success(self, mock_run_command):
        """Test successful addition of license to repository"""
        mock_response = json.dumps({
            "body": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted..."
        })
        mock_run_command.return_value = mock_response
        
        add_license_to_repo(
            self.test_repo,
            license_key="mit",
            author_name="Test Author",
            author_email="test@example.com",
            year="2023",
            dry_run=False,
            force=False
        )
        
        # Check that LICENSE file was created
        license_file = Path(self.test_repo) / "LICENSE"
        self.assertTrue(license_file.exists())
        
        # Check file contents
        with open(license_file, 'r') as f:
            content = f.read()
            self.assertIn("MIT License", content)
            self.assertIn("Copyright (c) 2023 Test Author", content)
        
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_dry_run(self, mock_run_command):
        """Test adding license in dry run mode"""
        mock_response = json.dumps({
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        add_license_to_repo(
            self.test_repo,
            license_key="mit",
            author_name="Test Author",
            author_email="test@example.com",
            year="2023",
            dry_run=True,
            force=False
        )
        
        # Check that LICENSE file was NOT created
        license_file = Path(self.test_repo) / "LICENSE"
        self.assertFalse(license_file.exists())
        
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)
    
    def test_add_license_to_repo_existing_file_no_force(self):
        """Test adding license when file exists and force is False"""
        # Create existing LICENSE file
        license_file = Path(self.test_repo) / "LICENSE"
        with open(license_file, 'w') as f:
            f.write("Existing license content")
        
        with patch('ghops.commands.license.run_command') as mock_run_command:
            add_license_to_repo(
                self.test_repo,
                license_key="mit",
                author_name="Test Author",
                author_email="test@example.com",
                year="2023",
                dry_run=False,
                force=False
            )
            
            # Command should not be called
            mock_run_command.assert_not_called()
            
            # File should remain unchanged
            with open(license_file, 'r') as f:
                content = f.read()
                self.assertEqual(content, "Existing license content")
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_existing_file_with_force(self, mock_run_command):
        """Test adding license when file exists and force is True"""
        # Create existing LICENSE file
        license_file = Path(self.test_repo) / "LICENSE"
        with open(license_file, 'w') as f:
            f.write("Existing license content")
        
        mock_response = json.dumps({
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        add_license_to_repo(
            self.test_repo,
            license_key="mit",
            author_name="Test Author",
            author_email="test@example.com",
            year="2023",
            dry_run=False,
            force=True
        )
        
        # File should be overwritten
        with open(license_file, 'r') as f:
            content = f.read()
            self.assertIn("MIT License", content)
            self.assertIn("Test Author", content)
        
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_command_failure(self, mock_run_command):
        """Test adding license when GitHub API command fails"""
        mock_run_command.return_value = None
        
        add_license_to_repo(
            self.test_repo,
            license_key="invalid",
            author_name="Test Author",
            author_email="test@example.com",
            year="2023",
            dry_run=False,
            force=False
        )
        
        # LICENSE file should not be created
        license_file = Path(self.test_repo) / "LICENSE"
        self.assertFalse(license_file.exists())
        
        mock_run_command.assert_called_once_with("gh api /licenses/invalid", capture_output=True)
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_invalid_json(self, mock_run_command):
        """Test adding license with invalid JSON response"""
        mock_run_command.return_value = "invalid json"
        
        # The function doesn't handle JSON decode errors gracefully currently
        # This is actually a bug that could be fixed, but we'll test the current behavior
        with self.assertRaises(json.JSONDecodeError):
            add_license_to_repo(
                self.test_repo,
                license_key="mit",
                author_name="Test Author",
                author_email="test@example.com",
                year="2023",
                dry_run=False,
                force=False
            )
        
        # LICENSE file should not be created due to the error
        license_file = Path(self.test_repo) / "LICENSE"
        self.assertFalse(license_file.exists())
    
    @patch('ghops.commands.license.run_command')
    @patch('ghops.commands.license.datetime')
    def test_add_license_to_repo_default_year(self, mock_datetime, mock_run_command):
        """Test adding license with default year"""
        mock_datetime.now.return_value.year = 2023
        mock_response = json.dumps({
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        add_license_to_repo(
            self.test_repo,
            license_key="mit",
            author_name="Test Author",
            author_email="test@example.com",
            year=None,  # Should use default year
            dry_run=False,
            force=False
        )
        
        # Check that current year was used
        license_file = Path(self.test_repo) / "LICENSE"
        with open(license_file, 'r') as f:
            content = f.read()
            self.assertIn("Copyright (c) 2023 Test Author", content)
    
    @patch('ghops.commands.license.run_command')
    def test_add_license_to_repo_no_author_info(self, mock_run_command):
        """Test adding license without author information"""
        mock_response = json.dumps({
            "body": "MIT License\n\nCopyright (c) [year] [fullname]"
        })
        mock_run_command.return_value = mock_response
        
        add_license_to_repo(
            self.test_repo,
            license_key="mit",
            author_name=None,  # No author info
            author_email=None,  # No author info
            year="2023",
            dry_run=False,
            force=False
        )
        
        # Check that placeholders remain if no author info provided
        license_file = Path(self.test_repo) / "LICENSE"
        with open(license_file, 'r') as f:
            content = f.read()
            # Since no author_name is provided, template replacements won't happen
            self.assertIn("Copyright (c) [year] [fullname]", content)


if __name__ == '__main__':
    unittest.main()
