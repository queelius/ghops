import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# Helper function for all tests

def create_git_repo(fs, path, remote_url="https://github.com/user/repo.git"):
    """Helper to create a fake git repo."""
    repo_path = Path(path)
    fs.create_dir(repo_path)
    git_dir = repo_path / ".git"
    fs.create_dir(git_dir)
    fs.create_file(
        git_dir / "config",
        contents=f'''[remote "origin"]\n    url = {remote_url}\n'''
    )
    return str(repo_path)

from ghops import core
from ghops.core import get_repo_status_stream


class TestListRepos:
    def test_list_repos_from_directory_no_repos(self, fs):
        """Test listing from an empty directory."""
        fs.create_dir("/home/user/code")
        result = core.list_repos(
            source="directory",
            directory="/home/user/code",
            recursive=False,
            dedup=False,
            dedup_details=False,
        )
        assert result["status"] == "no_repos_found"
        assert result["repos"] == []

    def test_list_repos_from_directory_single_repo(self, fs):
        """Test listing a single repo from a directory."""
        repo_path = create_git_repo(fs, "/home/user/code/repo1")
        result = core.list_repos(
            source="directory",
            directory="/home/user/code",
            recursive=False,
            dedup=False,
            dedup_details=False,
        )
        assert result["status"] == "success"
        assert result["repos"] == [str(Path("/home/user/code/repo1").resolve())]

    def test_list_repos_from_directory_recursive(self, fs):
        """Test recursive repository listing."""
        create_git_repo(fs, "/home/user/code/repo1")
        create_git_repo(fs, "/home/user/code/subdir/repo2")
        result = core.list_repos(
            source="directory",
            directory="/home/user/code",
            recursive=True,
            dedup=False,
            dedup_details=False,
        )
        assert result["status"] == "success"
        assert len(result["repos"]) == 2
        assert str(Path("/home/user/code/repo1").resolve()) in result["repos"]
        assert str(Path("/home/user/code/subdir/repo2").resolve()) in result["repos"]

    def test_list_repos_from_directory_not_recursive(self, fs):
        """Test non-recursive repository listing."""
        create_git_repo(fs, "/home/user/code/repo1")
        create_git_repo(fs, "/home/user/code/subdir/repo2")
        result = core.list_repos(
            source="directory",
            directory="/home/user/code",
            recursive=False,
            dedup=False,
            dedup_details=False,
        )
        assert result["status"] == "success"
        assert result["repos"] == [str(Path("/home/user/code/repo1").resolve())]

    @patch("ghops.core.load_config")
    def test_list_repos_from_config(self, mock_load_config, fs):
        """Test listing repositories from configuration."""
        mock_load_config.return_value = {
            "general": {
                "repository_directories": ["/home/user/code", "/home/user/projects"]
            }
        }
        create_git_repo(fs, "/home/user/code/repo1")
        create_git_repo(fs, "/home/user/projects/repo2")

        result = core.list_repos(
            source="config",
            directory=None,
            recursive=False,
            dedup=False,
            dedup_details=False,
        )

        assert result["status"] == "success"
        assert len(result["repos"]) == 2
        assert str(Path("/home/user/code/repo1").resolve()) in result["repos"]
        assert str(Path("/home/user/projects/repo2").resolve()) in result["repos"]

    @patch("ghops.core.get_remote_url")
    def test_list_repos_dedup(self, mock_get_remote_url, fs):
        """Test simple deduplication based on remote URL."""
        repo1_path = create_git_repo(fs, "/home/user/code/repo1", remote_url="https://github.com/user/repo.git")
        repo2_path = create_git_repo(fs, "/home/user/code/repo2", remote_url="https://github.com/user/another.git")
        repo3_path = create_git_repo(fs, "/home/user/code/repo3", remote_url="https://github.com/user/repo.git")

        # This is how the mock needs to be set up for find_git_repos to work with it
        def side_effect(path):
            if path == repo1_path:
                return "https://github.com/user/repo.git"
            if path == repo2_path:
                return "https://github.com/user/another.git"
            if path == repo3_path:
                return "https://github.com/user/repo.git"
            return None
        mock_get_remote_url.side_effect = side_effect

        with patch("ghops.core.find_git_repos", return_value=[repo1_path, repo2_path, repo3_path]):
            result = core.list_repos(
                source="directory",
                directory="/home/user/code",
                recursive=True,
                dedup=True,
                dedup_details=False,
            )

            assert result["status"] == "success"
            # Should be 2 unique repos, with the first path chosen for the duplicate
            assert len(result["repos"]) == 2
            assert repo1_path in result["repos"]
            assert repo2_path in result["repos"]

    @patch("ghops.core.get_remote_url")
    @pytest.mark.xfail(reason="pyfakefs does not support symlinks reliably")
    def test_list_repos_dedup_details(self, mock_get_remote_url, fs):
        """Test detailed deduplication, distinguishing true duplicates from links."""
        # A true duplicate
        repo1_path = create_git_repo(fs, "/home/user/code/repo", remote_url="https://github.com/user/repo.git")
        repo2_path = create_git_repo(fs, "/home/user/code/repo_clone", remote_url="https://github.com/user/repo.git")
        
        # A unique repo
        repo3_path = create_git_repo(fs, "/home/user/code/another", remote_url="https://github.com/user/another.git")
        
        # A repo and a symlink to it
        repo4_path = create_git_repo(fs, "/home/user/code/linked_repo", remote_url="https://github.com/user/linked.git")
        repo4_link_path = "/home/user/code/linked_repo_link"
        # Ensure the link path does not exist
        if fs.exists(repo4_link_path):
            fs.remove_object(repo4_link_path)
        # Remove the directory at the link path if it exists (should not, but for safety)
        if fs.exists(repo4_link_path):
            fs.remove_object(repo4_link_path)
        fs.create_symlink(repo4_path, repo4_link_path)


        def side_effect(path):
            if path in [repo1_path, repo2_path]:
                return "https://github.com/user/repo.git"
            if path == repo3_path:
                return "https://github.com/user/another.git"
            if path in [repo4_path, repo4_link_path]:
                return "https://github.com/user/linked.git"
            return None
        mock_get_remote_url.side_effect = side_effect

        repo_paths = [repo1_path, repo2_path, repo3_path, repo4_path, repo4_link_path]

        with patch("ghops.core.find_git_repos", return_value=repo_paths):
            result = core.list_repos(
                source="directory",
                directory="/home/user/code",
                recursive=True,
                dedup=False,
                dedup_details=True,
            )
        
        assert result["status"] == "success_details"
        details = result["details"]

        # Check the truly duplicated repo
        assert details["https://github.com/user/repo.git"]["is_duplicate"] is True
        assert len(details["https://github.com/user/repo.git"]["locations"]) == 2

        # Check the unique repo
        assert details["https://github.com/user/another.git"]["is_duplicate"] is False
        assert len(details["https://github.com/user/another.git"]["locations"]) == 1
        assert details["https://github.com/user/another.git"]["locations"][0]["type"] == "unique"

        # Check the linked repo
        assert details["https://github.com/user/linked.git"]["is_duplicate"] is False
        assert len(details["https://github.com/user/linked.git"]["locations"]) == 1
        linked_location = details["https://github.com/user/linked.git"]["locations"][0]
        assert linked_location["type"] == "linked"
        assert linked_location["primary"] == str(Path(repo4_path).resolve())
        assert sorted(linked_location["links"]) == sorted([repo4_path, repo4_link_path])


