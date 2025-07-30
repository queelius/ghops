"""Tests for templates.py module."""

import pytest
import tempfile
from pathlib import Path
from ghops.templates import (
    render_template,
    load_template,
    save_template,
    list_templates,
    get_builtin_templates
)


class TestTemplateEngine:
    """Test the template engine functionality."""
    
    def test_builtin_templates_exist(self):
        """Test that built-in templates are available."""
        templates = get_builtin_templates()
        
        # Should have at least these formats
        assert "markdown" in templates
        assert "html" in templates
        assert "latex" in templates
        assert "csv" in templates
        assert "json" in templates
        
        # Each template should be a non-empty string
        for name, content in templates.items():
            assert isinstance(content, str)
            assert len(content) > 0
    
    def test_render_simple_template(self):
        """Test rendering a simple template."""
        template = "Hello {{ name }}!"
        data = {"name": "World"}
        
        result = render_template(template, data)
        assert result == "Hello World!"
    
    def test_render_template_with_loops(self):
        """Test rendering template with loops."""
        template = """{% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}"""
        data = {"items": ["a", "b", "c"]}
        
        result = render_template(template, data)
        assert result == "a, b, c"
    
    def test_render_template_with_conditionals(self):
        """Test rendering template with conditionals."""
        template = """{% if show %}{{ message }}{% else %}Hidden{% endif %}"""
        
        # Test with show=True
        result = render_template(template, {"show": True, "message": "Hello"})
        assert result == "Hello"
        
        # Test with show=False
        result = render_template(template, {"show": False, "message": "Hello"})
        assert result == "Hidden"
    
    def test_render_template_with_filters(self):
        """Test rendering template with filters."""
        template = """{{ name | upper }} - {{ items | join(", ") }}"""
        data = {"name": "test", "items": ["a", "b", "c"]}
        
        result = render_template(template, data)
        assert result == "TEST - a, b, c"
    
    def test_render_builtin_markdown_template(self):
        """Test rendering the built-in markdown template."""
        template = get_builtin_templates()["markdown"]
        data = {
            "groups": {
                "Python Projects": [
                    {
                        "name": "test-repo",
                        "description": "A test repository",
                        "language": "Python",
                        "stars": 42,
                        "owner": "testuser",
                        "topics": ["python", "testing"],
                        "license": {"name": "MIT License"},
                        "url": "https://github.com/testuser/test-repo"
                    }
                ]
            },
            "generated_date": "2024-01-01 12:00:00",
            "title": "My Repos"
        }
        
        result = render_template(template, data)
        
        # Check key content is present
        assert "My Repos" in result
        assert "Python Projects" in result
        assert "test-repo" in result
        assert "A test repository" in result
        assert "Python" in result
        assert "42" in result
        assert "MIT License" in result
    
    def test_save_and_load_template(self):
        """Test saving and loading a template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock the template directory
            import ghops.templates
            original_get_dir = ghops.templates.get_template_dir
            ghops.templates.get_template_dir = lambda: Path(tmpdir)
            
            try:
                # Save a template
                template_content = "Test template: {{ name }}"
                save_template("test_template", template_content)
                
                # Load it back
                loaded = load_template("test_template", "markdown")
                assert loaded == template_content
                
                # List templates should include it
                templates = list_templates()
                saved_templates = [t for t in templates if t["type"] == "saved"]
                assert any(t["name"] == "test_template" for t in saved_templates)
                
            finally:
                # Restore original function
                ghops.templates.get_template_dir = original_get_dir
    
    def test_load_nonexistent_template(self):
        """Test loading a template that doesn't exist."""
        result = load_template("nonexistent_template_xyz", "markdown")
        # Should fall back to built-in markdown template
        assert result == get_builtin_templates()["markdown"]
    
    def test_template_error_handling(self):
        """Test template rendering with invalid syntax."""
        # Invalid template syntax
        template = "{{ name"  # Missing closing }}
        data = {"name": "test"}
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            render_template(template, data)
        assert "Failed to render template" in str(exc_info.value)
    
    def test_list_templates(self):
        """Test listing all templates."""
        templates = list_templates()
        
        # Should have built-in templates
        builtin = [t for t in templates if t["type"] == "builtin"]
        assert len(builtin) >= 5  # markdown, html, latex, csv, json
        
        # Check structure
        for t in templates:
            assert "name" in t
            assert "type" in t
            assert "description" in t


if __name__ == "__main__":
    pytest.main([__file__, "-v"])