#!/usr/bin/env python3
"""Test script for query engine improvements."""

from ghops.query import Query

# Test data
test_repo = {
    'name': 'test-repo',
    'language': 'Python',
    'stars': 42,
    'topics': ['python', 'cli', 'testing'],
    'owner': 'testuser',
    'license': {
        'key': 'mit',
        'name': 'MIT License'
    }
}

print("Testing Query improvements\n")
print("=" * 60)

# Test 1: Regex operator
print("\n1. Testing regex operator (=~):")
test_cases = [
    ("language =~ '^Py.*'", True),
    ("language =~ 'thon$'", True),
    ("language =~ '^Java'", False),
    ("name =~ 'test-.*'", True),
]

for query_str, expected in test_cases:
    try:
        q = Query(query_str)
        result = q.evaluate(test_repo)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {query_str} -> {result} (expected: {expected})")
    except Exception as e:
        print(f"  ✗ {query_str} -> ERROR: {e}")

# Test 2: Improved quote handling
print("\n2. Testing improved quote handling:")
test_cases = [
    ("name == 'test-repo' and language == 'Python'", True),
    ("'python' in topics and owner == 'testuser'", True),
]

for query_str, expected in test_cases:
    try:
        q = Query(query_str)
        result = q.evaluate(test_repo)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {query_str} -> {result}")
    except Exception as e:
        print(f"  ✗ {query_str} -> ERROR: {e}")

# Test 3: Fuzzy matching
print("\n3. Testing fuzzy matching (~=):")
test_cases = [
    ("language ~= 'Pyton'", True),   # Typo
    ("language ~= 'Pythoon'", True), # Typo
    ("language ~= 'Ruby'", False),   # Different language
]

for query_str, expected in test_cases:
    try:
        q = Query(query_str)
        result = q.evaluate(test_repo)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {query_str} -> {result}")
    except Exception as e:
        print(f"  ✗ {query_str} -> ERROR: {e}")

# Test 4: Null/None handling
print("\n4. Testing null/none value parsing:")
test_repo['description'] = None
test_cases = [
    ("description == null", True),
    ("description == none", True),
    ("description != null", False),
]

for query_str, expected in test_cases:
    try:
        q = Query(query_str)
        result = q.evaluate(test_repo)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {query_str} -> {result}")
    except Exception as e:
        print(f"  ✗ {query_str} -> ERROR: {e}")

# Test 5: Parentheses handling
print("\n5. Testing parentheses handling:")
test_cases = [
    ("(language == 'Python')", True),
    ("(stars > 40 and stars < 50)", True),
    ("(language == 'Python' or language == 'Ruby') and stars > 40", True),
]

for query_str, expected in test_cases:
    try:
        q = Query(query_str)
        result = q.evaluate(test_repo)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {query_str} -> {result}")
    except Exception as e:
        print(f"  ✗ {query_str} -> ERROR: {e}")

print("\n" + "=" * 60)
print("Test complete!")