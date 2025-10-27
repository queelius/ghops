"""
LLM integration for ghops.

Provides abstraction over multiple LLM providers for content generation
and publishing to various platforms.
"""

from .providers import LLMProvider, OllamaProvider, OpenAIProvider, get_llm_provider
from .content_context import ContentContext, build_content_context
from .prompts import (
    build_devto_release_prompt,
    build_twitter_release_prompt,
    build_linkedin_release_prompt,
    get_system_prompt
)
from .platforms import (
    PublishingPlatform,
    DevToPlatform,
    BlueskyPlatform,
    MastodonPlatform,
    get_publishing_platform,
    extract_title_from_markdown,
    extract_tags_from_content
)
from .review import (
    review_content_in_editor,
    confirm_publication,
    confirm_draft_creation,
    review_and_publish_workflow,
    save_content_to_file
)

__all__ = [
    # Providers
    'LLMProvider',
    'OllamaProvider',
    'OpenAIProvider',
    'get_llm_provider',

    # Content Context
    'ContentContext',
    'build_content_context',

    # Prompts
    'build_devto_release_prompt',
    'build_twitter_release_prompt',
    'build_linkedin_release_prompt',
    'get_system_prompt',

    # Platforms
    'PublishingPlatform',
    'DevToPlatform',
    'BlueskyPlatform',
    'MastodonPlatform',
    'get_publishing_platform',
    'extract_title_from_markdown',
    'extract_tags_from_content',

    # Review
    'review_content_in_editor',
    'confirm_publication',
    'confirm_draft_creation',
    'review_and_publish_workflow',
    'save_content_to_file',
]