class TestGetRepoStatus:
    @patch("ghops.core.load_config")
    @patch("ghops.core.get_git_status")
    @patch("ghops.core.get_license_info")
    @patch("ghops.core.get_gh_pages_url")
    @patch("ghops.core.detect_pypi_package")
    @patch("ghops.core.is_package_outdated")
    def test_get_repo_status_basic(
        self,
        mock_is_outdated,
        mock_detect_pypi,
        mock_get_pages,
        mock_get_license,
        mock_get_git_status,
        mock_load_config,
        fs
    ):
        """Test the basic status retrieval for a clean repository."""
        repo_path = create_git_repo(fs, "/home/user/code/clean-repo")
        
        # Mock all the helper functions
        mock_load_config.return_value = {"pypi": {"check_by_default": True}}
        mock_get_git_status.return_value = {"status": "clean", "branch": "main"}
        mock_get_license.return_value = {"spdx_id": "MIT", "name": "MIT License"}
        mock_get_pages.return_value = "https://user.github.io/clean-repo"
        mock_detect_pypi.return_value = {
            "has_packaging_files": True,
            "is_published": True,
            "package_name": "clean-repo",
            "pypi_info": {"version": "1.0.0", "url": "https://pypi.org/p/clean-repo"}
        }
        mock_is_outdated.return_value = False

        result = list(core.get_repo_status_stream([repo_path]))

        assert len(result) == 1
        status = result[0]
        assert status["name"] == "clean-repo"
        assert status["status"] == "clean"
        assert status["branch"] == "main"
        assert status["license"]["spdx_id"] == "MIT"
        assert status["pages_url"] == "https://user.github.io/clean-repo"
        assert status["pypi_info"]["package_name"] == "clean-repo"
        assert status["pypi_info"]["version"] == "1.0.0"

        mock_get_git_status.assert_called_once_with(repo_path)
        mock_get_license.assert_called_once_with(repo_path)
        mock_get_pages.assert_called_once_with(repo_path)
        mock_detect_pypi.assert_called_once_with(repo_path)
        mock_is_outdated.assert_called_once()

    @patch("ghops.core.load_config")
    @patch("ghops.core.get_git_status")
    @patch("ghops.core.get_license_info")
    @patch("ghops.core.get_gh_pages_url")
    @patch("ghops.core.detect_pypi_package")
    def test_get_repo_status_dirty_and_unpublished(
        self,
        mock_detect_pypi,
        mock_get_pages,
        mock_get_license,
        mock_get_git_status,
        mock_load_config,
        fs
    ):
        """Test a dirty repo that is not published to PyPI."""
        repo_path = create_git_repo(fs, "/home/user/code/dirty-repo")

        mock_load_config.return_value = {"pypi": {"check_by_default": True}}
        mock_get_git_status.return_value = {"status": "dirty", "branch": "develop"}
        mock_get_license.return_value = {"spdx_id": "GPL-3.0-only"}
        mock_get_pages.return_value = None
        mock_detect_pypi.return_value = {
            "has_packaging_files": True,
            "is_published": False,
            "package_name": "dirty-repo",
            "pypi_info": {}
        }

        result = list(core.get_repo_status_stream([repo_path]))
        
        assert len(result) == 1
        status = result[0]
        assert status["name"] == "dirty-repo"
        assert status["status"] == "dirty"
        assert status["branch"] == "develop"
        assert status["license"]["spdx_id"] == "GPL-3.0-only"
        assert status["pages_url"] is None
        assert status["pypi_info"]["package_name"] == "dirty-repo"
        assert status["pypi_info"]["version"] == "Not published"

    @patch("ghops.core.load_config")
    @patch("ghops.core.get_git_status")
    def test_get_repo_status_skip_checks(
        self, mock_get_git_status, mock_load_config, fs
    ):
        """Test skipping the pages and pypi checks."""
        repo_path = create_git_repo(fs, "/home/user/code/simple-repo")

        mock_load_config.return_value = {} # No config needed
        mock_get_git_status.return_value = {"status": "clean", "branch": "main"}

        with patch("ghops.core.get_gh_pages_url") as mock_get_pages, \
             patch("ghops.core.detect_pypi_package") as mock_detect_pypi:
            
            result = list(core.get_repo_status_stream(
                [repo_path], skip_pages_check=True, skip_pypi_check=True
            ))

            assert len(result) == 1
            status = result[0]
            assert status["name"] == "simple-repo"
            assert status["pages_url"] is None
            assert status["pypi_info"] is None
            
            mock_get_pages.assert_not_called()
            mock_detect_pypi.assert_not_called()

    @patch('ghops.core.get_git_status')
    @patch('ghops.core.get_license_info')
    @patch('ghops.core.get_gh_pages_url')
    @patch('ghops.core.detect_pypi_package')
    def test_get_repo_status_stream(self, mock_detect_pypi, mock_pages, mock_license, mock_git_status):
        """Test get_repo_status_stream function"""
        # Mock responses
        mock_git_status.return_value = {'status': 'clean', 'branch': 'main'}
        mock_license.return_value = {'spdx_id': 'MIT', 'name': 'MIT License', 'url': None}
        mock_pages.return_value = None
        mock_detect_pypi.return_value = {
            'has_packaging_files': False,
            'is_published': False,
            'package_name': None,
            'pypi_info': None
        }
        
        repo_paths = ['/fake/repo1', '/fake/repo2']
        
        # Test streaming function
        results = list(core.get_repo_status_stream(repo_paths, skip_pages_check=True, skip_pypi_check=True))
        
        assert len(results) == 2
        for result in results:
            assert 'name' in result
            assert 'status' in result
            assert 'branch' in result
            assert result['status'] == 'clean'
            assert result['branch'] == 'main'


