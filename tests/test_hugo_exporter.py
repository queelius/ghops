"""Tests for hugo_exporter.py module."""

import pytest
import tempfile
from pathlib import Path
import json
from ghops.hugo_exporter import (
    export_hugo_with_templates,
    create_hugo_site_structure,
    slugify,
    create_hugo_config_template
)


class TestHugoExporter:
    """Test Hugo export functionality."""
    
    @pytest.fixture
    def sample_repos(self):
        """Sample repository data for testing."""
        return {
            "Python Projects": [
                {
                    "name": "awesome-python-project",
                    "description": "An awesome Python project for testing",
                    "language": "Python",
                    "languages": {
                        "Python": {"files": 20, "bytes": 50000},
                        "JavaScript": {"files": 2, "bytes": 5000}
                    },
                    "stars": 100,
                    "owner": "testuser",
                    "topics": ["python", "testing", "awesome"],
                    "tags": ["lang:python", "type:library"],
                    "license": {"key": "mit", "name": "MIT License"},
                    "url": "https://github.com/testuser/awesome-python-project",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "private": False,
                    "archived": False
                }
            ],
            "JavaScript Tools": [
                {
                    "name": "cool-js-tool",
                    "description": "A cool JavaScript tool",
                    "language": "JavaScript",
                    "stars": 50,
                    "owner": "testuser",
                    "topics": ["javascript", "tool"],
                    "url": "https://github.com/testuser/cool-js-tool"
                }
            ]
        }
    
    def test_create_hugo_site_structure(self):
        """Test creating Hugo directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            create_hugo_site_structure(base_path)
            
            # Check directories exist
            assert (base_path / "content" / "repositories").exists()
            assert (base_path / "data").exists()
            assert (base_path / "layouts" / "repositories").exists()
            assert (base_path / "static" / "images").exists()
    
    def test_slugify(self):
        """Test slug generation."""
        assert slugify("Hello World") == "hello-world"
        assert slugify("Python/Django") == "python-django"
        assert slugify("Test 123") == "test-123"
        assert slugify("UPPERCASE") == "uppercase"
    
    def test_export_hugo_basic(self, sample_repos):
        """Test basic Hugo export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = list(export_hugo_with_templates(sample_repos, tmpdir))
            
            # Check results
            assert len(results) > 0
            
            # Check for success statuses
            success_results = [r for r in results if r["status"] == "success"]
            assert len(success_results) > 0
            
            # Check file types created
            file_types = {r.get("type") for r in success_results}
            assert "index" in file_types
            assert "group" in file_types
            assert "repository" in file_types
            
            # Check files exist
            content_path = Path(tmpdir) / "content" / "repositories"
            assert (content_path / "_index.md").exists()
            assert (content_path / "python-projects" / "_index.md").exists()
            assert (content_path / "python-projects" / "awesome-python-project.md").exists()
    
    def test_export_hugo_with_data_files(self, sample_repos):
        """Test Hugo export with data file generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = list(export_hugo_with_templates(
                sample_repos, 
                tmpdir,
                create_data_files=True
            ))
            
            # Check data files created
            data_results = [r for r in results if r.get("type") == "data"]
            assert len(data_results) == 2  # repositories.json and repository_groups.json
            
            # Check data files exist and are valid JSON
            data_path = Path(tmpdir) / "data"
            
            repos_file = data_path / "repositories.json"
            assert repos_file.exists()
            repos_data = json.loads(repos_file.read_text())
            assert len(repos_data) == 2  # Total repos across all groups
            
            groups_file = data_path / "repository_groups.json"
            assert groups_file.exists()
            groups_data = json.loads(groups_file.read_text())
            assert "Python Projects" in groups_data
            assert groups_data["Python Projects"]["count"] == 1
    
    def test_hugo_index_content(self, sample_repos):
        """Test the generated Hugo index content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            list(export_hugo_with_templates(sample_repos, tmpdir))
            
            # Read generated index
            index_file = Path(tmpdir) / "content" / "repositories" / "_index.md"
            content = index_file.read_text()
            
            # Check front matter
            assert "---" in content
            assert "title:" in content
            assert "Repository Catalog" in content
            
            # Check content
            assert "Python Projects" in content
            assert "JavaScript Tools" in content
            assert "**2** repositories" in content  # Total count in bold
    
    def test_hugo_repo_page_content(self, sample_repos):
        """Test the generated repository page content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            list(export_hugo_with_templates(sample_repos, tmpdir))
            
            # Read generated repo page
            repo_file = Path(tmpdir) / "content" / "repositories" / "python-projects" / "awesome-python-project.md"
            content = repo_file.read_text()
            
            # Check front matter
            assert "---" in content
            assert 'title: "awesome-python-project"' in content
            assert 'description: "An awesome Python project for testing"' in content
            assert "tags:" in content
            assert '- "lang:python"' in content
            assert 'stars: 100' in content
            
            # Check content sections
            assert "## Overview" in content
            assert "Python" in content
            assert "100" in content  # stars
            assert "MIT License" in content
            
            # Check language breakdown
            assert "## Languages" in content
            assert "Python" in content
            assert "20" in content  # file count
    
    def test_custom_template_name(self, sample_repos):
        """Test using custom template name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # This should try to load a custom template
            # Since it doesn't exist, it should fall back to built-in
            results = list(export_hugo_with_templates(
                sample_repos,
                tmpdir,
                template_name="my_custom_template"
            ))
            
            # Should still work with fallback
            success_results = [r for r in results if r["status"] == "success"]
            assert len(success_results) > 0
    
    def test_create_hugo_config_template(self):
        """Test creating Hugo config template."""
        config_template = create_hugo_config_template()
        
        assert "baseURL" in config_template
        assert "{{ base_url" in config_template
        assert "[menu]" in config_template
        assert "[taxonomies]" in config_template
        assert "language = \"languages\"" in config_template


if __name__ == "__main__":
    pytest.main([__file__, "-v"])