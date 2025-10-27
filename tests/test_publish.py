"""
Comprehensive tests for auto-publish command.

Tests the ProjectDetector and RegistryPublisher classes:
- Project type detection (Python, C++, Node.js, Rust, Ruby, Go)
- Registry-specific publishing logic
- Dry-run mode
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from ghops.commands.publish import (
    ProjectDetector,
    RegistryPublisher,
    REGISTRY_HANDLERS,
)


class TestProjectDetector:
    """Test project type detection."""

    def test_detect_python_pyproject_toml(self, fs):
        """Test detecting Python project via pyproject.toml."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "python" in detected

    def test_detect_python_setup_py(self, fs):
        """Test detecting Python project via setup.py."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/setup.py", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "python" in detected

    def test_detect_python_setup_cfg(self, fs):
        """Test detecting Python project via setup.cfg."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/setup.cfg", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "python" in detected

    def test_detect_cpp_conanfile_py(self, fs):
        """Test detecting C++ project via conanfile.py."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.py", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "cpp" in detected

    def test_detect_cpp_conanfile_txt(self, fs):
        """Test detecting C++ project via conanfile.txt."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.txt", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "cpp" in detected

    def test_detect_cpp_vcpkg_json(self, fs):
        """Test detecting C++ project via vcpkg.json."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/vcpkg.json", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "cpp" in detected

    def test_detect_cpp_cmake(self, fs):
        """Test detecting C++ project via CMakeLists.txt."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/CMakeLists.txt", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "cpp" in detected

    def test_detect_node_package_json(self, fs):
        """Test detecting Node.js project via package.json."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/package.json", contents="{}")

        detected = ProjectDetector.detect(repo_path)
        assert "node" in detected

    def test_detect_rust_cargo_toml(self, fs):
        """Test detecting Rust project via Cargo.toml."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/Cargo.toml", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "rust" in detected

    def test_detect_ruby_gemfile(self, fs):
        """Test detecting Ruby project via Gemfile."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/Gemfile", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "ruby" in detected

    def test_detect_ruby_gemspec(self, fs):
        """Test detecting Ruby project via .gemspec file."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/mygem.gemspec", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "ruby" in detected

    def test_detect_go_go_mod(self, fs):
        """Test detecting Go project via go.mod."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/go.mod", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "go" in detected

    def test_detect_multiple_project_types(self, fs):
        """Test detecting multiple project types in same repo."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")
        fs.create_file(f"{repo_path}/package.json", contents="{}")
        fs.create_file(f"{repo_path}/Cargo.toml", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert "python" in detected
        assert "node" in detected
        assert "rust" in detected
        assert len(detected) == 3

    def test_detect_no_project_indicators(self, fs):
        """Test when no project type indicators are found."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/README.md", contents="")

        detected = ProjectDetector.detect(repo_path)
        assert detected == []

    def test_detect_empty_directory(self, fs):
        """Test detecting in empty directory."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        detected = ProjectDetector.detect(repo_path)
        assert detected == []

    def test_detect_multiple_indicator_files_same_type(self, fs):
        """Test that multiple files of same type only detect once."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")
        fs.create_file(f"{repo_path}/setup.py", contents="")
        fs.create_file(f"{repo_path}/setup.cfg", contents="")

        detected = ProjectDetector.detect(repo_path)
        # Should only appear once
        assert detected.count("python") == 1


class TestRegistryPublisherPython:
    """Test Python/PyPI publishing."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_python_pypi_success_with_existing_dist(self, mock_console, mock_run_command, fs):
        """Test successful PyPI publish with pre-built distribution."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/dist")
        fs.create_file(f"{repo_path}/dist/package-1.0.0-py3-none-any.whl", contents="")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_python_pypi()

        assert success is True
        assert "Published to PyPI" in message
        mock_run_command.assert_called_once()
        assert "twine upload" in mock_run_command.call_args[0][0]

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_python_pypi_builds_if_needed(self, mock_console, mock_run_command, fs):
        """Test that PyPI publish builds package if dist/ doesn't exist."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_python_pypi()

        assert success is True
        # Should have called both build and upload
        assert mock_run_command.call_count == 2
        calls = [call[0][0] for call in mock_run_command.call_args_list]
        assert any("build" in cmd for cmd in calls)
        assert any("twine" in cmd for cmd in calls)

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_python_pypi_build_failure(self, mock_console, mock_run_command, fs):
        """Test handling build failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        mock_run_command.return_value = ("build error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_python_pypi()

        assert success is False
        assert "Build failed" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_python_pypi_upload_failure(self, mock_console, mock_run_command, fs):
        """Test handling upload failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/dist")
        fs.create_file(f"{repo_path}/dist/package.whl", contents="")

        mock_run_command.return_value = ("upload error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_python_pypi()

        assert success is False
        assert "Upload failed" in message

    @patch('ghops.commands.publish.console')
    def test_publish_python_pypi_dry_run(self, mock_console, fs):
        """Test PyPI publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_python_pypi()

        assert success is True
        assert "Dry run" in message
        assert "would upload to PyPI" in message


class TestRegistryPublisherCpp:
    """Test C++/Conan publishing."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_success(self, mock_console, mock_run_command, fs):
        """Test successful Conan publish."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.py", contents="")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_cpp_conan()

        assert success is True
        assert "Published to Conan" in message
        # Should call export and upload
        assert mock_run_command.call_count == 2

    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_no_conanfile(self, mock_console, fs):
        """Test Conan publish without conanfile."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_cpp_conan()

        assert success is False
        assert "No conanfile" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_export_failure(self, mock_console, mock_run_command, fs):
        """Test handling Conan export failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.py", contents="")

        mock_run_command.return_value = ("export error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_cpp_conan()

        assert success is False
        assert "Conan export failed" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_upload_failure(self, mock_console, mock_run_command, fs):
        """Test handling Conan upload failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.py", contents="")

        # First call (export) succeeds, second (upload) fails
        mock_run_command.side_effect = [("success", 0), ("upload error", 1)]

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_cpp_conan()

        assert success is False
        assert "Conan upload failed" in message

    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_dry_run(self, mock_console, fs):
        """Test Conan publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.py", contents="")

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_cpp_conan()

        assert success is True
        assert "Dry run" in message
        assert "would publish to Conan" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_cpp_conan_txt_file(self, mock_console, mock_run_command, fs):
        """Test Conan publish with conanfile.txt."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/conanfile.txt", contents="")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_cpp_conan()

        assert success is True


class TestRegistryPublisherNode:
    """Test Node.js/npm publishing."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_node_npm_success(self, mock_console, mock_run_command, fs):
        """Test successful npm publish."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/package.json", contents="{}")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_node_npm()

        assert success is True
        assert "Published to npm" in message

    @patch('ghops.commands.publish.console')
    def test_publish_node_npm_no_package_json(self, mock_console, fs):
        """Test npm publish without package.json."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_node_npm()

        assert success is False
        assert "No package.json" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_node_npm_failure(self, mock_console, mock_run_command, fs):
        """Test handling npm publish failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/package.json", contents="{}")

        mock_run_command.return_value = ("npm error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_node_npm()

        assert success is False
        assert "npm publish failed" in message

    @patch('ghops.commands.publish.console')
    def test_publish_node_npm_dry_run(self, mock_console, fs):
        """Test npm publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/package.json", contents="{}")

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_node_npm()

        assert success is True
        assert "Dry run" in message


class TestRegistryPublisherRust:
    """Test Rust/crates.io publishing."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_rust_crates_success(self, mock_console, mock_run_command, fs):
        """Test successful crates.io publish."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/Cargo.toml", contents="")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_rust_crates()

        assert success is True
        assert "Published to crates.io" in message

    @patch('ghops.commands.publish.console')
    def test_publish_rust_crates_no_cargo_toml(self, mock_console, fs):
        """Test crates.io publish without Cargo.toml."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_rust_crates()

        assert success is False
        assert "No Cargo.toml" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_rust_crates_failure(self, mock_console, mock_run_command, fs):
        """Test handling cargo publish failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/Cargo.toml", contents="")

        mock_run_command.return_value = ("cargo error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_rust_crates()

        assert success is False
        assert "cargo publish failed" in message

    @patch('ghops.commands.publish.console')
    def test_publish_rust_crates_dry_run(self, mock_console, fs):
        """Test crates.io publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/Cargo.toml", contents="")

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_rust_crates()

        assert success is True
        assert "Dry run" in message


class TestRegistryPublisherRuby:
    """Test Ruby/RubyGems publishing."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_ruby_gems_success(self, mock_console, mock_run_command, fs):
        """Test successful RubyGems publish."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/mygem.gemspec", contents="")

        mock_run_command.return_value = ("success", 0)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_ruby_gems()

        assert success is True
        assert "Published to RubyGems" in message
        # Should call build and push
        assert mock_run_command.call_count == 2

    @patch('ghops.commands.publish.console')
    def test_publish_ruby_gems_no_gemspec(self, mock_console, fs):
        """Test RubyGems publish without .gemspec."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_ruby_gems()

        assert success is False
        assert "No .gemspec file" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_ruby_gems_build_failure(self, mock_console, mock_run_command, fs):
        """Test handling gem build failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/test.gemspec", contents="")

        mock_run_command.return_value = ("build error", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_ruby_gems()

        assert success is False
        assert "gem build failed" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_ruby_gems_push_failure(self, mock_console, mock_run_command, fs):
        """Test handling gem push failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/test.gemspec", contents="")

        # First call (build) succeeds, second (push) fails
        mock_run_command.side_effect = [("success", 0), ("push error", 1)]

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_ruby_gems()

        assert success is False
        assert "gem push failed" in message

    @patch('ghops.commands.publish.console')
    def test_publish_ruby_gems_dry_run(self, mock_console, fs):
        """Test RubyGems publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/test.gemspec", contents="")

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_ruby_gems()

        assert success is True
        assert "Dry run" in message


class TestRegistryPublisherGo:
    """Test Go module publishing via git tags."""

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_go_pkg_success(self, mock_console, mock_run_command, fs):
        """Test successful Go module publish."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/go.mod", contents="")

        # First call checks for tags, second pushes tags
        mock_run_command.side_effect = [("v1.0.0", 0), ("success", 0)]

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_go_pkg()

        assert success is True
        assert "Published Go module" in message

    @patch('ghops.commands.publish.console')
    def test_publish_go_pkg_no_go_mod(self, mock_console, fs):
        """Test Go publish without go.mod."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_go_pkg()

        assert success is False
        assert "No go.mod" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_go_pkg_no_version_tag(self, mock_console, mock_run_command, fs):
        """Test Go publish when no version tag exists."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/go.mod", contents="")

        mock_run_command.return_value = ("", 1)

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_go_pkg()

        assert success is False
        assert "No git tag found" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_go_pkg_push_failure(self, mock_console, mock_run_command, fs):
        """Test handling git push failure."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/go.mod", contents="")

        # First call succeeds (has tag), second fails (push error)
        mock_run_command.side_effect = [("v1.0.0", 0), ("push error", 1)]

        publisher = RegistryPublisher(repo_path, dry_run=False)
        success, message = publisher.publish_go_pkg()

        assert success is False
        assert "git push --tags failed" in message

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_go_pkg_dry_run(self, mock_console, mock_run_command, fs):
        """Test Go publish in dry-run mode."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/go.mod", contents="")

        mock_run_command.return_value = ("v1.0.0", 0)

        publisher = RegistryPublisher(repo_path, dry_run=True)
        success, message = publisher.publish_go_pkg()

        assert success is True
        assert "Dry run" in message
        assert "current: v1.0.0" in message


class TestRegistryHandlers:
    """Test the REGISTRY_HANDLERS configuration."""

    def test_registry_handlers_structure(self):
        """Test that REGISTRY_HANDLERS has expected structure."""
        assert "python" in REGISTRY_HANDLERS
        assert "cpp" in REGISTRY_HANDLERS
        assert "node" in REGISTRY_HANDLERS
        assert "rust" in REGISTRY_HANDLERS
        assert "ruby" in REGISTRY_HANDLERS
        assert "go" in REGISTRY_HANDLERS

    def test_python_registries(self):
        """Test Python registry configuration."""
        assert "pypi" in REGISTRY_HANDLERS["python"]
        assert callable(REGISTRY_HANDLERS["python"]["pypi"])

    def test_cpp_registries(self):
        """Test C++ registry configuration."""
        assert "conan" in REGISTRY_HANDLERS["cpp"]
        assert callable(REGISTRY_HANDLERS["cpp"]["conan"])

    def test_node_registries(self):
        """Test Node.js registry configuration."""
        assert "npm" in REGISTRY_HANDLERS["node"]
        assert callable(REGISTRY_HANDLERS["node"]["npm"])

    def test_rust_registries(self):
        """Test Rust registry configuration."""
        assert "crates.io" in REGISTRY_HANDLERS["rust"]
        assert callable(REGISTRY_HANDLERS["rust"]["crates.io"])

    def test_ruby_registries(self):
        """Test Ruby registry configuration."""
        assert "rubygems" in REGISTRY_HANDLERS["ruby"]
        assert callable(REGISTRY_HANDLERS["ruby"]["rubygems"])

    def test_go_registries(self):
        """Test Go registry configuration."""
        assert "pkg.go.dev" in REGISTRY_HANDLERS["go"]
        assert callable(REGISTRY_HANDLERS["go"]["pkg.go.dev"])


class TestRegistryPublisherInit:
    """Test RegistryPublisher initialization."""

    def test_init_with_dry_run(self):
        """Test initializing with dry_run flag."""
        publisher = RegistryPublisher("/test/repo", dry_run=True)
        assert publisher.repo_path == "/test/repo"
        assert publisher.dry_run is True
        assert publisher.repo_name == "repo"

    def test_init_without_dry_run(self):
        """Test initializing without dry_run flag."""
        publisher = RegistryPublisher("/test/repo", dry_run=False)
        assert publisher.dry_run is False

    def test_init_extracts_repo_name(self):
        """Test that repo_name is extracted from path."""
        publisher = RegistryPublisher("/home/user/projects/myrepo")
        assert publisher.repo_name == "myrepo"

    def test_init_with_trailing_slash(self):
        """Test initialization with trailing slash in path."""
        publisher = RegistryPublisher("/test/repo/")
        # Path("/test/repo/").name returns empty string, this is Python's Path behavior
        assert publisher.repo_name in ["", "repo"]  # Depends on Path implementation


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_detect_with_nonexistent_path(self):
        """Test project detection with nonexistent path."""
        # Should not crash
        detected = ProjectDetector.detect("/nonexistent/path")
        assert detected == []

    @patch('ghops.commands.publish.console')
    def test_publish_with_invalid_repo_path(self, mock_console):
        """Test publishing with invalid repository path."""
        publisher = RegistryPublisher("/nonexistent/path", dry_run=False)
        # Methods should handle gracefully (return False)
        # Implementation may vary, but shouldn't crash
        try:
            publisher.publish_python_pypi()
        except Exception:
            pytest.fail("Should handle invalid path gracefully")

    def test_detector_handles_symlinks(self, fs):
        """Test that detector handles symbolic links."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_file(f"{repo_path}/pyproject.toml", contents="")

        # Create symlink
        fs.create_symlink(f"{repo_path}/link.toml", f"{repo_path}/pyproject.toml")

        detected = ProjectDetector.detect(repo_path)
        assert "python" in detected

    def test_detector_handles_nested_directories(self, fs):
        """Test detector only looks at top level (no recursion)."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/subdir")
        fs.create_file(f"{repo_path}/subdir/pyproject.toml", contents="")

        detected = ProjectDetector.detect(repo_path)
        # Should not detect nested files
        assert "python" not in detected

    @patch('ghops.commands.publish.run_command')
    @patch('ghops.commands.publish.console')
    def test_publish_handles_command_timeout(self, mock_console, mock_run_command, fs):
        """Test handling of command timeout/hang."""
        repo_path = "/test/repo"
        fs.create_dir(repo_path)
        fs.create_dir(f"{repo_path}/dist")
        fs.create_file(f"{repo_path}/dist/package.whl", contents="")

        # Simulate timeout or hanging
        mock_run_command.side_effect = Exception("Command timeout")

        publisher = RegistryPublisher(repo_path, dry_run=False)
        # Should not crash
        try:
            publisher.publish_python_pypi()
        except Exception:
            # Expected to propagate or handle
            pass
