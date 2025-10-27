"""
Smart Templates System - Extract patterns and create reusable templates.

This module provides capabilities for:
- Extracting patterns from successful repositories
- Building templates with variable substitution
- Supporting template inheritance and composition
- Creating template versioning and migration
- Including starter templates for common project types
"""

from .extractor import TemplateExtractor
from .engine import TemplateEngine
from .library import TemplateLibrary

__all__ = [
    'TemplateExtractor',
    'TemplateEngine',
    'TemplateLibrary',
]