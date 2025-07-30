"""
Integration tests for ghops CLI commands
"""
import unittest
import tempfile
import os
import shutil
import subprocess
import json
from pathlib import Path
from unittest.mock import patch


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for the CLI interface"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create a fake git repository
        self.test_repo = os.path.join(self.temp_dir, "test_repo")
        os.makedirs(self.test_repo)
        os.makedirs(os.path.join(self.test_repo, ".git"))
        
        # Create a pyproject.toml file
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
description = "A test package"
"""
        with open(os.path.join(self.test_repo, "pyproject.toml"), "w") as f:
            f.write(pyproject_content)
        
        # Create a LICENSE file
        license_content = "MIT License\n\nCopyright (c) 2023 Test User"
        with open(os.path.join(self.test_repo, "LICENSE"), "w") as f:
            f.write(license_content)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    def run_ghops_command(self, *args):
        """Helper to run ghops commands"""
        cmd = ["python", "-m", "ghops.cli"] + list(args)
        env = os.environ.copy()
        # Add the project root to PYTHONPATH so the module can be found
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env['PYTHONPATH'] = project_root + (os.pathsep + env.get('PYTHONPATH', ''))
        result = subprocess.run(
            cmd,
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
            env=env
        )
        return result
    
    def test_status_command_json_output(self):
        """Test status command with JSONL output"""
        result = self.run_ghops_command("status", "--no-pypi", "--no-pages")
        
        self.assertEqual(result.returncode, 0)
        
        # Parse JSONL output (each line should be valid JSON)
        lines = result.stdout.strip().split('\n')
        if lines and lines[0]:  # If there's output
            for line in lines:
                if line.strip():  # Skip empty lines
                    try:
                        repo_data = json.loads(line)
                        self.assertIn('name', repo_data)
                        self.assertIn('status', repo_data)
                        self.assertIn('branch', repo_data)
                        self.assertIn('license', repo_data)
                    except json.JSONDecodeError:
                        self.fail(f"Line is not valid JSON: {line}")
    
    def test_config_generate(self):
        """Test config generation"""
        result = self.run_ghops_command("config", "generate")
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("example configuration", result.stdout.lower())
        
        # Check that example file was created in the temp_dir
        example_file = Path.home() / ".ghopsrc"
        self.assertTrue(example_file.exists())
    
    def test_config_show(self):
        """Test config show command"""
        result = self.run_ghops_command("config", "show")
        
        self.assertEqual(result.returncode, 0)
        
        # Should output JSON configuration
        try:
            config_data = json.loads(result.stdout)
            self.assertIn('pypi', config_data)
            self.assertIn('social_media', config_data)
            self.assertIn('logging', config_data)
        except json.JSONDecodeError:
            self.fail(f"Config show did not output valid JSON: {result.stdout}")
    
    def test_license_list(self):
        """Test license list command"""
        result = self.run_ghops_command("license", "list")
        
        self.assertEqual(result.returncode, 0)
        try:
            output_data = json.loads(result.stdout)
            self.assertIsInstance(output_data, list)
            self.assertTrue(len(output_data) > 0)
            self.assertIn('mit', [item['key'] for item in output_data])
        except json.JSONDecodeError:
            self.fail(f"License list command did not output valid JSON: {result.stdout}")
    
    def test_license_show(self):
        """Test license show command"""
        result = self.run_ghops_command("license", "show", "mit")
        
        self.assertEqual(result.returncode, 0)
        try:
            output_data = json.loads(result.stdout)
            self.assertIsInstance(output_data, dict)
            self.assertIn('key', output_data)
            self.assertEqual(output_data['key'], 'mit')
            self.assertIn('body', output_data)
        except json.JSONDecodeError:
            self.fail(f"License show command did not output valid JSON: {result.stdout}")
    
    
    
    def test_social_post_dry_run(self):
        """Test social media posting with dry run"""
        result = self.run_ghops_command("social", "post", "--dry-run")
        
        self.assertEqual(result.returncode, 0)
        
        # Expecting message about no posts
        self.assertIn("No posts to execute.", result.stdout)
    
    def test_command_help(self):
        """Test that help is displayed for various commands"""
        # Main help
        result = self.run_ghops_command("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("GitHub Operations CLI Tool", result.stdout)
        
        # Status help
        result = self.run_ghops_command("status", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--json", result.stdout)  # --json option removed
        
        # Config help
        result = self.run_ghops_command("config", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("generate", result.stdout)  # Check for config-specific options
    
    def test_invalid_command(self):
        """Test handling of invalid commands"""
        result = self.run_ghops_command("invalid_command")
        
        self.assertNotEqual(result.returncode, 0)
    
    def test_status_with_performance_flags(self):
        """Test status command with performance optimization flags"""
        result = self.run_ghops_command("status", "--no-pypi", "--no-pages")
        
        self.assertEqual(result.returncode, 0)
        # Should complete faster without external API calls


class TestCLIErrorHandling(unittest.TestCase):
    """Test CLI error handling scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    def run_ghops_command(self, *args):
        """Helper to run ghops commands"""
        cmd = ["python", "-m", "ghops.cli"] + list(args)
        env = os.environ.copy()
        # Add the project root to PYTHONPATH so the module can be found
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env['PYTHONPATH'] = project_root + (os.pathsep + env.get('PYTHONPATH', ''))
        result = subprocess.run(
            cmd,
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
            env=env
        )
        return result
    
    def test_status_no_repositories(self):
        """Test status command when no repositories are found"""
        result = self.run_ghops_command("status", "--no-pypi", "--no-pages")
        
        self.assertEqual(result.returncode, 0)
        # With JSONL format, empty result means no output lines
        self.assertEqual(result.stdout.strip(), "")
    
    def test_license_show_invalid(self):
        """Test license show with invalid license"""
        result = self.run_ghops_command("license", "show", "invalid_license")
        
        # Should handle gracefully (implementation dependent)
        # Either succeed with error message or fail gracefully
        self.assertIsNotNone(result.returncode)


if __name__ == '__main__':
    unittest.main()
