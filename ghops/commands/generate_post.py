"""
Generate and publish LLM-powered content about releases.

This command uses LLMs to create engaging blog posts, tweets, and other content
about software releases, then publishes them to various platforms.
"""

import click
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@click.command('generate-post')
@click.argument('platform', type=click.Choice(['devto', 'twitter', 'linkedin', 'bluesky', 'mastodon']))
@click.option('--repo', '-r',
              type=click.Path(exists=True),
              default='.',
              help='Repository path (default: current directory)')
@click.option('--version', '-v',
              required=True,
              help='Version to generate content for (e.g., 0.8.0)')
@click.option('--draft/--publish',
              default=False,
              help='Create as draft or publish immediately (default: publish)')
@click.option('--review/--no-review',
              default=True,
              help='Enable human review before publishing (default: enabled)')
@click.option('--save-only',
              is_flag=True,
              help='Only save generated content to file, don\'t publish')
@click.option('--title',
              help='Override generated title')
@click.option('--tags',
              help='Comma-separated tags (e.g., "python,opensource,cli")')
@click.option('--temperature',
              type=float,
              default=0.7,
              help='LLM temperature (0.0-2.0, default: 0.7)')
def generate_post_handler(platform, repo, version, draft, review, save_only,
                          title, tags, temperature):
    """
    Generate and publish LLM-powered content about a release.

    This command:
    1. Builds comprehensive context from your repository
    2. Generates engaging content using configured LLM
    3. Optionally opens in editor for human review
    4. Publishes to the target platform

    Examples:

        # Generate and publish a dev.to blog post (with review)
        ghops generate-post devto --version 0.8.0

        # Generate a draft (not published)
        ghops generate-post devto --version 0.8.0 --draft

        # Skip human review (auto-publish)
        ghops generate-post devto --version 0.8.0 --no-review

        # Save to file only (don't publish)
        ghops generate-post devto --version 0.8.0 --save-only

        # Generate Twitter post
        ghops generate-post twitter --version 0.8.0

    Configuration:

        Add LLM and platform credentials to ~/.ghops/config.json:

        {
          "llm": {
            "default_provider": "ollama",
            "providers": {
              "ollama": {
                "base_url": "http://localhost:11434",
                "model": "llama3.2"
              },
              "openai": {
                "api_key": "sk-...",
                "model": "gpt-4-turbo-preview"
              }
            },
            "publishing": {
              "default_platform": "devto",
              "platforms": {
                "devto": {
                  "api_key": "your-devto-api-key"
                }
              }
            }
          }
        }

        Or use environment variables:
        - DEVTO_API_KEY
        - OPENAI_API_KEY
    """
    from ..config import load_config
    from ..llm import (
        build_content_context,
        get_llm_provider,
        build_devto_release_prompt,
        build_twitter_release_prompt,
        build_linkedin_release_prompt,
        get_system_prompt,
        extract_title_from_markdown,
        extract_tags_from_content,
        review_and_publish_workflow,
        save_content_to_file
    )

    try:
        # Load config
        config = load_config()

        # Step 1: Build context
        click.echo("=" * 60)
        click.echo("🔍 Building content context...")
        click.echo("=" * 60)

        repo_path = str(Path(repo).resolve())
        context = build_content_context(repo_path, version)

        click.echo(f"\n✅ Context built for {context.repo_name} v{context.version}")
        click.echo(f"   Language: {context.language}")
        click.echo(f"   Previous version: {context.previous_version or 'N/A'}")
        if context.new_features:
            click.echo(f"   New features: {len(context.new_features)}")
        if context.bug_fixes:
            click.echo(f"   Bug fixes: {len(context.bug_fixes)}")

        # Step 2: Get LLM provider
        click.echo("\n" + "=" * 60)
        click.echo("🤖 Initializing LLM provider...")
        click.echo("=" * 60)

        provider = get_llm_provider(config)
        provider_info = provider.get_info()

        click.echo(f"\n✅ Provider: {provider_info.get('provider')}")
        if 'model' in provider_info:
            click.echo(f"   Model: {provider_info.get('model')}")
        if 'base_url' in provider_info:
            click.echo(f"   Endpoint: {provider_info.get('base_url')}")

        # Step 3: Build prompt
        click.echo("\n" + "=" * 60)
        click.echo(f"📝 Generating {platform} content...")
        click.echo("=" * 60)

        if platform == 'devto':
            prompt = build_devto_release_prompt(context)
            system_prompt = get_system_prompt('devto')
            max_tokens = 2000
        elif platform == 'twitter':
            prompt = build_twitter_release_prompt(context)
            system_prompt = get_system_prompt('twitter')
            max_tokens = 100
        elif platform == 'bluesky':
            # Bluesky uses similar format to Twitter (short posts)
            prompt = build_twitter_release_prompt(context)
            system_prompt = "You are creating a short, engaging post for Bluesky (max 300 chars). Be conversational and use relevant hashtags."
            max_tokens = 100
        elif platform == 'mastodon':
            # Mastodon allows longer posts than Twitter (500 chars)
            prompt = build_twitter_release_prompt(context)
            system_prompt = "You are creating a post for Mastodon (max 500 chars). Be engaging and community-focused. Use relevant hashtags."
            max_tokens = 150
        elif platform == 'linkedin':
            prompt = build_linkedin_release_prompt(context)
            system_prompt = get_system_prompt('linkedin')
            max_tokens = 800
        else:
            click.echo(f"❌ Unsupported platform: {platform}")
            return 1

        # Step 4: Generate content
        click.echo(f"\n🚀 Generating content (this may take 30-90 seconds)...")

        content = provider.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=120
        )

        word_count = len(content.split())
        click.echo(f"\n✅ Generated content ({word_count} words)")

        # Step 5: Extract metadata
        metadata = {}

        # Extract or use provided title
        if title:
            metadata['title'] = title
        else:
            extracted_title = extract_title_from_markdown(content)
            if extracted_title:
                metadata['title'] = extracted_title
            else:
                metadata['title'] = f"{context.repo_name} {version} Release"

        # Extract or use provided tags
        if tags:
            metadata['tags'] = [t.strip() for t in tags.split(',')]
        else:
            metadata['tags'] = extract_tags_from_content(content, context)

        # Add canonical URL if available
        if context.github_url:
            metadata['canonical_url'] = context.github_url

        click.echo(f"\n📋 Metadata:")
        click.echo(f"   Title: {metadata['title']}")
        click.echo(f"   Tags: {', '.join(metadata['tags'])}")

        # Step 6: Save to file if requested
        if save_only:
            output_path = save_content_to_file(content, repo_path, version, platform)
            click.echo(f"\n✅ Content saved to: {output_path}")
            click.echo("\n💡 Review the content, then publish manually with:")
            click.echo(f"   ghops generate-post {platform} --version {version}")
            return 0

        # Step 7: Review and publish workflow
        result = review_and_publish_workflow(
            content=content,
            metadata=metadata,
            platform_name=platform,
            human_review=review,
            create_draft=draft
        )

        # Step 8: Report result
        if result['status'] in ('published', 'draft'):
            click.echo("\n" + "=" * 60)
            click.echo(f"✅ SUCCESS - Content {result['status']}!")
            click.echo("=" * 60)
            if result.get('url'):
                click.echo(f"\n🔗 URL: {result['url']}")
            if result.get('id'):
                click.echo(f"   ID: {result['id']}")

            # Record in analytics database
            try:
                from ..analytics_store import get_analytics_store
                analytics_store = get_analytics_store()

                platform_post_id = result.get('id', 'unknown')
                post_url = result.get('url', '')

                db_post_id = analytics_store.record_post(
                    repo_path=repo_path,
                    version=version,
                    platform=platform,
                    platform_post_id=str(platform_post_id),
                    url=post_url,
                    metadata=metadata
                )

                click.echo(f"\n📊 Recorded in analytics (DB ID: {db_post_id})")

            except Exception as e:
                logger.warning(f"Failed to record post in analytics: {e}")
                # Don't fail the whole command if analytics fails
                click.echo(f"   ⚠️  Analytics recording failed: {e}")

            # Also save to file
            output_path = save_content_to_file(content, repo_path, version, platform)
            click.echo(f"\n📁 Backup saved to: {output_path}")

            return 0

        elif result['status'] == 'cancelled':
            click.echo(f"\n⚠️  {result['message']}")
            return 1

        else:  # error
            click.echo(f"\n❌ Error: {result['message']}")
            return 1

    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        click.echo(f"\n❌ Error: {e}")
        click.echo("\n💡 Troubleshooting:")
        click.echo("   1. Check your config at ~/.ghops/config.json")
        click.echo("   2. Verify LLM provider is accessible (Ollama/OpenAI)")
        click.echo("   3. Check platform API credentials (dev.to)")
        click.echo("   4. Run with --help for usage examples")
        return 1
