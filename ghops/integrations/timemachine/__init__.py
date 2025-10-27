"""
Repository Time Machine - Advanced git history analysis and predictions.

This module provides capabilities for:
- Analyzing repository evolution patterns
- Detecting technology migrations
- Calculating code velocity and contributor patterns
- Creating snapshots and restoring repository states
- Predictive analytics for maintenance needs
"""

from .analyzer import TimeMachineAnalyzer
from .predictor import MaintenancePredictor
from .snapshot import SnapshotManager

__all__ = [
    'TimeMachineAnalyzer',
    'MaintenancePredictor',
    'SnapshotManager',
]