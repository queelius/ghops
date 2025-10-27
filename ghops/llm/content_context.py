"""
Content context builder for LLM content generation.

Extracts comprehensive information from repositories to provide
rich context for generating engaging blog posts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContentContext:
    """
    Rich context for LLM to generate interesting content.

    This class aggregates all information about a repository
    that would be useful for generating a blog post:
    - Project metadata
    - Version information
    - Git history
    - Features and capabilities
    - Getting started examples
    """

    # Project basics
    repo_name: str
    repo_path: str
    description: str
    language: str

    # Version info
    version: str
    previous_version: Optional[str] = None

    # What changed (from git)
    commits: List[Dict[str, str]] = field(default_factory=list)
    changelog: str = ""

    # Categorized changes (from conventional commits)
    new_features: List[str] = field(default_factory=list)
    bug_fixes: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)

    # Project capabilities (from README/docs)
    core_features: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)

    # Getting started
    installation_snippet: str = ""
    quick_example: str = ""

    # Metadata
    stars: int = 0
    topics: List[str] = field(default_factory=list)
    homepage_url: Optional[str] = None
    docs_url: Optional[str] = None

    # Links
    github_url: str = ""
    package_registry_url: Optional[str] = None


def build_content_context(repo_path: str, version: str) -> ContentContext:
    """
    Build comprehensive context from repository.

    Args:
        repo_path: Path to git repository
        version: Version for this post (e.g., "1.2.0")

    Returns:
        ContentContext with all extracted information
    """
    from ..metadata import get_metadata_store
    from ..utils import run_command

    repo_path = str(Path(repo_path).resolve())

    # Get cached metadata
    store = get_metadata_store()
    metadata = store.get(repo_path) or {}

    # Get git history
    prev_version = get_previous_version(repo_path, version)
    commits = get_commits_since(repo_path, prev_version)

    # Categorize commits
    categorized = categorize_commits(commits)

    # Extract from README
    readme_info = extract_readme_info(repo_path)

    # Build context
    return ContentContext(
        repo_name=Path(repo_path).name,
        repo_path=repo_path,
        description=metadata.get('description') or readme_info.get('description', ''),
        language=metadata.get('language', 'Unknown'),
        version=version,
        previous_version=prev_version,
        commits=commits,
        changelog=generate_changelog(commits, categorized),
        new_features=categorized['features'],
        bug_fixes=categorized['fixes'],
        breaking_changes=categorized['breaking'],
        core_features=readme_info.get('features', []),
        use_cases=readme_info.get('use_cases', []),
        installation_snippet=readme_info.get('installation', ''),
        quick_example=readme_info.get('quick_example', ''),
        stars=metadata.get('stargazers_count', 0),
        topics=metadata.get('topics', []),
        homepage_url=metadata.get('homepage'),
        docs_url=find_docs_url(repo_path, metadata),
        github_url=metadata.get('html_url', ''),
        package_registry_url=get_registry_url(repo_path, metadata)
    )


def get_previous_version(repo_path: str, current_version: str) -> Optional[str]:
    """Get the previous version tag."""
    from ..utils import run_command

    # Try to get all tags
    output, returncode = run_command(
        "git tag --sort=-version:refname",
        cwd=repo_path,
        capture_output=True,
        check=False
    )

    if returncode != 0 or not output:
        return None

    tags = [t.strip() for t in output.split('\n') if t.strip()]

    # Remove 'v' prefix if present
    current = current_version.lstrip('v')
    normalized_tags = [(t, t.lstrip('v')) for t in tags]

    # Find current version in tags
    for i, (tag, normalized) in enumerate(normalized_tags):
        if normalized == current:
            # Return previous tag if exists
            if i + 1 < len(normalized_tags):
                return normalized_tags[i + 1][1]  # Return normalized version
            break

    # If not found, return first tag or None
    return normalized_tags[0][1] if normalized_tags else None


def get_commits_since(repo_path: str, since_version: Optional[str]) -> List[Dict[str, str]]:
    """Get commits since a version."""
    from ..utils import run_command

    if since_version:
        # Get commits since tag
        cmd = f'git log v{since_version}..HEAD --pretty=format:"%H|||%s|||%an|||%ad" --date=short'
    else:
        # Get all commits (limited to last 50)
        cmd = 'git log --pretty=format:"%H|||%s|||%an|||%ad" --date=short -n 50'

    output, returncode = run_command(cmd, cwd=repo_path, capture_output=True, check=False)

    if returncode != 0 or not output:
        return []

    commits = []
    for line in output.split('\n'):
        if '|||' in line:
            parts = line.split('|||')
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'message': parts[1],
                    'author': parts[2],
                    'date': parts[3]
                })

    return commits


def categorize_commits(commits: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """
    Categorize commits using conventional commit format.

    Supports:
    - feat: / feat(scope): - New features
    - fix: / fix(scope): - Bug fixes
    - docs: - Documentation
    - BREAKING CHANGE - Breaking changes

    Returns:
        Dict with categories: features, fixes, breaking, docs, other
    """
    categories = {
        'features': [],
        'fixes': [],
        'breaking': [],
        'docs': [],
        'other': []
    }

    for commit in commits:
        msg = commit['message']

        # Check for breaking change
        if 'BREAKING CHANGE' in msg or msg.startswith('!:'):
            # Extract the description
            if 'BREAKING CHANGE:' in msg:
                desc = msg.split('BREAKING CHANGE:')[1].strip()
            else:
                desc = msg
            categories['breaking'].append(desc)

        # Check conventional commit prefixes
        if msg.startswith('feat:') or msg.startswith('feat('):
            desc = re.sub(r'^feat(\([^)]+\))?:\s*', '', msg)
            categories['features'].append(desc)
        elif msg.startswith('fix:') or msg.startswith('fix('):
            desc = re.sub(r'^fix(\([^)]+\))?:\s*', '', msg)
            categories['fixes'].append(desc)
        elif msg.startswith('docs:') or msg.startswith('docs('):
            desc = re.sub(r'^docs(\([^)]+\))?:\s*', '', msg)
            categories['docs'].append(desc)
        else:
            # Only add to 'other' if not already categorized
            if msg not in categories['breaking']:
                categories['other'].append(msg)

    return categories


def generate_changelog(commits: List[Dict[str, str]],
                       categorized: Dict[str, List[str]]) -> str:
    """Generate a formatted changelog from commits."""
    changelog_parts = []

    if categorized['breaking']:
        changelog_parts.append("### Breaking Changes\n")
        for change in categorized['breaking']:
            changelog_parts.append(f"- {change}")
        changelog_parts.append("")

    if categorized['features']:
        changelog_parts.append("### New Features\n")
        for feat in categorized['features']:
            changelog_parts.append(f"- {feat}")
        changelog_parts.append("")

    if categorized['fixes']:
        changelog_parts.append("### Bug Fixes\n")
        for fix in categorized['fixes']:
            changelog_parts.append(f"- {fix}")
        changelog_parts.append("")

    if categorized['docs']:
        changelog_parts.append("### Documentation\n")
        for doc in categorized['docs']:
            changelog_parts.append(f"- {doc}")
        changelog_parts.append("")

    if categorized['other']:
        changelog_parts.append("### Other Changes\n")
        for change in categorized['other'][:10]:  # Limit to 10
            changelog_parts.append(f"- {change}")
        if len(categorized['other']) > 10:
            changelog_parts.append(f"- ...and {len(categorized['other']) - 10} more")
        changelog_parts.append("")

    return '\n'.join(changelog_parts)


def extract_readme_info(repo_path: str) -> Dict[str, Any]:
    """
    Extract structured information from README.

    Looks for sections like:
    - ## Features
    - ## Installation
    - ## Quick Start
    - ## Usage
    """
    readme_path = find_readme(repo_path)
    if not readme_path:
        return {}

    try:
        content = readme_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Failed to read README: {e}")
        return {}

    return {
        'description': extract_description(content),
        'features': extract_section_list(content, 'Features'),
        'installation': extract_code_block(content, 'Installation'),
        'quick_example': extract_code_block(content, 'Quick Start', 'Usage', 'Example'),
        'use_cases': extract_section_list(content, 'Use Cases', 'When to Use')
    }


def find_readme(repo_path: str) -> Optional[Path]:
    """Find README file in repository."""
    repo = Path(repo_path)
    readme_names = ['README.md', 'README.rst', 'README.txt', 'README']

    for name in readme_names:
        readme = repo / name
        if readme.exists():
            return readme

    return None


def extract_description(content: str) -> str:
    """Extract project description from README (first paragraph)."""
    lines = content.split('\n')

    # Skip title (first # line)
    description_lines = []
    in_description = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines at start
        if not in_description and not stripped:
            continue

        # Skip title line
        if not in_description and stripped.startswith('#'):
            in_description = True
            continue

        # Collect description until next heading or empty line
        if in_description:
            if stripped.startswith('#'):
                break
            if stripped:
                description_lines.append(stripped)
            elif description_lines:  # Stop at empty line after content
                break

    return ' '.join(description_lines[:3])  # First 3 lines max


def extract_section_list(content: str, *section_names: str) -> List[str]:
    """Extract bullet list from a section."""
    for section_name in section_names:
        pattern = rf'##\s+{section_name}\s*\n(.*?)(?:\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            section_content = match.group(1)
            items = []

            for line in section_content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('- ') or stripped.startswith('* '):
                    item = stripped[2:].strip()
                    # Remove markdown links
                    item = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', item)
                    items.append(item)

            return items[:10]  # Max 10 items

    return []


def extract_code_block(content: str, *section_names: str) -> str:
    """Extract first code block from a section."""
    for section_name in section_names:
        pattern = rf'##\s+{section_name}\s*\n(.*?)(?:\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            section_content = match.group(1)
            # Find first code block
            code_pattern = r'```[\w]*\n(.*?)\n```'
            code_match = re.search(code_pattern, section_content, re.DOTALL)

            if code_match:
                return code_match.group(1).strip()

    return ""


def find_docs_url(repo_path: str, metadata: Dict[str, Any]) -> Optional[str]:
    """Find documentation URL."""
    # Check metadata first
    if metadata.get('homepage') and ('doc' in metadata['homepage'].lower() or 'readthedocs' in metadata['homepage']):
        return metadata['homepage']

    # Check for common doc URLs
    repo_name = Path(repo_path).name
    owner = metadata.get('owner', '')

    if owner:
        # Try GitHub Pages
        return f"https://{owner}.github.io/{repo_name}"

    return None


def get_registry_url(repo_path: str, metadata: Dict[str, Any]) -> Optional[str]:
    """Get package registry URL (PyPI, npm, etc.)."""
    from ..commands.publish import ProjectDetector

    project_types = ProjectDetector.detect(repo_path)

    for ptype in project_types:
        if ptype == 'python':
            # Try to get package name from pyproject.toml
            pyproject = Path(repo_path) / 'pyproject.toml'
            if pyproject.exists():
                try:
                    import toml
                    data = toml.load(pyproject)
                    name = data.get('project', {}).get('name') or data.get('tool', {}).get('poetry', {}).get('name')
                    if name:
                        return f"https://pypi.org/project/{name}/"
                except:
                    pass

        elif ptype == 'node':
            # npm package
            package_json = Path(repo_path) / 'package.json'
            if package_json.exists():
                try:
                    import json
                    data = json.loads(package_json.read_text())
                    name = data.get('name')
                    if name:
                        return f"https://www.npmjs.com/package/{name}"
                except:
                    pass

        elif ptype == 'rust':
            # crates.io
            cargo_toml = Path(repo_path) / 'Cargo.toml'
            if cargo_toml.exists():
                try:
                    import toml
                    data = toml.load(cargo_toml)
                    name = data.get('package', {}).get('name')
                    if name:
                        return f"https://crates.io/crates/{name}"
                except:
                    pass

    return None