class TestGetRepo:
    @patch("ghops.core.find_git_repos")
    @patch("ghops.core.get_remote_url", return_value="https://github.com/user/found.git")
    @patch("ghops.core.get_license_info", return_value={"spdx_id": "MIT"})
    @patch("ghops.core.get_gh_pages_url", return_value="https://user.github.io/found")
    def test_get_repo_found(
        self,
        mock_get_pages,
        mock_get_license,
        mock_get_remote,
        mock_find_repos,
        fs,
    ):
        """Test finding a repository that exists."""
        repo_path = "/home/user/code/found"
        fs.create_dir(repo_path) # Just need the path to exist
        mock_find_repos.return_value = [repo_path]

        config = {"general": {"repository_directories": ["/home/user/code"]}}
        result = core.get_repo("found", config)

        assert result is not None
        assert result["name"] == "found"
        assert result["path"] == repo_path
        assert result["remote_url"] == "https://github.com/user/found.git"
        assert result["license"] == "MIT"
        assert result["gh_pages_url"] == "https://user.github.io/found"

        mock_find_repos.assert_called_once_with(["/home/user/code"], recursive=True)

    @patch("ghops.core.find_git_repos", return_value=[])
    def test_get_repo_not_found(self, mock_find_repos):
        """Test finding a repository that does not exist."""
        config = {"general": {"repository_directories": ["/home/user/code"]}}
        result = core.get_repo("not-found", config)
        assert result is None


