"""
Event handlers for automated actions.

Handlers respond to events by:
- Posting to social media platforms
- Publishing packages to registries
- Sending notifications
"""

from typing import List, Dict, Any
import logging
from pathlib import Path

from .events import Event, EventHandler

logger = logging.getLogger(__name__)


class SocialMediaPostHandler(EventHandler):
    """
    Post to social media when events occur.

    Configured platforms and settings determine where posts are published.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize social media handler.

        Config structure:
        {
            "type": "social_media_post",
            "enabled": true,
            "trigger": "git_tag",
            "conditions": {
                "tag_pattern": "v*",
                "branches": ["main", "master"]
            },
            "actions": {
                "platforms": [
                    {"name": "devto", "draft": false, "human_review": true},
                    {"name": "twitter", "human_review": false},
                    {"name": "mastodon", "human_review": false}
                ]
            }
        }
        """
        super().__init__(config)
        self.trigger = config.get('trigger', 'git_tag')
        self.conditions = config.get('conditions', {})
        self.platforms = config.get('actions', {}).get('platforms', [])

    def should_handle(self, event: Event) -> bool:
        """Check if event should trigger social media posts."""
        # Check event type
        if event.type != self.trigger:
            return False

        # Check conditions
        if not self._check_conditions(event, self.conditions):
            return False

        return True

    def handle(self, event: Event) -> List[Dict[str, Any]]:
        """Generate and post content to configured platforms."""
        results = []

        # Extract version from tag
        tag = event.context.get('tag', '')
        version = tag.lstrip('v')  # Remove 'v' prefix if present

        logger.info(f"Generating social media posts for {event.repo_path} version {version}")

        for platform_config in self.platforms:
            platform_name = platform_config['name']
            draft = platform_config.get('draft', False)
            human_review = platform_config.get('human_review', True)

            try:
                result = self._generate_and_post(
                    repo_path=event.repo_path,
                    version=version,
                    platform=platform_name,
                    draft=draft,
                    human_review=human_review
                )

                results.append({
                    'action': 'social_post',
                    'platform': platform_name,
                    'status': result.get('status', 'unknown'),
                    'url': result.get('url'),
                    'post_id': result.get('id')
                })

            except Exception as e:
                logger.error(f"Failed to post to {platform_name}: {e}", exc_info=True)
                results.append({
                    'action': 'social_post',
                    'platform': platform_name,
                    'status': 'failed',
                    'error': str(e)
                })

        return results

    def _generate_and_post(self, repo_path: str, version: str,
                          platform: str, draft: bool = False,
                          human_review: bool = True) -> Dict[str, Any]:
        """
        Generate content and post to platform.

        Args:
            repo_path: Repository path
            version: Version string
            platform: Platform name
            draft: Create as draft
            human_review: Enable human review

        Returns:
            Result dict with status, url, id
        """
        from .llm import (
            build_content_context,
            get_llm_provider,
            build_devto_release_prompt,
            build_twitter_release_prompt,
            build_linkedin_release_prompt,
            get_system_prompt,
            extract_title_from_markdown,
            extract_tags_from_content,
            review_and_publish_workflow
        )
        from .config import load_config

        config = load_config()

        # Build context
        context = build_content_context(repo_path, version)

        # Get LLM provider
        provider = get_llm_provider(config)

        # Generate prompt
        if platform == 'devto':
            prompt = build_devto_release_prompt(context)
            system_prompt = get_system_prompt('devto')
            max_tokens = 2000
        elif platform in ('twitter', 'bluesky', 'mastodon'):
            prompt = build_twitter_release_prompt(context)
            if platform == 'bluesky':
                system_prompt = "You are creating a short, engaging post for Bluesky (max 300 chars)."
            elif platform == 'mastodon':
                system_prompt = "You are creating a post for Mastodon (max 500 chars)."
            else:
                system_prompt = get_system_prompt('twitter')
            max_tokens = 100
        elif platform == 'linkedin':
            prompt = build_linkedin_release_prompt(context)
            system_prompt = get_system_prompt('linkedin')
            max_tokens = 800
        else:
            raise ValueError(f"Unsupported platform: {platform}")

        # Generate content
        logger.info(f"Generating content for {platform}...")
        content = provider.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=max_tokens,
            timeout=120
        )

        # Extract metadata
        metadata = {}
        if platform == 'devto':
            title = extract_title_from_markdown(content)
            metadata['title'] = title or f"{context.repo_name} {version} Release"
            metadata['tags'] = extract_tags_from_content(content, context)
            if context.github_url:
                metadata['canonical_url'] = context.github_url

        # Publish
        result = review_and_publish_workflow(
            content=content,
            metadata=metadata,
            platform_name=platform,
            human_review=human_review,
            create_draft=draft
        )

        return result


class PublishPackageHandler(EventHandler):
    """
    Publish package to registry when events occur.

    Automatically publishes to PyPI, npm, etc. based on project type.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize package publish handler.

        Config structure:
        {
            "type": "publish_package",
            "enabled": true,
            "trigger": "git_tag",
            "conditions": {
                "tag_pattern": "v*",
                "project_types": ["python"]
            }
        }
        """
        super().__init__(config)
        self.trigger = config.get('trigger', 'git_tag')
        self.conditions = config.get('conditions', {})

    def should_handle(self, event: Event) -> bool:
        """Check if event should trigger package publish."""
        # Check event type
        if event.type != self.trigger:
            return False

        # Check conditions
        if not self._check_conditions(event, self.conditions):
            return False

        # Detect project type
        from .commands.publish import ProjectDetector
        project_types = ProjectDetector.detect(event.repo_path)

        # Check if any project type matches conditions
        allowed_types = self.conditions.get('project_types', [])
        if allowed_types and not any(pt in allowed_types for pt in project_types):
            return False

        # Store project type in event context for later use
        event.context['project_type'] = project_types[0] if project_types else 'unknown'

        return True

    def handle(self, event: Event) -> List[Dict[str, Any]]:
        """Publish package to appropriate registry."""
        results = []

        tag = event.context.get('tag', '')
        version = tag.lstrip('v')
        project_type = event.context.get('project_type', 'unknown')

        logger.info(f"Publishing {project_type} package from {event.repo_path} version {version}")

        try:
            result = self._publish_package(
                repo_path=event.repo_path,
                version=version,
                project_type=project_type
            )

            results.append({
                'action': 'publish_package',
                'project_type': project_type,
                'status': 'success' if result else 'failed',
                'version': version
            })

        except Exception as e:
            logger.error(f"Failed to publish package: {e}", exc_info=True)
            results.append({
                'action': 'publish_package',
                'project_type': project_type,
                'status': 'failed',
                'error': str(e)
            })

        return results

    def _publish_package(self, repo_path: str, version: str, project_type: str) -> bool:
        """
        Publish package using ghops publish command.

        Args:
            repo_path: Repository path
            version: Version string
            project_type: Project type (python, node, etc.)

        Returns:
            True if successful
        """
        from .utils import run_command

        # Change to repo directory and run publish
        logger.info(f"Running ghops publish in {repo_path}")

        # For now, we'll just log that we would publish
        # In production, you'd actually run the publish command
        logger.info(f"Would publish {project_type} package version {version}")

        # TODO: Actually run publish command
        # output, returncode = run_command(
        #     'ghops publish --yes',
        #     cwd=repo_path,
        #     capture_output=True,
        #     check=False
        # )
        #
        # return returncode == 0

        return True
