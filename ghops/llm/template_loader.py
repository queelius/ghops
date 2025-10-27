"""
Jinja2 template loader for customizable prompt generation.

Allows users to customize LLM prompts by editing templates in ~/.ghops/templates/
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape, Template, TemplateNotFound
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_template_dir() -> Path:
    """Get user's template directory."""
    from ..config import get_config_path
    config_dir = get_config_path().parent
    return config_dir / 'templates'


def get_builtin_template_dir() -> Path:
    """Get built-in template directory."""
    return Path(__file__).parent / 'templates'


class TemplateLoader:
    """
    Load and render Jinja2 templates for prompt generation.

    Templates can be customized by users in ~/.ghops/templates/{platform}/
    Falls back to built-in templates if user templates don't exist.
    """

    def __init__(self):
        """Initialize template loader."""
        self.user_dir = get_template_dir()
        self.builtin_dir = get_builtin_template_dir()

        # Ensure user template directory exists
        self.user_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Template loader initialized:")
        logger.debug(f"  User templates: {self.user_dir}")
        logger.debug(f"  Built-in templates: {self.builtin_dir}")

    def _get_environment(self, platform: str, use_builtin: bool = False) -> Environment:
        """
        Get Jinja2 environment for a platform.

        Args:
            platform: Platform name (devto, twitter, etc.)
            use_builtin: Force use of built-in templates

        Returns:
            Jinja2 Environment
        """
        if use_builtin:
            template_dir = self.builtin_dir / platform
        else:
            template_dir = self.user_dir / platform

        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        return env

    def load_template(self, platform: str, name: str = 'default') -> Template:
        """
        Load a template with fallback to built-in.

        Args:
            platform: Platform name (devto, twitter, mastodon, bluesky, linkedin)
            name: Template name (default: 'default')

        Returns:
            Jinja2 Template

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        template_filename = f'{name}.j2'

        # Try user templates first
        user_template_dir = self.user_dir / platform
        if user_template_dir.exists():
            try:
                env = self._get_environment(platform, use_builtin=False)
                template = env.get_template(template_filename)
                logger.info(f"Loaded user template: {platform}/{name}")
                return template
            except TemplateNotFound:
                logger.debug(f"User template not found: {platform}/{name}, trying built-in")

        # Fall back to built-in templates
        builtin_template_dir = self.builtin_dir / platform
        if builtin_template_dir.exists():
            try:
                env = self._get_environment(platform, use_builtin=True)
                template = env.get_template(template_filename)
                logger.info(f"Loaded built-in template: {platform}/{name}")
                return template
            except TemplateNotFound:
                pass

        raise TemplateNotFound(
            f"Template not found: {platform}/{name}.j2\n"
            f"Searched in:\n"
            f"  - {user_template_dir}\n"
            f"  - {builtin_template_dir}"
        )

    def render_prompt(self, platform: str, context: Any,
                     template_name: str = 'default',
                     **kwargs) -> str:
        """
        Render a prompt template.

        Args:
            platform: Platform name
            context: ContentContext object with repo information
            template_name: Template name (default: 'default')
            **kwargs: Additional variables to pass to template

        Returns:
            Rendered prompt string
        """
        template = self.load_template(platform, template_name)

        # Merge context and kwargs
        template_vars = {
            'context': context,
            **kwargs
        }

        return template.render(**template_vars)

    def list_templates(self, platform: str) -> Dict[str, list]:
        """
        List available templates for a platform.

        Args:
            platform: Platform name

        Returns:
            Dict with 'user' and 'builtin' template lists
        """
        result = {
            'user': [],
            'builtin': []
        }

        # List user templates
        user_dir = self.user_dir / platform
        if user_dir.exists():
            result['user'] = [
                f.stem for f in user_dir.glob('*.j2')
            ]

        # List built-in templates
        builtin_dir = self.builtin_dir / platform
        if builtin_dir.exists():
            result['builtin'] = [
                f.stem for f in builtin_dir.glob('*.j2')
            ]

        return result

    def init_user_templates(self, platform: Optional[str] = None,
                           force: bool = False) -> int:
        """
        Initialize user templates by copying built-in templates.

        Args:
            platform: Platform to initialize (None = all platforms)
            force: Overwrite existing templates

        Returns:
            Number of templates initialized
        """
        import shutil

        if platform:
            platforms = [platform]
        else:
            # Get all platform directories in built-in templates
            if self.builtin_dir.exists():
                platforms = [
                    d.name for d in self.builtin_dir.iterdir()
                    if d.is_dir()
                ]
            else:
                platforms = []

        initialized = 0

        for plat in platforms:
            builtin_dir = self.builtin_dir / plat
            user_dir = self.user_dir / plat

            if not builtin_dir.exists():
                continue

            # Create user directory
            user_dir.mkdir(parents=True, exist_ok=True)

            # Copy templates
            for template_file in builtin_dir.glob('*.j2'):
                user_file = user_dir / template_file.name

                if user_file.exists() and not force:
                    logger.debug(f"Skipping existing template: {user_file}")
                    continue

                shutil.copy2(template_file, user_file)
                logger.info(f"Initialized template: {user_file}")
                initialized += 1

        return initialized


def get_template_loader() -> TemplateLoader:
    """Get singleton template loader instance."""
    global _template_loader
    if '_template_loader' not in globals():
        _template_loader = TemplateLoader()
    return _template_loader
