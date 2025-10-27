"""
Event detection for repositories.

Detects events like:
- New git tags
- GitHub releases
- Star milestones

Maintains state to track what's already been processed.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from .events import Event
from .utils import run_command

logger = logging.getLogger(__name__)


class EventDetector:
    """
    Detects events in repositories.

    Maintains state to avoid processing the same event twice.
    State is stored in ~/.ghops/event_state.json
    """

    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize event detector.

        Args:
            state_file: Path to state file (default: ~/.ghops/event_state.json)
        """
        if state_file is None:
            from .config import get_config_path
            config_dir = get_config_path().parent
            state_file = config_dir / 'event_state.json'

        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state file: {e}")

        return {
            'last_check': {},  # repo_path -> timestamp
            'processed_tags': {},  # repo_path -> [tag1, tag2, ...]
            'processed_releases': {},  # repo_path -> [release_id1, ...]
        }

    def _save_state(self):
        """Save state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def detect_git_tags(self, repo_path: str) -> List[Event]:
        """
        Detect new git tags in a repository.

        Args:
            repo_path: Path to git repository

        Returns:
            List of git_tag events for new tags
        """
        repo_path = str(Path(repo_path).resolve())
        events = []

        # Get processed tags for this repo
        processed_tags = self.state['processed_tags'].get(repo_path, [])

        # Get all tags with creation date
        cmd = '''git for-each-ref --sort=-creatordate \
                 --format='%(refname:short)|%(creatordate:iso8601)|%(objectname:short)' \
                 refs/tags'''

        output, returncode = run_command(cmd, cwd=repo_path, capture_output=True, check=False)

        if returncode != 0 or not output:
            logger.debug(f"No tags found in {repo_path}")
            return events

        # Get current branch
        branch_output, _ = run_command('git branch --show-current', cwd=repo_path, capture_output=True, check=False)
        current_branch = branch_output.strip() if branch_output else 'main'

        # Parse tags
        for line in output.split('\n'):
            if not line.strip() or '|' not in line:
                continue

            try:
                parts = line.split('|')
                if len(parts) < 3:
                    continue

                tag = parts[0].strip()
                date_str = parts[1].strip()
                commit_hash = parts[2].strip()

                # Skip if already processed
                if tag in processed_tags:
                    continue

                # Parse date
                try:
                    tag_date = datetime.fromisoformat(date_str.replace(' ', 'T'))
                except:
                    tag_date = datetime.now()

                # Create event
                event = Event(
                    id=f"git_tag_{repo_path}_{tag}".replace('/', '_'),
                    type='git_tag',
                    repo_path=repo_path,
                    timestamp=tag_date,
                    context={
                        'tag': tag,
                        'commit': commit_hash,
                        'branch': current_branch,
                        'repo_name': Path(repo_path).name
                    }
                )

                events.append(event)

                # Mark as processed
                processed_tags.append(tag)

            except Exception as e:
                logger.warning(f"Failed to parse tag line '{line}': {e}")
                continue

        # Update state
        if events:
            self.state['processed_tags'][repo_path] = processed_tags
            self.state['last_check'][repo_path] = datetime.now().isoformat()
            self._save_state()

            logger.info(f"Detected {len(events)} new git tag(s) in {repo_path}")

        return events

    def detect_releases(self, repo_path: str) -> List[Event]:
        """
        Detect GitHub releases (not yet implemented).

        Args:
            repo_path: Path to git repository

        Returns:
            List of release_published events
        """
        # TODO: Implement GitHub API integration to detect releases
        logger.debug("GitHub release detection not yet implemented")
        return []

    def detect_milestone_stars(self, repo_path: str, milestones: List[int] = None) -> List[Event]:
        """
        Detect when repository reaches star milestones (not yet implemented).

        Args:
            repo_path: Path to git repository
            milestones: Star counts to watch for (e.g., [10, 50, 100, 500])

        Returns:
            List of milestone_stars events
        """
        # TODO: Implement GitHub API integration to check stars
        logger.debug("Star milestone detection not yet implemented")
        return []

    def detect_all(self, repo_path: str) -> List[Event]:
        """
        Detect all types of events in a repository.

        Args:
            repo_path: Path to git repository

        Returns:
            List of all detected events
        """
        events = []

        # Detect git tags
        events.extend(self.detect_git_tags(repo_path))

        # Detect releases (when implemented)
        events.extend(self.detect_releases(repo_path))

        # Detect milestone stars (when implemented)
        events.extend(self.detect_milestone_stars(repo_path))

        return events

    def reset_state(self, repo_path: Optional[str] = None):
        """
        Reset state for a repository or all repositories.

        Args:
            repo_path: Repository to reset (None = reset all)
        """
        if repo_path:
            repo_path = str(Path(repo_path).resolve())
            if repo_path in self.state['processed_tags']:
                del self.state['processed_tags'][repo_path]
            if repo_path in self.state['processed_releases']:
                del self.state['processed_releases'][repo_path]
            if repo_path in self.state['last_check']:
                del self.state['last_check'][repo_path]
            logger.info(f"Reset event state for {repo_path}")
        else:
            self.state = {
                'last_check': {},
                'processed_tags': {},
                'processed_releases': {}
            }
            logger.info("Reset event state for all repositories")

        self._save_state()


def get_event_detector() -> EventDetector:
    """Get singleton event detector instance."""
    global _event_detector
    if '_event_detector' not in globals():
        _event_detector = EventDetector()
    return _event_detector
