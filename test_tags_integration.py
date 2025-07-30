#!/usr/bin/env python3
"""Test tags integration in status output."""

import json
import subprocess

# Run status command
result = subprocess.run(
    ["python", "-m", "ghops.cli", "status"],
    capture_output=True,
    text=True
)

# Parse JSONL output
repos_with_tags = []
for line in result.stdout.strip().split('\n'):
    if line and not line.startswith("ERROR"):
        try:
            repo = json.loads(line)
            if repo.get('tags'):
                repos_with_tags.append({
                    'name': repo['name'],
                    'tags': repo['tags'][:5]  # First 5 tags
                })
        except json.JSONDecodeError:
            pass

# Show results
print(f"Found {len(repos_with_tags)} repositories with tags:\n")
for repo in repos_with_tags[:5]:  # Show first 5
    print(f"{repo['name']}:")
    for tag in repo['tags']:
        print(f"  - {tag}")
    print()