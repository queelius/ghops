"""
Repository clustering and consolidation analysis.

This module provides advanced clustering algorithms to:
- Identify duplicate/similar repositories
- Suggest consolidation opportunities
- Detect project families and relationships
- Auto-group repositories by purpose
"""

from .analyzer import ClusterAnalyzer
from .consolidator import ConsolidationAdvisor
from .commands import register_clustering_commands

__all__ = [
    'ClusterAnalyzer',
    'ConsolidationAdvisor',
    'register_clustering_commands',
]