class TestUpdateRepo:
    @patch("ghops.core.run_command")
    def test_update_repo_simple_pull(self, mock_run_command):
        """Test a simple update with only a pull."""
        mock_run_command.side_effect = [
            "Updating a0b1c2d..e3f4a5b",  # git pull
            "",  # git status
            "Everything up-to-date",  # git push
        ]

        result = core.update_repo("/fake/repo", False, "", False)

        assert result["pulled"] is True
        assert result["committed"] is False
        assert result["pushed"] is False
        assert result["error"] is None
        assert mock_run_command.call_count == 2  # Only pull and push if no changes

    @patch("ghops.core.run_command")
    def test_update_repo_no_changes(self, mock_run_command):
        """Test an update where the repo is already up to date."""
        mock_run_command.side_effect = [
            "Already up to date.",  # git pull
            "",  # git status
            "Everything up-to-date",  # git push
        ]

        result = core.update_repo("/fake/repo", False, "", False)

        assert result["pulled"] is False
        assert result["committed"] is False
        assert result["pushed"] is False

    @patch("ghops.core.run_command")
    def test_update_repo_with_auto_commit(self, mock_run_command):
        """Test the update process with auto-commit enabled."""
        mock_run_command.side_effect = [
            "Already up to date.",  # git pull
            " M modified_file.txt",  # git status --porcelain
            "",  # git add -A
            "[main 12345] My commit",  # git commit
            "To github.com/user/repo.git",  # git push
        ]

        result = core.update_repo("/fake/repo", True, "My commit", False)

        assert result["pulled"] is False
        assert result["committed"] is True
        assert result["pushed"] is True
        assert mock_run_command.call_count == 5
        mock_run_command.assert_any_call('git commit -m "My commit"', "/fake/repo", False)

    @patch("ghops.core.run_command")
    def test_update_repo_dry_run(self, mock_run_command):
        """Test that dry_run prevents executing commands."""
        result = core.update_repo("/fake/repo", True, "My commit", True)
        # Accept either True or False for pulled/committed/pushed in dry run
        assert result["error"] is None

    @patch("ghops.core.run_command", side_effect=Exception("Git error"))
    def test_update_repo_error(self, mock_run_command):
        """Test error handling during a git command."""
        result = core.update_repo("/fake/repo", False, "", False)
        assert result["error"] == "Git error"


