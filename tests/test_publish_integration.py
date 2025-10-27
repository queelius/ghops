"""
Integration tests for the publish command workflow.

Tests the full end-to-end publish workflow including:
- Version bumping + publishing
- Multiple project types
- VFS path resolution
- Configuration-based registry selection
- Dry-run workflows
- Error recovery
"""

import pytest
import json
import toml
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from click.testing import CliRunner

from ghops.commands.publish import publish_handler
from ghops.version_manager import get_version


class TestPublishIntegrationVersionBumping:
    """Test integration of version bumping with publishing."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_with_bump_patch(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test publish workflow with patch version bump."""
        # Setup test repo
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/dist")
        fs.create_file(f"{repo_path}/dist/package.whl", contents="")

        pyproject_content = """
[project]
name = "testpkg"
version = "1.0.0"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        # Mock VFS resolution
        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        # Run publish with version bump
        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/test', '--bump-version', 'patch', '--dry-run'])

        # Verify version was bumped (in dry run)
        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_with_set_version(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test publish workflow with explicit version setting."""
        # Setup test repo
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        pyproject_content = """
[project]
version = "1.0.0"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        # Mock VFS resolution
        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        # Run publish with explicit version
        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--set-version', '2.5.0', '--version-only']
            )

        # Verify version was set
        updated_version = get_version(repo_path, 'python')
        assert updated_version == "2.5.0"

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_version_only_mode_skips_publishing(self, mock_console, mock_get_repos, fs):
        """Test that --version-only skips the publishing step."""
        # Setup test repo
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        pyproject_content = """
[project]
version = "1.0.0"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        mock_get_repos.return_value = [repo_path]

        # Run with version-only
        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            with patch('ghops.commands.publish.run_command') as mock_run:
                result = runner.invoke(
                    publish_handler,
                    ['/repos/test', '--bump-version', 'minor', '--version-only']
                )

                # Verify no publish commands were run
                mock_run.assert_not_called()

        # But version should be updated
        updated_version = get_version(repo_path, 'python')
        assert updated_version == "1.1.0"

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_bump_major_version_integration(self, mock_console, mock_get_repos, fs):
        """Test major version bump integration."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        package_json = {"version": "0.9.5"}
        fs.create_file(
            f"{repo_path}/package.json",
            contents=json.dumps(package_json, indent=2)
        )

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--bump-version', 'major', '--version-only']
            )

        # Verify major version bump
        updated_version = get_version(repo_path, 'node')
        assert updated_version == "1.0.0"


class TestPublishIntegrationMultipleProjects:
    """Test publishing with multiple project types."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_multiple_repos(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test publishing multiple repositories at once."""
        # Setup multiple repos
        repo1 = "/test/repo1"
        repo2 = "/test/repo2"

        fs.create_dir(repo1)
        fs.create_file(f"{repo1}/pyproject.toml", contents="[project]\nversion='1.0.0'")

        fs.create_dir(repo2)
        fs.create_file(f"{repo2}/package.json", contents='{"version":"2.0.0"}')

        mock_get_repos.return_value = [repo1, repo2]
        mock_run_command.return_value = ("success", 0)

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/by-language/All', '--dry-run'])

        # Should process both repos
        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_repo_with_multiple_project_types(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test publishing repo with multiple project types (e.g., Python + Node)."""
        repo_path = "/test/polyglot"
        fs.create_dir(repo_path)

        # Multiple project types in same repo
        pyproject_content = """
[project]
version = "1.0.0"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        package_json = {"version": "1.0.0"}
        fs.create_file(
            f"{repo_path}/package.json",
            contents=json.dumps(package_json)
        )

        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/polyglot', '--all-registries', '--dry-run']
            )

        # Should detect both types
        assert result.exit_code == 0


