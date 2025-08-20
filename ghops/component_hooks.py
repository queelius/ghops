"""
Component render hooks for user customization.

This module provides a simple way for users to customize component rendering
without modifying the core codebase. Users can create Python functions that
override the default rendering of any component.

User customizations are loaded from:
- ~/.ghops/export_components/renders.py
"""

import importlib.util
from pathlib import Path
from typing import Dict, Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)


def get_user_components_path() -> Path:
    """Get the path to user component customizations.
    
    Returns ~/.ghops/export_components/ to keep all ghops data together.
    """
    return Path.home() / '.ghops' / 'export_components'


def load_user_renderers() -> Dict[str, Callable]:
    """Load user-defined component renderers.
    
    Returns:
        Dictionary mapping component names to render functions
    """
    renderers = {}
    components_dir = get_user_components_path()
    renders_file = components_dir / 'renders.py'
    
    if not renders_file.exists():
        return renderers
    
    try:
        # Load the renders module
        spec = importlib.util.spec_from_file_location('user_renders', renders_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the RENDERERS dict if it exists
            if hasattr(module, 'RENDERERS'):
                renderers = module.RENDERERS
                logger.debug(f"Loaded {len(renderers)} custom renderers from {renders_file}")
            
            # Also check for individual render_<component> functions
            for attr_name in dir(module):
                if attr_name.startswith('render_'):
                    component_name = attr_name[7:]  # Remove 'render_' prefix
                    if component_name not in renderers:
                        renderers[component_name] = getattr(module, attr_name)
                        logger.debug(f"Found renderer function for {component_name}")
    
    except Exception as e:
        logger.warning(f"Failed to load user renderers from {renders_file}: {e}")
    
    return renderers


# Cache for loaded renderers
_renderer_cache: Optional[Dict[str, Callable]] = None


def get_user_renderer(component_name: str) -> Optional[Callable]:
    """Get a user-defined renderer for a specific component.
    
    Args:
        component_name: Name of the component (e.g., 'summary_stats')
    
    Returns:
        Render function if found, None otherwise
    """
    global _renderer_cache
    
    if _renderer_cache is None:
        _renderer_cache = load_user_renderers()
    
    return _renderer_cache.get(component_name)


def clear_renderer_cache():
    """Clear the renderer cache (useful for testing or reload)."""
    global _renderer_cache
    _renderer_cache = None


def create_component_template(component_name: str) -> str:
    """Generate a template for customizing a component.
    
    Args:
        component_name: Name of the component to customize
    
    Returns:
        Python code template as a string
    """
    template = f'''"""
Custom renderer for {component_name} component.

This file is loaded by ghops to customize the {component_name} component's output.
Modify the render function below to change how the component displays.
"""

def render_{component_name}(data):
    """
    Custom render function for {component_name}.
    
    Args:
        data: Dictionary containing the component's data.
              The exact keys depend on the component.
    
    Returns:
        String with the rendered output (Markdown, HTML, etc.)
    """
    # Example: Default rendering
    # Modify this to customize the output
    
    # For debugging - uncomment to see available data:
    # import json
    # print("Available data keys:", json.dumps(list(data.keys()), indent=2))
    
    return f"""## {component_name.replace('_', ' ').title()}
    
    {{data}}
    """

# Alternative: Export via RENDERERS dictionary
# RENDERERS = {{
#     '{component_name}': render_{component_name}
# }}
'''
    return template


def init_user_components():
    """Initialize user components directory with examples."""
    components_dir = get_user_components_path()
    components_dir.mkdir(parents=True, exist_ok=True)
    
    # Create an example renders.py if it doesn't exist
    renders_file = components_dir / 'renders.py'
    if not renders_file.exists():
        example_content = '''"""
User-defined component renderers.

Define custom rendering functions for export components here.
Each function receives a data dictionary and returns a formatted string.

Example functions are provided below - uncomment and modify as needed.
"""

# Example: Custom summary statistics renderer
def render_summary_stats(data):
    """Custom renderer for summary statistics."""
    return f"""
### 📊 Quick Stats
- **Projects:** {data.get('total_repos', 0)}
- **Stars:** ⭐ {data.get('total_stars', 0)}
- **Most used:** {', '.join(lang for lang, _ in data.get('top_languages', [])[:3])}
"""

# Example: Simplified repository cards
def render_repository_cards(data):
    """Custom renderer for repository cards."""
    lines = ["## Repositories\\n"]
    for repo in data.get('repositories', []):
        name = repo.get('name', 'Unknown')
        desc = repo.get('description', 'No description')
        stars = repo.get('stargazers_count', 0)
        lines.append(f"**{name}** {'⭐' * min(stars, 5)}")
        lines.append(f"  {desc}\\n")
    return '\\n'.join(lines)

# Export all renderers
RENDERERS = {
    # Uncomment to activate:
    # 'summary_stats': render_summary_stats,
    # 'repository_cards': render_repository_cards,
}
'''
        renders_file.write_text(example_content)
        logger.info(f"Created example renders file at {renders_file}")
        return True
    return False