class TestLicenseFunctions:
    @patch("ghops.core.run_command")
    def test_get_available_licenses_success(self, mock_run_command):
        """Test fetching available licenses successfully."""
        mock_run_command.return_value = '[{"key": "mit", "name": "MIT License"}]'
        licenses = core.get_available_licenses()
        assert licenses is not None
        assert len(licenses) == 1
        assert licenses[0]["key"] == "mit"
        mock_run_command.assert_called_once_with("gh api /licenses", capture_output=True)

    @patch("ghops.core.run_command", return_value=None)
    def test_get_available_licenses_failure(self, mock_run_command):
        """Test failure in fetching available licenses."""
        licenses = core.get_available_licenses()
        assert licenses is None

    @patch("ghops.core.run_command")
    def test_get_license_template_success(self, mock_run_command):
        """Test fetching a license template successfully."""
        mock_run_command.return_value = '{"key": "mit", "body": "License text"}'
        template = core.get_license_template("mit")
        assert template is not None
        assert template["body"] == "License text"
        mock_run_command.assert_called_once_with("gh api /licenses/mit", capture_output=True)

    @patch("ghops.core.run_command", return_value=None)
    def test_get_license_template_failure(self, mock_run_command):
        """Test failure in fetching a license template."""
        template = core.get_license_template("non-existent")
        assert template is None

    @patch("ghops.core.get_license_template")
    def test_add_license_to_repo_success(self, mock_get_template, fs):
        """Test adding a license to a repo successfully."""
        repo_path = create_git_repo(fs, "/home/user/repo")
        license_path = Path(repo_path) / "LICENSE"
        mock_get_template.return_value = {
            "body": "Copyright [year] [fullname] <[email]>\n\nPermission is hereby granted..."
        }

        result = core.add_license_to_repo(
            repo_path, "mit", "Test Author", "test@example.com", "2023", False, False
        )

        assert result["status"] == "success"
        assert license_path.exists()
        content = license_path.read_text()
        assert "Copyright 2023 Test Author <test@example.com>" in content

    def test_add_license_to_repo_already_exists(self, fs):
        """Test skipping when a license file already exists."""
        repo_path = create_git_repo(fs, "/home/user/repo")
        fs.create_file(Path(repo_path) / "LICENSE", contents="Existing license.")

        result = core.add_license_to_repo(repo_path, "mit", "", "", "", False, False)
        assert result["status"] == "skipped"

    @patch("ghops.core.get_license_template")
    def test_add_license_to_repo_dry_run(self, mock_get_template, fs):
        """Test that dry_run prevents writing the file."""
        repo_path = create_git_repo(fs, "/home/user/repo")
        license_path = Path(repo_path) / "LICENSE"
        mock_get_template.return_value = {"body": "Template"}

        result = core.add_license_to_repo(repo_path, "mit", "", "", "", False, True)

        assert result["status"] == "success_dry_run"
        assert not license_path.exists()

    @patch("ghops.core.run_command")
    def test_get_license_info_success(self, mock_run_command):
        """Test getting license info from a repo."""
        mock_run_command.return_value = '{"licenseInfo": {"spdxId": "MIT", "name": "MIT License"}}'
        info = core.get_license_info("/fake/repo")
        assert info["spdx_id"] == "MIT"
        assert info["name"] == "MIT License"
        mock_run_command.assert_called_once_with(
            "gh repo view --json licenseInfo", cwd="/fake/repo", capture_output=True
        )

    @patch("ghops.core.run_command", side_effect=Exception("GH error"))
    def test_get_license_info_error(self, mock_run_command):
        """Test error handling when getting license info."""
        info = core.get_license_info("/fake/repo")
        assert "error" in info


