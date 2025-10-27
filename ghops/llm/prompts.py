"""
Prompt templates for LLM content generation.

Provides structured prompts for generating engaging blog posts
about software projects and releases.

Supports Jinja2 templates for customization. Templates are loaded from:
1. ~/.ghops/templates/{platform}/ (user templates)
2. Built-in templates (fallback)
3. Hardcoded prompts (final fallback for backward compatibility)
"""

from typing import Dict, Any, Optional
from .content_context import ContentContext
import logging

logger = logging.getLogger(__name__)


def _try_template_render(platform: str, context: ContentContext,
                         template_name: str = 'default',
                         **kwargs) -> Optional[str]:
    """
    Try to render using Jinja2 template.

    Args:
        platform: Platform name
        context: ContentContext
        template_name: Template name
        **kwargs: Additional template variables

    Returns:
        Rendered prompt or None if template not available
    """
    try:
        from .template_loader import get_template_loader
        loader = get_template_loader()
        return loader.render_prompt(platform, context, template_name, **kwargs)
    except Exception as e:
        logger.debug(f"Template rendering failed, using hardcoded prompt: {e}")
        return None


def build_devto_release_prompt(context: ContentContext,
                               template_name: str = 'default',
                               **kwargs) -> str:
    """
    Build a prompt for generating a dev.to blog post about a release.

    This follows the content strategy:
    - What is X? (Project overview + motivation)
    - What's New? (Release highlights)
    - Core Features (All key features, not just new)
    - Getting Started (Installation + quick example)
    - Full Changelog (Categorized)

    Args:
        context: ContentContext with all repo information

    Returns:
        Formatted prompt string for the LLM
    """
    # Try template rendering first
    template_result = _try_template_render('devto', context, template_name, **kwargs)
    if template_result:
        return template_result

    # Fallback to hardcoded prompt
    # Build sections
    sections = []

    # 1. Project basics
    sections.append(f"**Project**: {context.repo_name}")
    sections.append(f"**Language**: {context.language}")
    sections.append(f"**Version**: {context.version}")
    if context.previous_version:
        sections.append(f"**Previous Version**: {context.previous_version}")

    # 2. Description
    if context.description:
        sections.append(f"\n**Description**: {context.description}")

    # 3. Core features (ALL features, not just new)
    if context.core_features:
        sections.append("\n**Core Features**:")
        for feat in context.core_features:
            sections.append(f"- {feat}")

    # 4. What's new in this release
    if context.new_features or context.bug_fixes or context.breaking_changes:
        sections.append("\n**What's New in This Release**:")

        if context.breaking_changes:
            sections.append("\n*Breaking Changes*:")
            for change in context.breaking_changes:
                sections.append(f"- {change}")

        if context.new_features:
            sections.append("\n*New Features*:")
            for feat in context.new_features:
                sections.append(f"- {feat}")

        if context.bug_fixes:
            sections.append("\n*Bug Fixes*:")
            for fix in context.bug_fixes:
                sections.append(f"- {fix}")

    # 5. Getting started
    if context.installation_snippet:
        sections.append(f"\n**Installation**:\n```\n{context.installation_snippet}\n```")

    if context.quick_example:
        sections.append(f"\n**Quick Example**:\n```\n{context.quick_example}\n```")

    # 6. Links
    links = []
    if context.github_url:
        links.append(f"- GitHub: {context.github_url}")
    if context.package_registry_url:
        links.append(f"- Package: {context.package_registry_url}")
    if context.docs_url:
        links.append(f"- Docs: {context.docs_url}")

    if links:
        sections.append("\n**Links**:")
        sections.extend(links)

    # 7. Additional context
    if context.topics:
        sections.append(f"\n**Topics**: {', '.join(context.topics[:10])}")

    if context.use_cases:
        sections.append("\n**Use Cases**:")
        for use_case in context.use_cases:
            sections.append(f"- {use_case}")

    # Build the full prompt
    context_block = "\n".join(sections)

    prompt = f"""You are a technical writer creating an engaging blog post for dev.to about a software project release.

# Context Information

{context_block}

# Your Task

Write a compelling blog post (800-1500 words) that:

1. **Opens with a hook** - Start with an interesting question, problem, or insight that developers care about
2. **Introduces the project** - Explain what {context.repo_name} is and WHY it exists (motivation/problem it solves)
3. **Highlights what's new** - If this is a new version, explain what's changed and why users should care
4. **Showcases core capabilities** - Explain the main features that make this project useful (not just what's new)
5. **Provides getting started** - Show how to install and use it with clear examples
6. **Ends with a call to action** - Encourage readers to try it, contribute, or share feedback

# Writing Style

- **Conversational but professional** - Write like you're explaining to a colleague
- **Focus on value** - Explain WHY features matter, not just WHAT they do
- **Use concrete examples** - Show real use cases and code when possible
- **Be honest** - Don't oversell, acknowledge limitations or areas for growth
- **Engaging structure** - Use headers, code blocks, lists for readability

# Format

Return ONLY the blog post content in Markdown format. Structure it with:
- Catchy title (as H1)
- Introduction paragraph (hook + context)
- H2 sections for: What is it?, What's New, Core Features, Getting Started
- Code blocks where appropriate
- Conclusion with links and call to action

Do NOT include frontmatter, tags, or metadata - just the markdown content.

# Important Notes

- If this is version {context.version}, treat it as an {("update/enhancement" if context.previous_version else "initial release")}
- Emphasize practical value for developers
- Make it interesting enough that people want to try it
- Keep it under 1500 words but make every word count
"""

    return prompt


