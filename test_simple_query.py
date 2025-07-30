#!/usr/bin/env python3
"""Test script for query module."""

import logging
from ghops.query import Query

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test data
test_repo = {
    "name": "jaf",
    "path": "/home/spinoza/github/repos/jaf",
    "tags": ["lang:python", "tools:cli", "json:parsing"],
    "language": "Python",
    "owner": "queelius",
    "stargazers_count": 0,
    "topics": ["json", "filter", "boolean-algebra"],
    "license": {
        "key": "mit",
        "name": "MIT License"
    }
}

# Test queries
test_queries = [
    # Simple queries
    "'lang:python' in tags",
    "tags contains 'python'",
    "language == 'Python'",
    "language ~= 'pyton'",  # Fuzzy match
    "owner == 'queelius'",
    
    # Complex queries
    "language == 'Python' and owner == 'queelius'",
    "'json' in topics or 'yaml' in topics",
    
    # Path queries
    "license.key == 'mit'",
    
    # Simple text search
    "json",
    "python"
]

print("Testing Query with sample repository data\n")
print(f"Test repository: {test_repo['name']}")
print(f"Tags: {test_repo['tags']}")
print(f"Language: {test_repo['language']}")
print("\n" + "="*60 + "\n")

for query_str in test_queries:
    print(f"Query: {query_str}")
    try:
        query = Query(query_str)
        result = query.evaluate(test_repo)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 40)