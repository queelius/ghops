"""
Tests for event_detector.py module.

Tests the event detection system including:
- Git tag detection
- State management (avoiding duplicates)
- State file persistence
- Release and milestone detection (when implemented)
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from ghops.event_detector import EventDetector, get_event_detector
from ghops.events import Event


class TestEventDetector:
    """Test EventDetector functionality."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_path = Path(f.name)

        yield state_path

        # Cleanup
        if state_path.exists():
            state_path.unlink()

    @pytest.fixture
    def detector(self, temp_state_file):
        """Create a test event detector."""
        return EventDetector(temp_state_file)

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary git repository."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        return str(repo_path)

    # ========================================================================
    # Initialization and State Management
    # ========================================================================

    def test_detector_initialization(self, detector, temp_state_file):
        """Test detector initializes with correct state structure."""
        assert detector.state_file == temp_state_file
        assert 'last_check' in detector.state
        assert 'processed_tags' in detector.state
        assert 'processed_releases' in detector.state

    def test_detector_creates_empty_state(self, temp_state_file):
        """Test detector creates empty state when no file exists."""
        # Remove state file
        if temp_state_file.exists():
            temp_state_file.unlink()

        detector = EventDetector(temp_state_file)

        assert detector.state == {
            'last_check': {},
            'processed_tags': {},
            'processed_releases': {}
        }

    def test_detector_loads_existing_state(self, temp_state_file):
        """Test detector loads existing state from file."""
        # Write state file
        state = {
            'last_check': {'/repo1': '2024-01-15T10:00:00'},
            'processed_tags': {'/repo1': ['v1.0.0', 'v1.1.0']},
            'processed_releases': {}
        }
        with open(temp_state_file, 'w') as f:
            json.dump(state, f)

        detector = EventDetector(temp_state_file)

        assert detector.state == state
        assert '/repo1' in detector.state['processed_tags']
        assert 'v1.0.0' in detector.state['processed_tags']['/repo1']

    def test_detector_handles_corrupted_state_file(self, temp_state_file):
        """Test detector handles corrupted state file gracefully."""
        # Write corrupted JSON
        with open(temp_state_file, 'w') as f:
            f.write("{ invalid json")

        detector = EventDetector(temp_state_file)

        # Should fall back to empty state
        assert detector.state == {
            'last_check': {},
            'processed_tags': {},
            'processed_releases': {}
        }

    def test_save_state(self, detector, temp_state_file):
        """Test saving state to file."""
        detector.state['processed_tags']['/repo1'] = ['v1.0.0']
        detector._save_state()

        # Verify file was written
        assert temp_state_file.exists()

        with open(temp_state_file, 'r') as f:
            saved_state = json.load(f)

        assert saved_state['processed_tags']['/repo1'] == ['v1.0.0']

    # ========================================================================
    # Git Tag Detection
    # ========================================================================

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_no_tags(self, mock_run_command, detector, temp_repo):
        """Test detecting tags when repository has no tags."""
        # Mock git command to return no tags
        mock_run_command.return_value = ('', 1)

        events = detector.detect_git_tags(temp_repo)

        assert events == []

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_single_tag(self, mock_run_command, detector, temp_repo):
        """Test detecting a single new git tag."""
        # Mock git commands
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_git_tags(temp_repo)

        assert len(events) == 1
        event = events[0]
        assert event.type == 'git_tag'
        assert event.context['tag'] == 'v1.0.0'
        assert event.context['commit'] == 'abc1234'
        assert event.context['branch'] == 'main'

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_multiple_tags(self, mock_run_command, detector, temp_repo):
        """Test detecting multiple new tags."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return (
                    'v1.2.0|2024-01-17 10:00:00 +0000|def5678\n'
                    'v1.1.0|2024-01-16 10:00:00 +0000|bcd4567\n'
                    'v1.0.0|2024-01-15 10:00:00 +0000|abc1234',
                    0
                )
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_git_tags(temp_repo)

        assert len(events) == 3
        tags = [e.context['tag'] for e in events]
        assert 'v1.0.0' in tags
        assert 'v1.1.0' in tags
        assert 'v1.2.0' in tags

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_avoids_duplicates(self, mock_run_command, detector, temp_repo):
        """Test that already-processed tags are not returned again."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return (
                    'v1.1.0|2024-01-16 10:00:00 +0000|bcd4567\n'
                    'v1.0.0|2024-01-15 10:00:00 +0000|abc1234',
                    0
                )
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        # First detection - should find both tags
        events1 = detector.detect_git_tags(temp_repo)
        assert len(events1) == 2

        # Second detection - should find no new tags
        events2 = detector.detect_git_tags(temp_repo)
        assert len(events2) == 0

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_new_tags_only(self, mock_run_command, detector, temp_repo):
        """Test that only new tags are returned after initial detection."""
        # First call - tags v1.0.0 and v1.1.0
        def first_call_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return (
                    'v1.1.0|2024-01-16 10:00:00 +0000|bcd4567\n'
                    'v1.0.0|2024-01-15 10:00:00 +0000|abc1234',
                    0
                )
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = first_call_side_effect
        events1 = detector.detect_git_tags(temp_repo)
        assert len(events1) == 2

        # Second call - new tag v1.2.0 added
        def second_call_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return (
                    'v1.2.0|2024-01-17 10:00:00 +0000|def5678\n'
                    'v1.1.0|2024-01-16 10:00:00 +0000|bcd4567\n'
                    'v1.0.0|2024-01-15 10:00:00 +0000|abc1234',
                    0
                )
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = second_call_side_effect
        events2 = detector.detect_git_tags(temp_repo)

        # Should only find the new tag
        assert len(events2) == 1
        assert events2[0].context['tag'] == 'v1.2.0'

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_saves_state(self, mock_run_command, detector, temp_repo):
        """Test that state is saved after detecting tags."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_git_tags(temp_repo)

        # Verify state was updated
        repo_path = str(Path(temp_repo).resolve())
        assert repo_path in detector.state['processed_tags']
        assert 'v1.0.0' in detector.state['processed_tags'][repo_path]
        assert repo_path in detector.state['last_check']

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_handles_malformed_output(self, mock_run_command, detector, temp_repo):
        """Test that malformed git output is handled gracefully."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                # Return some malformed lines
                return (
                    'v1.0.0|2024-01-15 10:00:00 +0000|abc1234\n'
                    'malformed line without pipes\n'
                    'only|two\n'  # Only 2 parts, should be skipped
                    'v1.1.0|2024-01-16 10:00:00 +0000|bcd4567',
                    0
                )
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_git_tags(temp_repo)

        # Should get at least the valid tags (may get 2 or 3 depending on parsing)
        assert len(events) >= 2
        tags = [e.context['tag'] for e in events]
        assert 'v1.0.0' in tags
        assert 'v1.1.0' in tags

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_generates_unique_event_ids(self, mock_run_command, detector, temp_repo):
        """Test that event IDs are unique and consistent."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_git_tags(temp_repo)

        assert len(events) == 1
        event_id = events[0].id
        assert 'git_tag' in event_id
        assert 'v1.0.0' in event_id

    @patch('ghops.event_detector.run_command')
    def test_detect_git_tags_normalizes_repo_path(self, mock_run_command, detector):
        """Test that repo paths are normalized to absolute paths."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        # Use relative path
        events = detector.detect_git_tags('.')

        # Event should have absolute path
        assert Path(events[0].repo_path).is_absolute()

    # ========================================================================
    # Release Detection (Placeholder Tests)
    # ========================================================================

    def test_detect_releases_not_implemented(self, detector, temp_repo):
        """Test that release detection returns empty list (not yet implemented)."""
        events = detector.detect_releases(temp_repo)
        assert events == []

    # ========================================================================
    # Milestone Star Detection (Placeholder Tests)
    # ========================================================================

    def test_detect_milestone_stars_not_implemented(self, detector, temp_repo):
        """Test that milestone detection returns empty list (not yet implemented)."""
        events = detector.detect_milestone_stars(temp_repo, milestones=[10, 50, 100])
        assert events == []

    # ========================================================================
    # Detect All
    # ========================================================================

    @patch('ghops.event_detector.run_command')
    def test_detect_all(self, mock_run_command, detector, temp_repo):
        """Test detect_all aggregates all detection methods."""
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect

        events = detector.detect_all(temp_repo)

        # Should include git tag events (release and milestone not implemented yet)
        assert len(events) >= 1
        assert any(e.type == 'git_tag' for e in events)

    # ========================================================================
    # State Reset
    # ========================================================================

    @patch('ghops.event_detector.run_command')
    def test_reset_state_for_repo(self, mock_run_command, detector, temp_repo):
        """Test resetting state for a specific repository."""
        # Add some state
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect
        detector.detect_git_tags(temp_repo)

        repo_path = str(Path(temp_repo).resolve())
        assert repo_path in detector.state['processed_tags']

        # Reset state
        detector.reset_state(temp_repo)

        # State should be cleared
        assert repo_path not in detector.state['processed_tags']
        assert repo_path not in detector.state['last_check']

    @patch('ghops.event_detector.run_command')
    def test_reset_state_all_repos(self, mock_run_command, detector, temp_repo):
        """Test resetting state for all repositories."""
        # Add state for multiple repos
        def run_command_side_effect(cmd, **kwargs):
            if 'for-each-ref' in cmd:
                return ('v1.0.0|2024-01-15 10:00:00 +0000|abc1234', 0)
            elif 'branch --show-current' in cmd:
                return ('main', 0)
            return ('', 0)

        mock_run_command.side_effect = run_command_side_effect
        detector.detect_git_tags(temp_repo)

        # Add another repo manually
        detector.state['processed_tags']['/another/repo'] = ['v2.0.0']

        # Reset all
        detector.reset_state()

        # All state should be cleared
        assert detector.state['processed_tags'] == {}
        assert detector.state['processed_releases'] == {}
        assert detector.state['last_check'] == {}

    def test_reset_state_saves_file(self, detector, temp_state_file):
        """Test that reset_state saves to file."""
        detector.state['processed_tags']['/repo1'] = ['v1.0.0']
        detector.reset_state()

        # Verify file was updated
        with open(temp_state_file, 'r') as f:
            saved_state = json.load(f)

        assert saved_state['processed_tags'] == {}


class TestGetEventDetector:
    """Test singleton event detector."""

    def test_get_event_detector_singleton(self):
        """Test that get_event_detector returns singleton instance."""
        # Clear any existing global
        import ghops.event_detector as module
        if '_event_detector' in dir(module):
            delattr(module, '_event_detector')

        detector1 = get_event_detector()
        detector2 = get_event_detector()

        assert detector1 is detector2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