def build_twitter_release_prompt(context: ContentContext,
                                 template_name: str = 'default',
                                 **kwargs) -> str:
    """
    Build a prompt for generating a Twitter/X post about a release.

    Args:
        context: ContentContext with all repo information
        template_name: Template name (default: 'default')
        **kwargs: Additional template variables

    Returns:
        Formatted prompt string for the LLM
    """
    # Try template rendering first
    template_result = _try_template_render('twitter', context, template_name, **kwargs)
    if template_result:
        return template_result

    # Fallback to hardcoded prompt
    highlights = []

    # Add breaking changes first (most important)
    if context.breaking_changes:
        highlights.append(f"⚠️ Breaking Changes: {len(context.breaking_changes)}")

    # Add feature count
    if context.new_features:
        highlights.append(f"✨ New Features: {len(context.new_features)}")

    # Add fix count
    if context.bug_fixes:
        highlights.append(f"🐛 Bug Fixes: {len(context.bug_fixes)}")

    highlights_text = "\n".join(highlights) if highlights else "Various improvements"

    prompt = f"""Create a compelling Twitter/X post announcing {context.repo_name} version {context.version}.

**Project**: {context.repo_name}
**Description**: {context.description or 'A developer tool'}
**Version**: {context.version}
**Language**: {context.language}

**Highlights**:
{highlights_text}

**Links**:
- GitHub: {context.github_url or 'N/A'}
- Package: {context.package_registry_url or 'N/A'}

Create a tweet that:
1. Is engaging and makes developers want to check it out
2. Stays under 280 characters
3. Includes 2-3 relevant hashtags
4. Has a clear call to action
5. Mentions the most exciting feature or improvement

Return ONLY the tweet text, nothing else.
"""

    return prompt


def build_linkedin_release_prompt(context: ContentContext,
                                  template_name: str = 'default',
                                  **kwargs) -> str:
    """
    Build a prompt for generating a LinkedIn post about a release.

    Args:
        context: ContentContext with all repo information
        template_name: Template name (default: 'default')
        **kwargs: Additional template variables

    Returns:
        Formatted prompt string for the LLM
    """
    # Try template rendering first
    template_result = _try_template_render('linkedin', context, template_name, **kwargs)
    if template_result:
        return template_result

    # Fallback to hardcoded prompt
    # Build feature highlights
    feature_list = []
    if context.new_features:
        for feat in context.new_features[:5]:
            feature_list.append(f"• {feat}")

    features_text = "\n".join(feature_list) if feature_list else "Various improvements and enhancements"

    prompt = f"""Create a professional LinkedIn post announcing {context.repo_name} version {context.version}.

**Project**: {context.repo_name}
**Description**: {context.description or 'A developer tool'}
**Version**: {context.version}
**Previous Version**: {context.previous_version or 'Initial release'}
**Language**: {context.language}
**Topics**: {', '.join(context.topics[:5]) if context.topics else 'N/A'}

**New Features**:
{features_text}

**Links**:
- GitHub: {context.github_url or 'N/A'}
- Package: {context.package_registry_url or 'N/A'}
- Docs: {context.docs_url or 'N/A'}

Create a LinkedIn post (300-500 words) that:
1. Starts with a professional but engaging hook
2. Explains the value proposition for developers/teams
3. Highlights key improvements in this release
4. Shows real-world use cases or benefits
5. Ends with a call to action (try it, contribute, share feedback)
6. Uses a professional tone suitable for LinkedIn
7. Includes 3-5 relevant hashtags at the end

Return ONLY the post text in plain text format.
"""

    return prompt


def get_system_prompt(platform: str = "devto") -> str:
    """
    Get the system prompt for a specific platform.

    Args:
        platform: Target platform (devto, twitter, linkedin)

    Returns:
        System prompt string
    """

    if platform == "devto":
        return """You are an experienced technical writer who creates engaging, developer-focused blog posts.
You understand how to:
- Hook readers with interesting problems or questions
- Explain technical concepts clearly without oversimplifying
- Use concrete examples and code to illustrate points
- Structure content for easy scanning and readability
- Balance enthusiasm with honesty about limitations
- Write in a conversational but professional tone

Your posts get developers excited about trying new tools while giving them all the information they need to make informed decisions."""

    elif platform == "twitter":
        return """You are a developer advocate who crafts compelling, concise social media posts.
You know how to:
- Hook attention in the first few words
- Convey value in minimal characters
- Use emojis strategically (not excessively)
- Create FOMO without being salesy
- Write clear calls to action
- Use hashtags that developers actually follow

Your tweets get engagement because they're valuable, not spammy."""

    elif platform == "linkedin":
        return """You are a professional technical communicator who creates valuable content for developers and engineering leaders on LinkedIn.
You know how to:
- Start with insights that resonate with professionals
- Frame technical topics in business context when relevant
- Write with authority without being arrogant
- Use storytelling to make technical content engaging
- Appeal to both individual developers and decision-makers
- Maintain a professional tone while being approachable

Your posts build credibility and spark meaningful discussions."""

    else:
        return "You are a technical writer creating engaging content about software projects."
