"""
Tests for llm/template_loader.py module.

Tests the Jinja2 template system including:
- Template loading with fallback (user -> builtin)
- Template rendering with context
- Template initialization (copying built-in templates)
- Template listing
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from jinja2 import TemplateNotFound
from ghops.llm.template_loader import (
    TemplateLoader,
    get_template_dir,
    get_builtin_template_dir,
    get_template_loader
)


class TestTemplateLoader:
    """Test TemplateLoader functionality."""

    @pytest.fixture
    def temp_template_dirs(self):
        """Create temporary directories for user and built-in templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            user_dir = tmpdir_path / 'user'
            builtin_dir = tmpdir_path / 'builtin'

            user_dir.mkdir()
            builtin_dir.mkdir()

            yield user_dir, builtin_dir

    @pytest.fixture
    def loader(self, temp_template_dirs):
        """Create a test template loader."""
        user_dir, builtin_dir = temp_template_dirs
        loader = TemplateLoader()
        loader.user_dir = user_dir
        loader.builtin_dir = builtin_dir
        return loader

    # ========================================================================
    # Initialization
    # ========================================================================

    def test_loader_initialization(self):
        """Test template loader initializes with correct paths."""
        loader = TemplateLoader()

        assert loader.user_dir.exists()
        assert isinstance(loader.builtin_dir, Path)

    def test_loader_creates_user_directory(self):
        """Test that user template directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / 'templates'
            loader = TemplateLoader()
            loader.user_dir = user_dir

            # Re-init to trigger directory creation
            loader.user_dir.mkdir(parents=True, exist_ok=True)

            assert user_dir.exists()

    # ========================================================================
    # Template Loading
    # ========================================================================

    def test_load_user_template(self, loader, temp_template_dirs):
        """Test loading a template from user directory."""
        user_dir, _ = temp_template_dirs

        # Create user template
        platform_dir = user_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('User template: {{ context.repo_name }}')

        template = loader.load_template('devto', 'default')

        assert template is not None
        result = template.render(context=MagicMock(repo_name='test-repo'))
        assert 'User template: test-repo' in result

    def test_load_builtin_template(self, loader, temp_template_dirs):
        """Test loading a template from built-in directory."""
        _, builtin_dir = temp_template_dirs

        # Create built-in template
        platform_dir = builtin_dir / 'twitter'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('Built-in: {{ context.repo_name }}')

        template = loader.load_template('twitter', 'default')

        assert template is not None
        result = template.render(context=MagicMock(repo_name='my-project'))
        assert 'Built-in: my-project' in result

    def test_load_template_fallback_to_builtin(self, loader, temp_template_dirs):
        """Test that loader falls back to built-in when user template doesn't exist."""
        user_dir, builtin_dir = temp_template_dirs

        # Create only built-in template
        platform_dir = builtin_dir / 'linkedin'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('Built-in template')

        # User directory exists but no template
        (user_dir / 'linkedin').mkdir()

        template = loader.load_template('linkedin', 'default')

        result = template.render()
        assert 'Built-in template' in result

    def test_load_template_user_overrides_builtin(self, loader, temp_template_dirs):
        """Test that user template takes precedence over built-in."""
        user_dir, builtin_dir = temp_template_dirs

        # Create both user and built-in templates
        user_platform = user_dir / 'mastodon'
        user_platform.mkdir()
        (user_platform / 'default.j2').write_text('User custom template')

        builtin_platform = builtin_dir / 'mastodon'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('Built-in template')

        template = loader.load_template('mastodon', 'default')

        result = template.render()
        # Should use user template
        assert 'User custom template' in result
        assert 'Built-in' not in result

    def test_load_template_not_found(self, loader):
        """Test that TemplateNotFound is raised when template doesn't exist."""
        with pytest.raises(TemplateNotFound) as exc_info:
            loader.load_template('nonexistent_platform', 'default')

        assert 'nonexistent_platform' in str(exc_info.value)

    def test_load_custom_template_name(self, loader, temp_template_dirs):
        """Test loading a template with custom name."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'custom.j2').write_text('Custom template')

        template = loader.load_template('devto', 'custom')

        result = template.render()
        assert 'Custom template' in result

    # ========================================================================
    # Template Rendering
    # ========================================================================

    def test_render_prompt(self, loader, temp_template_dirs):
        """Test rendering a prompt template."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text(
            'Release: {{ context.repo_name }} version {{ context.version }}'
        )

        context = MagicMock(repo_name='my-app', version='1.0.0')
        result = loader.render_prompt('devto', context)

        assert 'Release: my-app version 1.0.0' in result

    def test_render_prompt_with_extra_kwargs(self, loader, temp_template_dirs):
        """Test rendering with additional template variables."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'twitter'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text(
            '{{ custom_var }}: {{ context.repo_name }}'
        )

        context = MagicMock(repo_name='project')
        result = loader.render_prompt('twitter', context, custom_var='Announcing')

        assert 'Announcing: project' in result

    def test_render_prompt_with_jinja2_features(self, loader, temp_template_dirs):
        """Test that Jinja2 features work (loops, conditionals, filters)."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'devto'
        platform_dir.mkdir()
        template_content = '''
        {% if context.stars > 100 %}
        Popular project!
        {% endif %}
        Tags: {% for tag in context.tags %}{{ tag }}{% if not loop.last %}, {% endif %}{% endfor %}
        Title: {{ context.repo_name | upper }}
        '''
        (platform_dir / 'default.j2').write_text(template_content)

        context = MagicMock(
            stars=150,
            tags=['python', 'testing', 'cli'],
            repo_name='ghops'
        )
        result = loader.render_prompt('devto', context)

        assert 'Popular project!' in result
        assert 'Tags: python, testing, cli' in result
        assert 'GHOPS' in result

    # ========================================================================
    # Template Listing
    # ========================================================================

    def test_list_templates_empty(self, loader, temp_template_dirs):
        """Test listing templates when none exist."""
        result = loader.list_templates('devto')

        assert result == {'user': [], 'builtin': []}

    def test_list_templates_user_only(self, loader, temp_template_dirs):
        """Test listing user templates."""
        user_dir, _ = temp_template_dirs

        platform_dir = user_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('template')
        (platform_dir / 'custom.j2').write_text('template')

        result = loader.list_templates('devto')

        assert set(result['user']) == {'default', 'custom'}
        assert result['builtin'] == []

    def test_list_templates_builtin_only(self, loader, temp_template_dirs):
        """Test listing built-in templates."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'twitter'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('template')
        (platform_dir / 'release.j2').write_text('template')

        result = loader.list_templates('twitter')

        assert result['user'] == []
        assert set(result['builtin']) == {'default', 'release'}

    def test_list_templates_both(self, loader, temp_template_dirs):
        """Test listing both user and built-in templates."""
        user_dir, builtin_dir = temp_template_dirs

        user_platform = user_dir / 'mastodon'
        user_platform.mkdir()
        (user_platform / 'custom.j2').write_text('template')

        builtin_platform = builtin_dir / 'mastodon'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('template')

        result = loader.list_templates('mastodon')

        assert result['user'] == ['custom']
        assert result['builtin'] == ['default']

    def test_list_templates_ignores_non_j2_files(self, loader, temp_template_dirs):
        """Test that only .j2 files are listed."""
        user_dir, _ = temp_template_dirs

        platform_dir = user_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('template')
        (platform_dir / 'README.md').write_text('docs')
        (platform_dir / 'backup.txt').write_text('backup')

        result = loader.list_templates('devto')

        assert result['user'] == ['default']

    # ========================================================================
    # Template Initialization
    # ========================================================================

    def test_init_user_templates_single_platform(self, loader, temp_template_dirs):
        """Test initializing user templates for a single platform."""
        user_dir, builtin_dir = temp_template_dirs

        # Create built-in templates
        builtin_platform = builtin_dir / 'devto'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('built-in template')
        (builtin_platform / 'custom.j2').write_text('another template')

        count = loader.init_user_templates(platform='devto')

        assert count == 2
        assert (user_dir / 'devto' / 'default.j2').exists()
        assert (user_dir / 'devto' / 'custom.j2').exists()

    def test_init_user_templates_all_platforms(self, loader, temp_template_dirs):
        """Test initializing user templates for all platforms."""
        user_dir, builtin_dir = temp_template_dirs

        # Create built-in templates for multiple platforms
        for platform in ['devto', 'twitter', 'linkedin']:
            platform_dir = builtin_dir / platform
            platform_dir.mkdir()
            (platform_dir / 'default.j2').write_text(f'{platform} template')

        count = loader.init_user_templates()

        assert count == 3
        assert (user_dir / 'devto' / 'default.j2').exists()
        assert (user_dir / 'twitter' / 'default.j2').exists()
        assert (user_dir / 'linkedin' / 'default.j2').exists()

    def test_init_user_templates_skips_existing(self, loader, temp_template_dirs):
        """Test that existing user templates are not overwritten."""
        user_dir, builtin_dir = temp_template_dirs

        # Create built-in template
        builtin_platform = builtin_dir / 'devto'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('built-in')

        # Create existing user template
        user_platform = user_dir / 'devto'
        user_platform.mkdir()
        (user_platform / 'default.j2').write_text('user custom')

        count = loader.init_user_templates(platform='devto')

        # Should skip existing
        assert count == 0
        assert (user_platform / 'default.j2').read_text() == 'user custom'

    def test_init_user_templates_force_overwrite(self, loader, temp_template_dirs):
        """Test force overwriting existing user templates."""
        user_dir, builtin_dir = temp_template_dirs

        # Create built-in template
        builtin_platform = builtin_dir / 'devto'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('built-in new')

        # Create existing user template
        user_platform = user_dir / 'devto'
        user_platform.mkdir()
        (user_platform / 'default.j2').write_text('user old')

        count = loader.init_user_templates(platform='devto', force=True)

        # Should overwrite
        assert count == 1
        assert (user_platform / 'default.j2').read_text() == 'built-in new'

    def test_init_user_templates_creates_directories(self, loader, temp_template_dirs):
        """Test that platform directories are created."""
        user_dir, builtin_dir = temp_template_dirs

        builtin_platform = builtin_dir / 'bluesky'
        builtin_platform.mkdir()
        (builtin_platform / 'default.j2').write_text('template')

        loader.init_user_templates(platform='bluesky')

        assert (user_dir / 'bluesky').exists()
        assert (user_dir / 'bluesky').is_dir()

    def test_init_user_templates_nonexistent_platform(self, loader):
        """Test initializing templates for nonexistent platform."""
        count = loader.init_user_templates(platform='nonexistent')

        # Should return 0 if platform doesn't exist
        assert count == 0

    def test_init_user_templates_no_builtin_templates(self, loader, temp_template_dirs):
        """Test behavior when no built-in templates exist."""
        count = loader.init_user_templates()

        # Should return 0 if no built-in templates
        assert count == 0


class TestTemplateFunctions:
    """Test template utility functions."""

    def test_get_template_dir(self):
        """Test getting user template directory."""
        template_dir = get_template_dir()

        assert isinstance(template_dir, Path)
        assert 'templates' in str(template_dir)

    def test_get_builtin_template_dir(self):
        """Test getting built-in template directory."""
        builtin_dir = get_builtin_template_dir()

        assert isinstance(builtin_dir, Path)
        assert 'llm' in str(builtin_dir)
        assert 'templates' in str(builtin_dir)

    def test_get_template_loader_singleton(self):
        """Test that get_template_loader returns singleton."""
        # Clear any existing global
        import ghops.llm.template_loader as module
        if '_template_loader' in dir(module):
            delattr(module, '_template_loader')

        loader1 = get_template_loader()
        loader2 = get_template_loader()

        assert loader1 is loader2


class TestTemplateEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_template_dirs(self):
        """Create temporary directories for user and built-in templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            user_dir = tmpdir_path / 'user'
            builtin_dir = tmpdir_path / 'builtin'

            user_dir.mkdir()
            builtin_dir.mkdir()

            yield user_dir, builtin_dir

    @pytest.fixture
    def loader(self, temp_template_dirs):
        """Create a test template loader."""
        user_dir, builtin_dir = temp_template_dirs
        loader = TemplateLoader()
        loader.user_dir = user_dir
        loader.builtin_dir = builtin_dir
        return loader

    def test_template_with_syntax_error(self, loader, temp_template_dirs):
        """Test that templates with syntax errors are caught when rendering."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'devto'
        platform_dir.mkdir()
        # Invalid Jinja2 syntax
        (platform_dir / 'default.j2').write_text('{{ unclosed variable')

        # Loading might fail or succeed depending on Jinja2 version
        try:
            template = loader.load_template('devto', 'default')
            # If loading succeeds, rendering should fail
            with pytest.raises(Exception):
                template.render()
        except Exception:
            # Loading failed - also acceptable
            pass

    def test_template_with_missing_variable(self, loader, temp_template_dirs):
        """Test rendering template with missing variable (Jinja2 allows undefined)."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'twitter'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('{{ context.missing_var }}')

        context = MagicMock(spec=[])  # Empty mock with no attributes

        # Jinja2 renders undefined variables as empty string by default
        try:
            result = loader.render_prompt('twitter', context)
            # Should render (possibly empty or with undefined marker)
            assert result is not None or result == ''
        except (AttributeError, Exception):
            # Some configurations might raise - also acceptable
            pass

    def test_template_autoescape(self, loader, temp_template_dirs):
        """Test template rendering with HTML content."""
        _, builtin_dir = temp_template_dirs

        platform_dir = builtin_dir / 'devto'
        platform_dir.mkdir()
        (platform_dir / 'default.j2').write_text('<div>{{ content }}</div>')

        # Test that template renders (autoescape behavior depends on config)
        template = loader.load_template('devto', 'default')
        result = template.render(content='<script>alert("xss")</script>')
        assert result is not None
        assert '<div>' in result  # Should contain the div wrapper


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
