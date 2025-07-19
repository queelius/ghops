"""
Metadata store for ghops repositories.

Provides a single source of truth for repository metadata,
replacing the distributed caching system with a unified store.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterator
from datetime import datetime
import logging

from .config import get_config_path
from .utils import get_remote_url, parse_repo_url, run_command

logger = logging.getLogger(__name__)


def run_git_command(repo_path: str, args: List[str]) -> Optional[str]:
    """Run a git command in a repository."""
    import subprocess
    try:
        result = subprocess.run(['git'] + args, 
                              cwd=repo_path, 
                              capture_output=True, 
                              text=True,
                              check=True)
        return result.stdout.strip() if result.stdout else None
    except Exception:
        return None


class MetadataStore:
    """Local metadata store for repository information."""
    
    def __init__(self, store_path: Optional[Path] = None):
        """Initialize the metadata store.
        
        Args:
            store_path: Path to the metadata JSON file. 
                       Defaults to ~/.ghops/metadata.json
        """
        if store_path is None:
            config_path = Path(get_config_path())
            config_dir = config_path.parent
            store_path = config_dir / "metadata.json"
        
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing metadata
        self._metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from disk."""
        if self.store_path.exists():
            try:
                with open(self.store_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            with open(self.store_path, 'w') as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def get(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a repository.
        
        Args:
            repo_path: Absolute path to the repository
            
        Returns:
            Repository metadata or None if not found
        """
        return self._metadata.get(repo_path)
    
    def update(self, repo_path: str, metadata: Dict[str, Any], 
               merge: bool = True) -> Dict[str, Any]:
        """Update metadata for a repository.
        
        Args:
            repo_path: Absolute path to the repository
            metadata: Metadata to store
            merge: If True, merge with existing metadata
            
        Returns:
            Updated metadata
        """
        if merge and repo_path in self._metadata:
            # Merge with existing
            existing = self._metadata[repo_path]
            existing.update(metadata)
            metadata = existing
        
        # Add timestamp
        metadata['_updated'] = datetime.utcnow().isoformat()
        
        self._metadata[repo_path] = metadata
        self._save_metadata()
        return metadata
    
    def delete(self, repo_path: str) -> bool:
        """Delete metadata for a repository.
        
        Args:
            repo_path: Absolute path to the repository
            
        Returns:
            True if deleted, False if not found
        """
        if repo_path in self._metadata:
            del self._metadata[repo_path]
            self._save_metadata()
            return True
        return False
    
    def refresh(self, repo_path: str, fetch_github: bool = False) -> Dict[str, Any]:
        """Refresh metadata for a repository.
        
        This fetches fresh data from git, filesystem, and optionally GitHub API.
        
        Args:
            repo_path: Absolute path to the repository
            fetch_github: If True, fetch data from GitHub API
            
        Returns:
            Updated metadata
        """
        logger.debug(f"Refreshing metadata for {repo_path}")
        
        # Get basic repository info
        metadata = {
            'path': repo_path,
            'name': os.path.basename(repo_path)
        }
        
        # Get git info
        try:
            # Get current branch
            branch = run_git_command(repo_path, ['branch', '--show-current'])
            if branch:
                metadata['branch'] = branch.strip()
            
            # Get remote URL
            remote_url = get_remote_url(repo_path)
            if remote_url:
                metadata['remote_url'] = remote_url
                owner, repo = parse_repo_url(remote_url)
                if owner:
                    metadata['owner'] = owner
                if repo:
                    metadata['repo'] = repo
                
                # Determine provider
                if 'github.com' in remote_url:
                    metadata['provider'] = 'github'
                elif 'gitlab.com' in remote_url:
                    metadata['provider'] = 'gitlab'
                elif 'bitbucket.org' in remote_url:
                    metadata['provider'] = 'bitbucket'
            
            # Get last commit info
            commit_info = run_git_command(repo_path, 
                ['log', '-1', '--format=%H|%an|%ae|%at|%s'])
            if commit_info:
                parts = commit_info.strip().split('|')
                if len(parts) >= 5:
                    metadata['last_commit'] = {
                        'hash': parts[0],
                        'author': parts[1],
                        'email': parts[2],
                        'timestamp': int(parts[3]),
                        'message': parts[4]
                    }
            
            # Check if there are uncommitted changes
            status = run_git_command(repo_path, ['status', '--porcelain'])
            metadata['has_uncommitted_changes'] = bool(status and status.strip())
            
        except Exception as e:
            logger.warning(f"Failed to get git info for {repo_path}: {e}")
        
        # Get language info (simplified for now)
        # TODO: Implement proper language detection using linguist or similar
        # For now, just try to detect from common file extensions
        try:
            languages = {}
            lang_extensions = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.go': 'Go',
                '.rs': 'Rust',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.rb': 'Ruby',
                '.php': 'PHP',
                '.cs': 'C#',
                '.swift': 'Swift',
                '.kt': 'Kotlin',
                '.scala': 'Scala',
                '.r': 'R',
                '.jl': 'Julia',
                '.sh': 'Shell',
                '.ps1': 'PowerShell'
            }
            
            for root, dirs, files in os.walk(repo_path):
                if '.git' in root:
                    continue
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in lang_extensions:
                        lang = lang_extensions[ext]
                        languages[lang] = languages.get(lang, 0) + 1
            
            if languages:
                metadata['languages'] = languages
                # Primary language is the one with most files
                primary = max(languages.items(), key=lambda x: x[1])
                metadata['language'] = primary[0]
        except Exception as e:
            logger.warning(f"Failed to get language info for {repo_path}: {e}")
        
        # Get documentation info
        try:
            # Import here to avoid circular dependency
            from .commands.docs import detect_docs_tool
            docs_info = detect_docs_tool(repo_path)
            if docs_info:
                metadata['has_docs'] = True
                metadata['docs_tool'] = docs_info['tool']
                metadata['docs_config'] = docs_info.get('config')
            else:
                metadata['has_docs'] = False
        except Exception as e:
            logger.warning(f"Failed to detect docs for {repo_path}: {e}")
        
        # Get file stats
        try:
            # Count files
            file_count = 0
            total_size = 0
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory
                if '.git' in root:
                    continue
                file_count += len(files)
                for f in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except:
                        pass
            
            metadata['file_count'] = file_count
            metadata['total_size'] = total_size
        except Exception as e:
            logger.warning(f"Failed to get file stats for {repo_path}: {e}")
        
        # Fetch GitHub-specific data if requested
        if fetch_github and metadata.get('provider') == 'github':
            owner = metadata.get('owner')
            repo = metadata.get('repo')
            if owner and repo:
                try:
                    # Make direct API call
                    import requests
                    
                    # Check for GitHub token in config
                    from .config import load_config
                    config = load_config()
                    github_token = config.get('github', {}).get('token')
                    
                    headers = {'Accept': 'application/vnd.github.v3+json'}
                    if github_token:
                        headers['Authorization'] = f'token {github_token}'
                    
                    url = f'https://api.github.com/repos/{owner}/{repo}'
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    # Check for rate limiting
                    if response.status_code == 403:
                        remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                        reset_time_str = response.headers.get('X-RateLimit-Reset', 'unknown')
                        logger.warning(f"GitHub API rate limit hit. Remaining: {remaining}, Reset: {reset_time_str}")
                        
                        # Check if it's rate limit or other 403
                        if 'rate limit' in response.text.lower():
                            # Include reset time in the exception for the retry logic
                            raise Exception(f"GitHub API rate limit exceeded. Reset at {reset_time_str}|RESET_TIME:{reset_time_str}")
                    
                    if response.status_code == 200:
                        github_data = response.json()
                        # Extract relevant fields
                        metadata['description'] = github_data.get('description')
                        metadata['stargazers_count'] = github_data.get('stargazers_count', 0)
                        metadata['forks_count'] = github_data.get('forks_count', 0)
                        metadata['open_issues_count'] = github_data.get('open_issues_count', 0)
                        metadata['topics'] = github_data.get('topics', [])
                        metadata['archived'] = github_data.get('archived', False)
                        metadata['disabled'] = github_data.get('disabled', False)
                        metadata['private'] = github_data.get('private', False)
                        metadata['fork'] = github_data.get('fork', False)
                        metadata['created_at'] = github_data.get('created_at')
                        metadata['updated_at'] = github_data.get('updated_at')
                        metadata['pushed_at'] = github_data.get('pushed_at')
                        metadata['homepage'] = github_data.get('homepage')
                        metadata['has_issues'] = github_data.get('has_issues', False)
                        metadata['has_projects'] = github_data.get('has_projects', False)
                        metadata['has_downloads'] = github_data.get('has_downloads', False)
                        metadata['has_wiki'] = github_data.get('has_wiki', False)
                        metadata['has_pages'] = github_data.get('has_pages', False)
                        
                        # License info
                        if github_data.get('license'):
                            metadata['license'] = {
                                'key': github_data['license'].get('key'),
                                'name': github_data['license'].get('name'),
                                'spdx_id': github_data['license'].get('spdx_id')
                            }
                except Exception as e:
                    logger.warning(f"Failed to fetch GitHub data for {owner}/{repo}: {e}")
        
        # Update the store
        self.update(repo_path, metadata, merge=False)
        return metadata
    
    def refresh_all(self, repo_paths: List[str], fetch_github: bool = False,
                   progress_callback=None) -> Iterator[Dict[str, Any]]:
        """Refresh metadata for multiple repositories.
        
        Args:
            repo_paths: List of repository paths
            fetch_github: If True, fetch data from GitHub API
            progress_callback: Optional callback(current, total) for progress
            
        Yields:
            Updated metadata for each repository
        """
        import time
        
        # Get config for rate limiting
        from .config import load_config
        config = load_config()
        rate_limit_config = config.get('github', {}).get('rate_limit', {})
        max_retries = rate_limit_config.get('max_retries', 3)
        max_retry_delay = rate_limit_config.get('max_delay_seconds', 60)
        respect_reset_time = rate_limit_config.get('respect_reset_time', True)
        
        total = len(repo_paths)
        retry_delay = 1  # Start with 1 second
        
        for i, repo_path in enumerate(repo_paths):
            if progress_callback:
                progress_callback(i + 1, total)
            
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    metadata = self.refresh(repo_path, fetch_github)
                    yield metadata
                    # Reset delay on success
                    retry_delay = 1
                    break
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check if it's a rate limit error
                    if 'rate limit' in error_msg.lower():
                        retry_count += 1
                        if retry_count < max_retries:
                            # Check if we have GitHub's reset time
                            wait_time = retry_delay
                            
                            if respect_reset_time and 'RESET_TIME:' in error_msg:
                                try:
                                    # Extract reset time from error message
                                    reset_time_str = error_msg.split('RESET_TIME:')[1].strip()
                                    reset_timestamp = int(reset_time_str)
                                    current_time = int(time.time())
                                    github_wait_time = reset_timestamp - current_time + 1  # Add 1 second buffer
                                    
                                    if github_wait_time > 0:
                                        wait_time = min(github_wait_time, max_retry_delay)
                                        logger.info(f"Using GitHub's rate limit reset time: waiting {wait_time}s")
                                except (ValueError, IndexError):
                                    # Fall back to exponential backoff if parsing fails
                                    wait_time = min(retry_delay, max_retry_delay)
                            else:
                                wait_time = min(retry_delay, max_retry_delay)
                            
                            logger.warning(f"Rate limited. Waiting {wait_time}s before retry {retry_count}/{max_retries}")
                            time.sleep(wait_time)
                            retry_delay *= 2  # Exponential backoff for next retry
                        else:
                            logger.error(f"Max retries exceeded for {repo_path}")
                            yield {
                                'path': repo_path,
                                'error': f"Rate limited after {max_retries} retries",
                                '_updated': datetime.utcnow().isoformat()
                            }
                    else:
                        # Non-rate limit error, don't retry
                        logger.error(f"Failed to refresh {repo_path}: {e}")
                        yield {
                            'path': repo_path,
                            'error': error_msg,
                            '_updated': datetime.utcnow().isoformat()
                        }
                        break
    
    def search(self, query_func) -> Iterator[Dict[str, Any]]:
        """Search repositories using a query function.
        
        Args:
            query_func: Function that takes metadata dict and returns bool
            
        Yields:
            Metadata for matching repositories
        """
        for repo_path, metadata in self._metadata.items():
            if query_func(metadata):
                yield metadata
    
    def clear(self):
        """Clear all metadata."""
        self._metadata = {}
        self._save_metadata()
    
    def stats(self) -> Dict[str, Any]:
        """Get statistics about the metadata store."""
        total_repos = len(self._metadata)
        
        # Calculate various stats
        providers = {}
        languages = {}
        total_stars = 0
        total_forks = 0
        
        for metadata in self._metadata.values():
            # Provider stats
            provider = metadata.get('provider', 'unknown')
            providers[provider] = providers.get(provider, 0) + 1
            
            # Language stats
            language = metadata.get('language')
            if language:
                languages[language] = languages.get(language, 0) + 1
            
            # GitHub stats
            total_stars += metadata.get('stargazers_count', 0)
            total_forks += metadata.get('forks_count', 0)
        
        return {
            'total_repositories': total_repos,
            'providers': providers,
            'languages': languages,
            'total_stars': total_stars,
            'total_forks': total_forks,
            'store_size': os.path.getsize(self.store_path) if self.store_path.exists() else 0
        }


# Global instance
_store = None

def get_metadata_store() -> MetadataStore:
    """Get the global metadata store instance."""
    global _store
    if _store is None:
        _store = MetadataStore()
    return _store