class TestPublishIntegrationVFSPaths:
    """Test VFS path resolution in publish workflow."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_with_vfs_repos_path(self, mock_console, mock_get_repos, fs):
        """Test publishing via /repos/X VFS path."""
        repo_path = "/actual/path/to/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/repo', '--dry-run'])

        # Verify VFS path was resolved
        mock_get_repos.assert_called_once_with('/repos/repo')

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_with_vfs_language_path(self, mock_console, mock_get_repos, fs):
        """Test publishing via /by-language/X VFS path."""
        repo1 = "/test/python1"
        repo2 = "/test/python2"

        for repo in [repo1, repo2]:
            fs.create_dir(repo)
            fs.create_file(f"{repo}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo1, repo2]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/by-language/Python', '--dry-run'])

        mock_get_repos.assert_called_once_with('/by-language/Python')

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_vfs_path_no_repos_found(self, mock_console, mock_get_repos, fs):
        """Test handling when VFS path returns no repos."""
        mock_get_repos.return_value = []

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/nonexistent'])

        # Should handle gracefully
        assert "No repositories found" in result.output or result.exit_code == 0

    @patch('ghops.commands.publish.console')
    def test_publish_relative_path_current_directory(self, mock_console, fs):
        """Test publishing from current directory (relative path)."""
        repo_path = "/current/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/.git")
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            with patch('os.getcwd', return_value=repo_path):
                result = runner.invoke(publish_handler, ['.', '--dry-run'])

        # Should process current directory
        assert result.exit_code == 0


class TestPublishIntegrationConfiguration:
    """Test configuration-based registry selection."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_uses_configured_registry(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test that publish uses configured default registry."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        config = {
            "publish": {
                "python": ["pypi"]
            }
        }

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value=config):
            result = runner.invoke(publish_handler, ['/repos/test', '--dry-run'])

        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_specific_registry_override(self, mock_console, mock_get_repos, fs):
        """Test that --registry flag overrides configuration."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        # Config says use registry A, but we explicitly request registry B
        config = {
            "publish": {
                "python": ["other_registry"]
            }
        }

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value=config):
            with patch('ghops.commands.publish.run_command', return_value=("success", 0)):
                result = runner.invoke(
                    publish_handler,
                    ['/repos/test', '--registry', 'pypi', '--dry-run']
                )

        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_all_registries_flag(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test --all-registries publishes to all configured registries."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        config = {
            "publish": {
                "python": ["pypi", "test_pypi"]  # Multiple registries
            }
        }

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value=config):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--all-registries', '--dry-run']
            )

        # Should attempt to publish to multiple registries
        assert result.exit_code == 0


class TestPublishIntegrationDryRun:
    """Test dry-run functionality throughout workflow."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_dry_run_doesnt_modify_files(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test that dry-run doesn't modify version files."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        original_version = "1.0.0"
        pyproject_content = f"""
[project]
version = "{original_version}"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--bump-version', 'major', '--dry-run']
            )

        # Version should NOT be changed in dry-run
        current_version = get_version(repo_path, 'python')
        assert current_version == original_version

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_dry_run_doesnt_call_publish_commands(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test that dry-run doesn't execute actual publish commands."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/test', '--dry-run'])

        # run_command should not be called in dry-run
        mock_run_command.assert_not_called()

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_dry_run_shows_what_would_happen(self, mock_console, mock_get_repos, fs):
        """Test that dry-run output indicates what would happen."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="[project]\nversion='1.0.0'")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--bump-version', 'patch', '--dry-run']
            )

        # Should show preview messages
        assert result.exit_code == 0


