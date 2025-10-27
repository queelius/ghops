"""
Repository snapshot and restoration management.
"""

import json
import logging
import subprocess
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
import os

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages repository snapshots for time travel capabilities."""

    def __init__(self, repo_path: str, snapshot_dir: Optional[str] = None):
        """Initialize snapshot manager.

        Args:
            repo_path: Path to the repository.
            snapshot_dir: Directory to store snapshots (default: ~/.ghops/snapshots).
        """
        self.repo_path = Path(repo_path)
        self.repo_name = self.repo_path.name

        if snapshot_dir:
            self.snapshot_dir = Path(snapshot_dir)
        else:
            self.snapshot_dir = Path.home() / '.ghops' / 'snapshots'

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.snapshot_dir / f'{self.repo_name}_metadata.json'

    def create_snapshot(self, tag: Optional[str] = None, description: str = '') -> Dict[str, Any]:
        """Create a snapshot of the current repository state.

        Args:
            tag: Optional tag for the snapshot.
            description: Description of the snapshot.

        Returns:
            Snapshot metadata.
        """
        # Generate snapshot ID
        timestamp = datetime.now()
        snapshot_id = f"{self.repo_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        if tag:
            snapshot_id = f"{snapshot_id}_{tag}"

        # Get current repository state
        repo_state = self._capture_repo_state()

        # Create snapshot archive
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.tar.gz"
        self._create_archive(snapshot_path)

        # Calculate snapshot hash
        with open(snapshot_path, 'rb') as f:
            snapshot_hash = hashlib.sha256(f.read()).hexdigest()

        # Create metadata
        metadata = {
            'id': snapshot_id,
            'repository': str(self.repo_path),
            'timestamp': timestamp.isoformat(),
            'tag': tag,
            'description': description,
            'hash': snapshot_hash,
            'size': snapshot_path.stat().st_size,
            'state': repo_state,
            'file_path': str(snapshot_path),
        }

        # Save metadata
        self._save_metadata(metadata)

        logger.info(f"Created snapshot: {snapshot_id}")
        return metadata

    def _capture_repo_state(self) -> Dict[str, Any]:
        """Capture current repository state information.

        Returns:
            Repository state dictionary.
        """
        state = {}

        # Get current branch
        result = subprocess.run(
            ['git', '-C', str(self.repo_path), 'branch', '--show-current'],
            capture_output=True,
            text=True
        )
        state['branch'] = result.stdout.strip()

        # Get current commit
        result = subprocess.run(
            ['git', '-C', str(self.repo_path), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True
        )
        state['commit'] = result.stdout.strip()

        # Get status
        result = subprocess.run(
            ['git', '-C', str(self.repo_path), 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
        state['uncommitted_changes'] = len(result.stdout.strip()) > 0

        # Get file count
        files = list(self.repo_path.rglob('*'))
        state['file_count'] = len([f for f in files if f.is_file()])

        # Get repository size
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        state['total_size'] = total_size

        # Get remote URLs
        result = subprocess.run(
            ['git', '-C', str(self.repo_path), 'remote', '-v'],
            capture_output=True,
            text=True
        )
        remotes = {}
        for line in result.stdout.split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    name = parts[0]
                    url = parts[1].split()[0]
                    remotes[name] = url
        state['remotes'] = remotes

        # Get tag list
        result = subprocess.run(
            ['git', '-C', str(self.repo_path), 'tag', '-l'],
            capture_output=True,
            text=True
        )
        state['tags'] = result.stdout.strip().split('\n') if result.stdout.strip() else []

        return state

    def _create_archive(self, output_path: Path):
        """Create compressed archive of repository.

        Args:
            output_path: Path for the output archive.
        """
        with tarfile.open(output_path, 'w:gz') as tar:
            # Add all files except .git internals
            for item in self.repo_path.iterdir():
                if item.name != '.git' or self._should_include_git_file(item):
                    tar.add(item, arcname=item.name)

            # Include essential .git files
            git_dir = self.repo_path / '.git'
            if git_dir.exists():
                essential_git = ['config', 'HEAD', 'packed-refs']
                for file_name in essential_git:
                    file_path = git_dir / file_name
                    if file_path.exists():
                        tar.add(file_path, arcname=f'.git/{file_name}')

    def _should_include_git_file(self, path: Path) -> bool:
        """Determine if a .git file should be included in snapshot."""
        # Include essential git files but skip large/temporary ones
        exclude_patterns = ['objects/', 'logs/', 'COMMIT_EDITMSG', 'index.lock']
        path_str = str(path)
        return not any(pattern in path_str for pattern in exclude_patterns)

    def list_snapshots(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available snapshots.

        Args:
            tag: Filter by tag.

        Returns:
            List of snapshot metadata.
        """
        metadata = self._load_all_metadata()

        if tag:
            metadata = [m for m in metadata if m.get('tag') == tag]

        # Sort by timestamp
        metadata.sort(key=lambda x: x['timestamp'], reverse=True)

        return metadata

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Get snapshot metadata by ID.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Snapshot metadata or None if not found.
        """
        metadata = self._load_all_metadata()

        for snapshot in metadata:
            if snapshot['id'] == snapshot_id:
                return snapshot

        return None

    def restore_snapshot(self, snapshot_id: str, target_path: Optional[str] = None,
                        create_branch: bool = True) -> Dict[str, Any]:
        """Restore a snapshot to a directory.

        Args:
            snapshot_id: Snapshot to restore.
            target_path: Target directory (default: create new directory).
            create_branch: Create a new branch for the restored state.

        Returns:
            Restoration result.
        """
        # Get snapshot metadata
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        # Determine target path
        if target_path:
            target = Path(target_path)
        else:
            target = Path(tempfile.mkdtemp(prefix=f"{self.repo_name}_restore_"))

        target.mkdir(parents=True, exist_ok=True)

        # Extract snapshot
        snapshot_path = Path(snapshot['file_path'])
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")

        with tarfile.open(snapshot_path, 'r:gz') as tar:
            tar.extractall(target)

        # Initialize git if needed
        if not (target / '.git').exists():
            subprocess.run(['git', 'init'], cwd=target)

        # Create restoration branch
        if create_branch:
            branch_name = f"restore/{snapshot_id}"
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=target,
                capture_output=True
            )

            # Commit restored state
            subprocess.run(['git', 'add', '-A'], cwd=target)
            subprocess.run(
                ['git', 'commit', '-m', f"Restored from snapshot: {snapshot_id}"],
                cwd=target,
                capture_output=True
            )

        result = {
            'snapshot_id': snapshot_id,
            'target_path': str(target),
            'timestamp': datetime.now().isoformat(),
            'branch': branch_name if create_branch else None,
            'original_state': snapshot['state'],
        }

        logger.info(f"Restored snapshot {snapshot_id} to {target}")
        return result

    def compare_snapshots(self, snapshot1_id: str, snapshot2_id: str) -> Dict[str, Any]:
        """Compare two snapshots.

        Args:
            snapshot1_id: First snapshot ID.
            snapshot2_id: Second snapshot ID.

        Returns:
            Comparison results.
        """
        snap1 = self.get_snapshot(snapshot1_id)
        snap2 = self.get_snapshot(snapshot2_id)

        if not snap1 or not snap2:
            raise ValueError("One or both snapshots not found")

        # Extract snapshots to temporary directories
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / 'snap1'
            dir2 = Path(tmpdir) / 'snap2'

            # Extract both snapshots
            with tarfile.open(snap1['file_path'], 'r:gz') as tar:
                tar.extractall(dir1)
            with tarfile.open(snap2['file_path'], 'r:gz') as tar:
                tar.extractall(dir2)

            # Compare file lists
            files1 = set(f.relative_to(dir1) for f in dir1.rglob('*') if f.is_file())
            files2 = set(f.relative_to(dir2) for f in dir2.rglob('*') if f.is_file())

            added_files = files2 - files1
            removed_files = files1 - files2
            common_files = files1 & files2

            # Compare common files for modifications
            modified_files = []
            for file_path in common_files:
                file1 = dir1 / file_path
                file2 = dir2 / file_path

                if file1.stat().st_size != file2.stat().st_size:
                    modified_files.append(str(file_path))
                else:
                    # Compare content hash
                    with open(file1, 'rb') as f:
                        hash1 = hashlib.md5(f.read()).hexdigest()
                    with open(file2, 'rb') as f:
                        hash2 = hashlib.md5(f.read()).hexdigest()

                    if hash1 != hash2:
                        modified_files.append(str(file_path))

        return {
            'snapshot1': {
                'id': snap1['id'],
                'timestamp': snap1['timestamp'],
            },
            'snapshot2': {
                'id': snap2['id'],
                'timestamp': snap2['timestamp'],
            },
            'time_diff_days': (
                datetime.fromisoformat(snap2['timestamp']) -
                datetime.fromisoformat(snap1['timestamp'])
            ).days,
            'added_files': list(added_files),
            'removed_files': list(removed_files),
            'modified_files': modified_files,
            'added_count': len(added_files),
            'removed_count': len(removed_files),
            'modified_count': len(modified_files),
        }

    def create_timeline(self) -> List[Dict[str, Any]]:
        """Create a timeline view of all snapshots.

        Returns:
            Timeline of snapshots with key events.
        """
        snapshots = self.list_snapshots()
        timeline = []

        for i, snapshot in enumerate(snapshots):
            event = {
                'timestamp': snapshot['timestamp'],
                'snapshot_id': snapshot['id'],
                'tag': snapshot.get('tag'),
                'description': snapshot.get('description'),
                'state': snapshot.get('state', {}),
            }

            # Identify key events
            if i > 0:
                prev_snapshot = snapshots[i - 1]
                prev_state = prev_snapshot.get('state', {})
                curr_state = snapshot.get('state', {})

                # Detect branch changes
                if prev_state.get('branch') != curr_state.get('branch'):
                    event['event_type'] = 'branch_change'
                    event['event_detail'] = f"Branch: {prev_state.get('branch')} -> {curr_state.get('branch')}"

                # Detect major file changes
                file_diff = curr_state.get('file_count', 0) - prev_state.get('file_count', 0)
                if abs(file_diff) > 50:
                    event['event_type'] = 'major_change'
                    event['event_detail'] = f"Files: {file_diff:+d}"

            timeline.append(event)

        return timeline

    def auto_snapshot(self, condition: str = 'daily') -> Optional[Dict[str, Any]]:
        """Create automatic snapshot based on conditions.

        Args:
            condition: When to create snapshot ('daily', 'weekly', 'on_change').

        Returns:
            Snapshot metadata if created, None otherwise.
        """
        should_create = False
        tag = None

        # Get last snapshot
        snapshots = self.list_snapshots()
        last_snapshot = snapshots[0] if snapshots else None

        if condition == 'daily':
            if not last_snapshot or self._hours_since(last_snapshot['timestamp']) > 24:
                should_create = True
                tag = 'auto_daily'

        elif condition == 'weekly':
            if not last_snapshot or self._hours_since(last_snapshot['timestamp']) > 168:
                should_create = True
                tag = 'auto_weekly'

        elif condition == 'on_change':
            current_state = self._capture_repo_state()
            if last_snapshot:
                if current_state.get('commit') != last_snapshot['state'].get('commit'):
                    should_create = True
                    tag = 'auto_change'
            else:
                should_create = True
                tag = 'auto_initial'

        if should_create:
            return self.create_snapshot(tag=tag, description=f'Automatic {condition} snapshot')

        return None

    def _hours_since(self, timestamp_str: str) -> float:
        """Calculate hours since a timestamp."""
        timestamp = datetime.fromisoformat(timestamp_str)
        delta = datetime.now() - timestamp
        return delta.total_seconds() / 3600

    def prune_snapshots(self, keep_count: int = 10, keep_days: int = 30) -> List[str]:
        """Prune old snapshots based on retention policy.

        Args:
            keep_count: Number of recent snapshots to keep.
            keep_days: Keep snapshots newer than this many days.

        Returns:
            List of pruned snapshot IDs.
        """
        snapshots = self.list_snapshots()
        pruned = []

        # Keep recent snapshots
        to_keep = set(s['id'] for s in snapshots[:keep_count])

        # Keep snapshots within retention period
        cutoff_date = datetime.now().timestamp() - (keep_days * 86400)
        for snapshot in snapshots:
            timestamp = datetime.fromisoformat(snapshot['timestamp']).timestamp()
            if timestamp > cutoff_date:
                to_keep.add(snapshot['id'])

            # Always keep tagged snapshots
            if snapshot.get('tag') and not snapshot['tag'].startswith('auto_'):
                to_keep.add(snapshot['id'])

        # Prune snapshots not in keep list
        for snapshot in snapshots:
            if snapshot['id'] not in to_keep:
                # Delete snapshot file
                snapshot_path = Path(snapshot['file_path'])
                if snapshot_path.exists():
                    snapshot_path.unlink()
                    pruned.append(snapshot['id'])
                    logger.info(f"Pruned snapshot: {snapshot['id']}")

        # Update metadata
        if pruned:
            remaining = [s for s in snapshots if s['id'] not in pruned]
            self._save_all_metadata(remaining)

        return pruned

    def _load_all_metadata(self) -> List[Dict[str, Any]]:
        """Load all snapshot metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return []

    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save snapshot metadata."""
        all_metadata = self._load_all_metadata()
        all_metadata.append(metadata)
        self._save_all_metadata(all_metadata)

    def _save_all_metadata(self, metadata_list: List[Dict[str, Any]]):
        """Save all metadata to file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata_list, f, indent=2)

    def export_snapshot_info_jsonl(self) -> str:
        """Export snapshot information as JSONL.

        Returns:
            JSONL string of snapshot data.
        """
        snapshots = self.list_snapshots()
        lines = []

        for snapshot in snapshots:
            lines.append(json.dumps({
                'type': 'snapshot',
                'id': snapshot['id'],
                'timestamp': snapshot['timestamp'],
                'tag': snapshot.get('tag'),
                'size': snapshot['size'],
                'file_count': snapshot['state'].get('file_count'),
                'branch': snapshot['state'].get('branch'),
                'commit': snapshot['state'].get('commit'),
            }))

        return '\n'.join(lines)