"""
Repository clustering integration for ghops.

This module provides advanced clustering algorithms to identify related repositories,
find duplicate implementations, and suggest consolidation opportunities.
"""

from .core import RepositoryClusterer
from .algorithms import (
    KMeansClustering,
    DBSCANClustering,
    HierarchicalClustering,
    NetworkClustering
)
from .analyzer import DuplicationAnalyzer, ConsolidationAdvisor

__all__ = [
    'RepositoryClusterer',
    'KMeansClustering',
    'DBSCANClustering',
    'HierarchicalClustering',
    'NetworkClustering',
    'DuplicationAnalyzer',
    'ConsolidationAdvisor'
]