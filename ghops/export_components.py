"""
Component-based export system for ghops.

This module provides a flexible, extensible system for generating exports
in various formats. Components can be registered, configured, and composed
to create rich export outputs.

Design principles:
- Components are independent and reusable
- Configuration is explicit and validated
- Format-specific rendering is supported
- Performance is optimized through shared context
- Extension through plugins is supported
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Protocol, runtime_checkable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats."""
    MARKDOWN = "markdown"
    HTML = "html"
    HUGO = "hugo"
    LATEX = "latex"
    JSON = "json"
    CSV = "csv"


@dataclass
class ComponentConfig:
    """Configuration for a component."""
    enabled: bool = True
    priority: int = 100
    options: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration option with a default."""
        return self.options.get(key, default)


@dataclass
class ExportContext:
    """Shared context passed between components.
    
    This allows components to share computed data and avoid
    redundant calculations.
    """
    format: ExportFormat
    repositories: List[Dict[str, Any]]
    config: Dict[str, Any]
    shared_data: Dict[str, Any] = field(default_factory=dict)
    
    def get_or_compute(self, key: str, compute_func):
        """Get cached data or compute and cache it."""
        if key not in self.shared_data:
            self.shared_data[key] = compute_func()
        return self.shared_data[key]
    
    @property
    def total_repos(self) -> int:
        """Total number of repositories."""
        return len(self.repositories)
    
    @property
    def language_distribution(self) -> Dict[str, int]:
        """Get language distribution (cached)."""
        return self.get_or_compute('lang_dist', self._compute_language_dist)
    
    def _compute_language_dist(self) -> Dict[str, int]:
        """Compute language distribution."""
        lang_counts = {}
        for repo in self.repositories:
            lang = repo.get('language')
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        return lang_counts


@runtime_checkable
class ExportComponent(Protocol):
    """Protocol for export components.
    
    Using Protocol instead of ABC for more flexibility.
    Components can be any class that implements these methods.
    """
    
    @property
    def name(self) -> str:
        """Unique name for this component."""
        ...
    
    @property
    def description(self) -> str:
        """Human-readable description."""
        ...
    
    def should_render(self, context: ExportContext) -> bool:
        """Determine if this component should be rendered."""
        ...
    
    def render(self, context: ExportContext) -> str:
        """Render the component to a string."""
        ...


class BaseExportComponent(ABC):
    """Base class for export components with common functionality."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        self.config = config or ComponentConfig()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this component."""
        pass
    
    @property
    def description(self) -> str:
        """Human-readable description."""
        return f"{self.name} component"
    
    def should_render(self, context: ExportContext) -> bool:
        """Determine if this component should be rendered.
        
        Can be overridden for conditional rendering.
        """
        return self.config.enabled
    
    def get_data(self, context: ExportContext) -> Dict[str, Any]:
        """Extract data for rendering.
        
        Override this to provide data for rendering.
        Default implementation returns empty dict.
        """
        return {}
    
    @abstractmethod
    def render(self, context: ExportContext) -> str:
        """Render the component to a string."""
        pass
    
    def render_markdown(self, context: ExportContext) -> str:
        """Render as Markdown. Override for format-specific rendering."""
        # Check for user-defined renderer
        from .component_hooks import get_user_renderer
        custom_renderer = get_user_renderer(self.name)
        
        if custom_renderer:
            try:
                data = self.get_data(context)
                return custom_renderer(data)
            except Exception as e:
                logger.error(f"Custom renderer for {self.name} failed: {e}")
                # Fall back to default
        
        return self.render(context)
    
    def render_html(self, context: ExportContext) -> str:
        """Render as HTML. Override for format-specific rendering."""
        # Check for HTML-specific custom renderer
        from .component_hooks import get_user_renderer
        custom_renderer = get_user_renderer(f"{self.name}_html")
        
        if custom_renderer:
            try:
                data = self.get_data(context)
                return custom_renderer(data)
            except Exception as e:
                logger.error(f"Custom HTML renderer for {self.name} failed: {e}")
        
        # Default: convert markdown to HTML (could use markdown library)
        return f"<div class='{self.name}'>{self.render(context)}</div>"
    
    def render_hugo(self, context: ExportContext) -> str:
        """Render for Hugo. Override for format-specific rendering."""
        return self.render_markdown(context)
    
    def get_render_method(self, format: ExportFormat):
        """Get the appropriate render method for the format."""
        format_methods = {
            ExportFormat.MARKDOWN: self.render_markdown,
            ExportFormat.HTML: self.render_html,
            ExportFormat.HUGO: self.render_hugo,
        }
        return format_methods.get(format, self.render)