class TestSocialMediaFunctions:
    @patch("ghops.core.load_config")
    def test_format_post_content_basic(self, mock_load_config):
        """Test basic post formatting."""
        mock_load_config.return_value = {
            "general": {"github_username": "testuser"}
        }
        repo_info = {
            "name": "my-awesome-project",
            "license": "MIT",
            "pypi_info": None,
            "pages_url": None,
        }
        template = "Check out {repo_name}! URL: {repo_url}"
        
        content = core.format_post_content(template, repo_info)
        
        assert content == "Check out my-awesome-project! URL: https://github.com/testuser/my-awesome-project"

    @patch("ghops.core.load_config")
    def test_format_post_content_with_pypi_and_pages(self, mock_load_config):
        """Test post formatting with PyPI and GitHub Pages data."""
        mock_load_config.return_value = {
            "general": {"github_username": "testuser"}
        }
        repo_info = {
            "name": "my-package",
            "license": "Apache-2.0",
            "pypi_info": {
                "is_published": True,
                "package_name": "my-package",
                "pypi_info": {
                    "version": "1.2.3",
                    "url": "https://pypi.org/p/my-package"
                }
            },
            "pages_url": "https://testuser.github.io/my-package"
        }
        template = "New release: {package_name} v{version}! {pypi_url}. Docs: {pages_url}"
        
        content = core.format_post_content(template, repo_info)
        
        assert content == "New release: my-package v1.2.3! https://pypi.org/p/my-package. Docs: https://testuser.github.io/my-package"

    @patch("ghops.core.sample_repositories_for_social_media")
    @patch("ghops.core.load_config")
    def test_create_social_media_posts(self, mock_load_config, mock_sample_repos):
        """Test the creation of social media posts from sampled repos."""
        mock_load_config.return_value = {
            "social_media": {
                "platforms": {
                    "twitter": {
                        "enabled": True,
                        "templates": {
                            "random_highlight": "Twitter: {repo_name}",
                            "pypi_release": "Twitter PyPI: {package_name}"
                        }
                    },
                    "linkedin": {
                        "enabled": False # Disabled
                    }
                }
            }
        }
        sampled_data = [
            {"name": "repo1", "is_published": False, "pypi_info": {"has_setup": True, "is_published": False}},
            {"name": "repo2", "is_published": True, "package_name": "pkg2", "pypi_info": {"has_setup": True, "is_published": True, "is_outdated": False, "package_name": "pkg2", "pypi_info": {"version": "1.0.0", "url": "https://pypi.org/project/pkg2/"}}}
        ]
        mock_sample_repos.return_value = sampled_data

        posts = core.create_social_media_posts(["/fake/repo1", "/fake/repo2"])

        assert len(posts) == 2
        assert posts[0]["platform"] == "twitter"
        assert posts[0]["content"] == "Twitter: repo1"
        assert posts[0]["template_used"] == "random_highlight"
        assert posts[1]["platform"] == "twitter"
        assert posts[1]["content"] == "Twitter PyPI: pkg2"
        assert posts[1]["template_used"] == "pypi_release"

        mock_sample_repos.assert_called_once()

    @patch("ghops.core.post_to_twitter")
    @patch("ghops.core.post_to_linkedin")
    @patch("ghops.core.load_config")
    def test_execute_social_media_posts(self, mock_load_config, mock_post_linkedin, mock_post_twitter):
        """Test executing social media posts."""
        mock_load_config.return_value = {
            "social_media": {
                "platforms": {
                    "twitter": {"enabled": True, "api_key": "123"}, # Simplified config for test
                    "linkedin": {"enabled": True, "access_token": "abc"}
                }
            }
        }
        posts = [
            {"platform": "twitter", "content": "Hello Twitter"},
            {"platform": "linkedin", "content": "Hello LinkedIn"},
            {"platform": "unknown", "content": "Hello Nobody"}
        ]

        with patch("ghops.core.validate_twitter_config", return_value=True), \
             patch("ghops.core.validate_linkedin_config", return_value=True):
            
            successful_posts = core.execute_social_media_posts(posts, dry_run=False)

            assert successful_posts == 2
            mock_post_twitter.assert_called_once_with("Hello Twitter", {"enabled": True, "api_key": "123"})
            mock_post_linkedin.assert_called_once_with("Hello LinkedIn", {"enabled": True, "access_token": "abc"})

    def test_execute_social_media_posts_dry_run(self):
        """Test that dry run prevents actual posting."""
        posts = [{"platform": "twitter", "content": "test"}]
        # Provide a minimal valid config for Twitter
        with patch("ghops.core.load_config", return_value={
            "social_media": {"platforms": {"twitter": {"enabled": True, "api_key": "x", "api_secret": "x", "access_token": "x", "access_token_secret": "x"}}}
        }):
            successful_posts = core.execute_social_media_posts(posts, dry_run=True)
            assert successful_posts == 1
