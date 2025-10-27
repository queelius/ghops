"""
Human review workflow for LLM-generated content.

Provides interactive editing and approval before publishing.
"""

import os
import tempfile
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def get_editor() -> str:
    """
    Get the user's preferred editor.

    Checks in order:
    1. VISUAL environment variable
    2. EDITOR environment variable
    3. Falls back to 'nano' (more user-friendly than vim)

    Returns:
        Editor command
    """
    return os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'nano'


def review_content_in_editor(content: str, file_extension: str = '.md') -> Optional[str]:
    """
    Open content in user's editor for review and editing.

    Args:
        content: The content to review (markdown, text, etc.)
        file_extension: File extension for syntax highlighting (default: .md)

    Returns:
        Edited content if user saved, None if cancelled
    """
    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix=file_extension,
        delete=False,
        encoding='utf-8'
    ) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # Get editor
        editor = get_editor()

        # Open in editor
        logger.info(f"Opening content in {editor}...")
        print(f"\n📝 Opening content in {editor} for review...")
        print(f"   File: {tmp_path}")
        print(f"   Edit the content, save, and close the editor to continue.")
        print(f"   Or exit without saving to cancel.\n")

        # Run editor
        result = subprocess.run([editor, tmp_path])

        if result.returncode != 0:
            logger.warning(f"Editor exited with code {result.returncode}")
            print("⚠️  Editor exited with error. Cancelling...")
            return None

        # Read edited content
        with open(tmp_path, 'r', encoding='utf-8') as f:
            edited_content = f.read()

        # Check if content changed
        if edited_content == content:
            logger.info("Content unchanged")
            print("ℹ️  Content unchanged from original.")
        else:
            logger.info("Content was edited")
            print("✅ Content was edited.")

        return edited_content

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass


def confirm_publication(platform: str = "dev.to") -> bool:
    """
    Ask user to confirm publication.

    Args:
        platform: Platform name for display

    Returns:
        True if user confirms, False otherwise
    """
    print(f"\n📤 Ready to publish to {platform}")
    print("   This will create a published post (not a draft).")

    while True:
        response = input("\n   Publish now? [y/n]: ").strip().lower()

        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            print("   ❌ Publication cancelled.")
            return False
        else:
            print("   Please enter 'y' or 'n'")


def confirm_draft_creation(platform: str = "dev.to") -> bool:
    """
    Ask user to confirm draft creation.

    Args:
        platform: Platform name for display

    Returns:
        True if user confirms, False otherwise
    """
    print(f"\n📝 Ready to create draft on {platform}")

    while True:
        response = input("\n   Create draft? [y/n]: ").strip().lower()

        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            print("   ❌ Draft creation cancelled.")
            return False
        else:
            print("   Please enter 'y' or 'n'")


def review_and_publish_workflow(
    content: str,
    metadata: Dict[str, Any],
    platform_name: str = "devto",
    human_review: bool = True,
    create_draft: bool = False
) -> Dict[str, Any]:
    """
    Complete workflow for reviewing and publishing content.

    Args:
        content: Generated content
        metadata: Platform metadata (title, tags, etc.)
        platform_name: Target platform
        human_review: Whether to enable human review (default: True)
        create_draft: Whether to create draft instead of publishing (default: False)

    Returns:
        Dict with workflow result:
            - status: 'published', 'draft', 'cancelled', 'error'
            - url: Published URL (if successful)
            - message: Status message

    Example:
        >>> result = review_and_publish_workflow(
        ...     content=generated_post,
        ...     metadata={'title': 'My Post', 'tags': ['python']},
        ...     human_review=True
        ... )
        >>> print(result['url'])
    """
    from .platforms import get_publishing_platform

    try:
        # Step 1: Human review if enabled
        if human_review:
            print("\n" + "=" * 60)
            print("📝 CONTENT REVIEW")
            print("=" * 60)

            edited_content = review_content_in_editor(content, '.md')

            if edited_content is None:
                return {
                    'status': 'cancelled',
                    'message': 'User cancelled during review'
                }

            content = edited_content

        # Step 2: Confirm publication
        if create_draft:
            if human_review and not confirm_draft_creation(platform_name):
                return {
                    'status': 'cancelled',
                    'message': 'User cancelled draft creation'
                }
        else:
            if human_review and not confirm_publication(platform_name):
                return {
                    'status': 'cancelled',
                    'message': 'User cancelled publication'
                }

        # Step 3: Get platform
        from ..config import load_config
        config = load_config()
        platform = get_publishing_platform(config)

        # Step 4: Publish or create draft
        print(f"\n🚀 {'Creating draft' if create_draft else 'Publishing'} to {platform_name}...")

        if create_draft:
            result = platform.create_draft(content, metadata)
        else:
            metadata = metadata.copy()
            metadata['published'] = True
            result = platform.publish(content, metadata)

        print(f"✅ {'Draft created' if create_draft else 'Published'} successfully!")
        print(f"   URL: {result.get('url', 'N/A')}")
        print(f"   ID: {result.get('id', 'N/A')}")

        return {
            'status': result.get('status', 'draft' if create_draft else 'published'),
            'url': result.get('url'),
            'id': result.get('id'),
            'message': f"{'Draft created' if create_draft else 'Published'} successfully"
        }

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return {
            'status': 'cancelled',
            'message': 'Interrupted by user'
        }

    except Exception as e:
        logger.error(f"Publication failed: {e}")
        print(f"\n❌ Publication failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


def save_content_to_file(content: str, repo_path: str, version: str, platform: str) -> Path:
    """
    Save generated content to a file in the repository.

    Args:
        content: The content to save
        repo_path: Repository path
        version: Version string
        platform: Platform name

    Returns:
        Path to saved file
    """
    # Create output directory
    output_dir = Path(repo_path) / '.ghops' / 'generated_content'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    filename = f"{platform}_{version}.md"
    output_path = output_dir / filename

    # Save content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Saved content to {output_path}")
    return output_path