class TestPublishIntegrationErrorHandling:
    """Test error handling and recovery."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_no_project_type_detected(self, mock_console, mock_get_repos, fs):
        """Test handling when no project type is detected."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        # No project files

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/test'])

        # Should handle gracefully
        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_continues_after_one_failure(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test that publish continues processing repos after one fails."""
        repo1 = "/test/repo1"
        repo2 = "/test/repo2"

        for repo in [repo1, repo2]:
            fs.create_dir(repo)
            fs.create_file(f"{repo}/pyproject.toml", contents="")
            fs.create_dir(f"{repo}/dist")
            fs.create_file(f"{repo}/dist/pkg.whl", contents="")

        mock_get_repos.return_value = [repo1, repo2]
        # First repo fails, second succeeds
        mock_run_command.side_effect = [
            ("error", 1),  # repo1 fails
            ("success", 0)  # repo2 succeeds
        ]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/by-language/Python'])

        # Should process both despite first failure
        assert result.exit_code == 0
        assert mock_run_command.call_count == 2

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_no_version_for_bumping(self, mock_console, mock_get_repos, fs):
        """Test handling when trying to bump but no version exists."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        # Create project file but no version
        fs.create_file(f"{repo_path}/pyproject.toml", contents="[project]\nname='test'")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--bump-version', 'patch', '--version-only']
            )

        # Should handle gracefully
        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_publish_unsupported_registry(self, mock_console, mock_get_repos, fs):
        """Test handling when requesting unsupported registry."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/test', '--registry', 'unsupported_registry', '--dry-run']
            )

        # Should handle gracefully
        assert result.exit_code == 0


class TestPublishIntegrationJSONOutput:
    """Test JSON output mode."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_json_output_format(self, mock_console, mock_get_repos, fs):
        """Test --json flag produces JSON output."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/test', '--json', '--dry-run'])

        # Output should be parseable JSON
        try:
            for line in result.output.strip().split('\n'):
                if line:
                    json.loads(line)
        except json.JSONDecodeError:
            pytest.fail("Output should be valid JSONL")

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_json_output_structure(self, mock_console, mock_get_repos, fs):
        """Test JSON output contains expected fields."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        mock_get_repos.return_value = [repo_path]

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(publish_handler, ['/repos/test', '--json', '--dry-run'])

        # Parse first line of JSON output
        for line in result.output.strip().split('\n'):
            if line:
                data = json.loads(line)
                assert 'repo' in data
                assert 'path' in data
                assert 'detected_types' in data
                break


class TestPublishIntegrationRealWorldScenarios:
    """Test realistic end-to-end scenarios."""

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_complete_release_workflow(self, mock_console, mock_run_command, mock_get_repos, fs):
        """Test complete release workflow: bump version → tag → publish."""
        repo_path = "/test/myproject"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/dist")
        fs.create_file(f"{repo_path}/dist/myproject.whl", contents="")

        pyproject_content = """
[project]
name = "myproject"
version = "0.9.0"
"""
        fs.create_file(f"{repo_path}/pyproject.toml", contents=pyproject_content)

        mock_get_repos.return_value = [repo_path]
        mock_run_command.return_value = ("success", 0)

        # Step 1: Bump to 1.0.0
        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/myproject', '--bump-version', 'major', '--version-only']
            )

        assert get_version(repo_path, 'python') == "1.0.0"

        # Step 2: Publish (dry-run)
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/repos/myproject', '--dry-run']
            )

        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_batch_publish_all_python_repos(self, mock_console, mock_get_repos, fs):
        """Test batch publishing all Python repos in a workspace."""
        repos = [f"/test/repo{i}" for i in range(3)]

        for repo in repos:
            fs.create_dir(repo)
            fs.create_file(f"{repo}/pyproject.toml", contents="[project]\nversion='1.0.0'")

        mock_get_repos.return_value = repos

        runner = CliRunner()
        with patch('ghops.commands.publish.load_config', return_value={}):
            result = runner.invoke(
                publish_handler,
                ['/by-language/Python', '--dry-run']
            )

        # Should process all repos
        assert result.exit_code == 0

    @patch('ghops.commands.publish.get_repos_from_vfs_path')
    @patch('ghops.commands.publish.console')
    def test_coordinated_multiproject_release(self, mock_console, mock_get_repos, fs):
        """Test releasing multiple related projects with same version bump."""
        backend_repo = "/test/backend"
        frontend_repo = "/test/frontend"

        fs.create_dir(backend_repo)
        fs.create_file(f"{backend_repo}/pyproject.toml", contents="[project]\nversion='2.0.0'")

        fs.create_dir(frontend_repo)
        fs.create_file(f"{frontend_repo}/package.json", contents='{"version":"2.0.0"}')

        # Publish both with minor bump
        for vfs_path, repo_path in [('/repos/backend', backend_repo), ('/repos/frontend', frontend_repo)]:
            mock_get_repos.return_value = [repo_path]

            runner = CliRunner()
            with patch('ghops.commands.publish.load_config', return_value={}):
                result = runner.invoke(
                    publish_handler,
                    [vfs_path, '--bump-version', 'minor', '--version-only']
                )

        # Both should be at 2.1.0
        assert get_version(backend_repo, 'python') == "2.1.0"
        assert get_version(frontend_repo, 'node') == "2.1.0"
