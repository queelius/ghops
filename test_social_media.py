#!/usr/bin/env python3
"""Test script for social media functionality."""

import json
from ghops.social import (
    generate_social_content,
    generate_hashtags,
    post_to_twitter,
    post_to_linkedin,
    post_to_mastodon
)

# Test repository metadata
test_repo = {
    'name': 'ghops',
    'description': 'A multi-platform git project management system',
    'language': 'Python',
    'stargazers_count': 42,
    'topics': ['git', 'github', 'automation'],
    'owner': 'testuser',
    'homepage': 'https://github.com/testuser/ghops'
}

# Test platform configs
twitter_config = {
    'enabled': True,
    'template': '🚀 Check out {{repo_name}}! {{description}} ⭐ {{stars}} stars {{hashtags}} {{url}}'
}

linkedin_config = {
    'enabled': True,
    'template': 'Excited to share {{repo_name}}!\n\n{{description}}\n\n🔧 Built with {{language}}\n⭐ {{stars}} stars\n\n{{hashtags}}\n\n{{url}}'
}

mastodon_config = {
    'enabled': True,
    'template': '📦 {{repo_name}}: {{description}}\n\n{{hashtags}}\n\n{{url}}'
}

print("Testing Social Media Content Generation\n")
print("=" * 60)

# Test content generation
print("\n1. Twitter Content:")
twitter_content = generate_social_content(test_repo, 'twitter', twitter_config)
print(twitter_content)
print(f"Length: {len(twitter_content)} characters")

print("\n2. LinkedIn Content:")
linkedin_content = generate_social_content(test_repo, 'linkedin', linkedin_config)
print(linkedin_content)

print("\n3. Mastodon Content:")
mastodon_content = generate_social_content(test_repo, 'mastodon', mastodon_config)
print(mastodon_content)

# Test hashtag generation
print("\n4. Hashtags:")
hashtags = generate_hashtags(test_repo, twitter_config)
print(f"Generated hashtags: {hashtags}")

# Test posting functions (dry run)
print("\n5. Testing posting functions (dry run):")

print("\n- Twitter post result:")
twitter_result = post_to_twitter(twitter_content, {}, dry_run=True)
print(json.dumps(twitter_result, indent=2))

print("\n- LinkedIn post result:")
linkedin_result = post_to_linkedin(linkedin_content, {}, dry_run=True)
print(json.dumps(linkedin_result, indent=2))

print("\n- Mastodon post result:")
mastodon_result = post_to_mastodon(mastodon_content, {}, dry_run=True)
print(json.dumps(mastodon_result, indent=2))

print("\n" + "=" * 60)
print("Test complete!")