class ComponentRegistry:
    """Registry for managing export components.
    
    Provides registration, discovery, and dependency resolution.
    """
    
    def __init__(self):
        self._components: Dict[str, ExportComponent] = {}
        self._dependencies: Dict[str, List[str]] = {}
    
    def register(self, component: ExportComponent, 
                 depends_on: Optional[List[str]] = None) -> None:
        """Register a component with optional dependencies."""
        if not isinstance(component, ExportComponent):
            raise TypeError(f"{component} must implement ExportComponent protocol")
        
        self._components[component.name] = component
        if depends_on:
            self._dependencies[component.name] = depends_on
        
        logger.debug(f"Registered component: {component.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a component."""
        self._components.pop(name, None)
        self._dependencies.pop(name, None)
    
    def get(self, name: str) -> Optional[ExportComponent]:
        """Get a component by name."""
        return self._components.get(name)
    
    def list_components(self) -> List[str]:
        """List all registered component names."""
        return list(self._components.keys())
    
    def resolve_dependencies(self, names: List[str]) -> List[str]:
        """Resolve component dependencies and return ordered list."""
        resolved = []
        visited = set()
        
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            
            # Visit dependencies first
            for dep in self._dependencies.get(name, []):
                if dep in self._components:
                    visit(dep)
            
            if name not in resolved and name in self._components:
                resolved.append(name)
        
        for name in names:
            visit(name)
        
        return resolved


class ExportComposer:
    """Composes multiple components into a complete export.
    
    Handles component ordering, dependency resolution, and rendering.
    """
    
    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry or ComponentRegistry()
        self._component_order: List[tuple[int, str]] = []
    
    def add_component(self, name: str, priority: int = 100) -> None:
        """Add a component to the composition by name."""
        if name not in self.registry.list_components():
            raise ValueError(f"Component '{name}' not registered")
        
        self._component_order.append((priority, name))
        self._component_order.sort(key=lambda x: x[0])
    
    def compose(self, context: ExportContext) -> str:
        """Compose all components into final output."""
        output_parts = []
        
        # Resolve dependencies and get final order
        component_names = [name for _, name in self._component_order]
        ordered_names = self.registry.resolve_dependencies(component_names)
        
        # Render each component
        for name in ordered_names:
            component = self.registry.get(name)
            if component and component.should_render(context):
                try:
                    # Get format-specific render method if available
                    if hasattr(component, 'get_render_method'):
                        render_func = component.get_render_method(context.format)
                        rendered = render_func(context)
                    else:
                        rendered = component.render(context)
                    
                    if rendered:
                        output_parts.append(rendered)
                        logger.debug(f"Rendered component: {name}")
                except Exception as e:
                    logger.error(f"Error rendering component {name}: {e}")
        
        # Join with appropriate separator based on format
        separator = "\n\n" if context.format == ExportFormat.MARKDOWN else "\n"
        return separator.join(output_parts)
    
    @classmethod
    def from_config(cls, config: Dict[str, Any], 
                    registry: Optional[ComponentRegistry] = None) -> 'ExportComposer':
        """Create a composer from configuration."""
        composer = cls(registry)
        
        # Add components based on config
        components_config = config.get('components', {})
        for name, comp_config in components_config.items():
            if comp_config.get('enabled', True):
                priority = comp_config.get('priority', 100)
                composer.add_component(name, priority)
        
        return composer


# Default registry instance
default_registry = ComponentRegistry()



def register_component(depends_on: Optional[List[str]] = None):
    """Decorator to register a component class."""
    def decorator(cls):
        # Create instance and register
        instance = cls()
        default_registry.register(instance, depends_on)
        return cls
    return decorator