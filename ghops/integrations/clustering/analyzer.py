"""
Advanced repository clustering analyzer.

Uses multiple signals to identify related repositories and suggest groupings.
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
import hashlib
from datetime import datetime

import numpy as np
from rapidfuzz import fuzz
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from ..network_analysis import RepositoryNetwork

logger = logging.getLogger(__name__)


class ClusterAnalyzer:
    """Advanced clustering analysis for repository organization."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the cluster analyzer.

        Args:
            config: Configuration for clustering parameters.
        """
        self.config = config or self.get_default_config()
        self.repositories = {}
        self.features = {}
        self.clusters = {}
        self.cluster_metadata = {}

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Get default clustering configuration."""
        return {
            'min_cluster_size': 2,
            'similarity_threshold': 0.7,
            'clustering_method': 'hierarchical',  # 'kmeans', 'dbscan', 'hierarchical', 'network'
            'k_clusters': None,  # Auto-detect optimal k for k-means
            'feature_weights': {
                'name_similarity': 0.2,
                'code_similarity': 0.25,
                'dependency_overlap': 0.15,
                'commit_pattern': 0.1,
                'file_structure': 0.15,
                'documentation': 0.15,
            },
            'detection_modes': {
                'duplicates': True,
                'families': True,
                'monorepo_candidates': True,
                'split_candidates': True,
            },
            'code_similarity': {
                'min_lines': 10,  # Minimum lines for code similarity
                'threshold': 0.8,  # Similarity threshold for duplicates
                'ignore_whitespace': True,
                'ignore_comments': True,
            }
        }

    def add_repository(self, repo_data: Dict[str, Any]):
        """Add a repository for clustering analysis.

        Args:
            repo_data: Repository metadata including path, name, files, etc.
        """
        path = repo_data.get('path', '')
        if not path:
            return

        self.repositories[path] = repo_data
        self.features[path] = self._extract_features(repo_data)

    def _extract_features(self, repo_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract numerical features from repository for clustering.

        Args:
            repo_data: Repository metadata.

        Returns:
            Dictionary of feature name to value.
        """
        features = {}

        # Language distribution
        languages = repo_data.get('languages', {})
        total_bytes = sum(languages.values()) if languages else 1
        for lang in ['Python', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'Java', 'C++']:
            features[f'lang_{lang.lower()}'] = languages.get(lang, 0) / total_bytes

        # Repository size and activity
        features['total_files'] = len(repo_data.get('files', []))
        features['total_commits'] = repo_data.get('commit_count', 0)
        features['contributors'] = len(repo_data.get('contributors', []))
        features['age_days'] = self._calculate_age(repo_data.get('created_at'))
        features['last_activity_days'] = self._calculate_age(repo_data.get('updated_at'))

        # Code characteristics
        features['avg_file_size'] = self._calculate_avg_file_size(repo_data)
        features['directory_depth'] = self._calculate_max_depth(repo_data.get('files', []))
        features['has_tests'] = 1.0 if self._has_tests(repo_data) else 0.0
        features['has_ci'] = 1.0 if self._has_ci(repo_data) else 0.0
        features['has_docs'] = 1.0 if self._has_docs(repo_data) else 0.0

        # Package/dependency characteristics
        package = repo_data.get('package', {})
        features['is_published'] = 1.0 if package.get('published') else 0.0
        features['dependency_count'] = len(package.get('dependencies', []))
        features['is_library'] = 1.0 if self._is_library(repo_data) else 0.0
        features['is_application'] = 1.0 if self._is_application(repo_data) else 0.0

        # Documentation and metadata
        features['readme_length'] = len(repo_data.get('readme_content', ''))
        features['has_license'] = 1.0 if repo_data.get('license') else 0.0
        features['topic_count'] = len(repo_data.get('topics', []))

        return features

    def _calculate_age(self, date_str: Optional[str]) -> float:
        """Calculate age in days from date string."""
        if not date_str:
            return 0.0
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return (datetime.now() - date).days
        except:
            return 0.0

    def _calculate_avg_file_size(self, repo_data: Dict) -> float:
        """Calculate average file size."""
        files = repo_data.get('files', [])
        if not files:
            return 0.0
        sizes = [f.get('size', 0) for f in files if isinstance(f, dict)]
        return sum(sizes) / len(sizes) if sizes else 0.0

    def _calculate_max_depth(self, files: List) -> int:
        """Calculate maximum directory depth."""
        if not files:
            return 0
        max_depth = 0
        for f in files:
            if isinstance(f, str):
                depth = f.count('/') if '/' in f else 0
            elif isinstance(f, dict):
                path = f.get('path', '')
                depth = path.count('/') if '/' in path else 0
            else:
                depth = 0
            max_depth = max(max_depth, depth)
        return max_depth

    def _has_tests(self, repo_data: Dict) -> bool:
        """Check if repository has test files."""
        files = repo_data.get('files', [])
        test_patterns = ['test_', '_test', '/tests/', '/test/', 'spec.', '.spec']
        for f in files:
            path = f if isinstance(f, str) else f.get('path', '')
            if any(pattern in path.lower() for pattern in test_patterns):
                return True
        return False

    def _has_ci(self, repo_data: Dict) -> bool:
        """Check if repository has CI configuration."""
        files = repo_data.get('files', [])
        ci_patterns = ['.github/workflows', '.gitlab-ci', '.travis', 'jenkinsfile', '.circleci']
        for f in files:
            path = f if isinstance(f, str) else f.get('path', '')
            if any(pattern in path.lower() for pattern in ci_patterns):
                return True
        return False

    def _has_docs(self, repo_data: Dict) -> bool:
        """Check if repository has documentation."""
        files = repo_data.get('files', [])
        doc_patterns = ['/docs/', '/documentation/', 'readme', '.md', '.rst']
        for f in files:
            path = f if isinstance(f, str) else f.get('path', '')
            if any(pattern in path.lower() for pattern in doc_patterns):
                return True
        return False

    def _is_library(self, repo_data: Dict) -> bool:
        """Detect if repository is a library."""
        indicators = [
            repo_data.get('package', {}).get('published'),
            'lib' in repo_data.get('name', '').lower(),
            'library' in repo_data.get('description', '').lower(),
            'framework' in repo_data.get('description', '').lower(),
            any('lib' in topic.lower() for topic in repo_data.get('topics', [])),
        ]
        return sum(bool(i) for i in indicators) >= 2

    def _is_application(self, repo_data: Dict) -> bool:
        """Detect if repository is an application."""
        indicators = [
            'app' in repo_data.get('name', '').lower(),
            'application' in repo_data.get('description', '').lower(),
            'server' in repo_data.get('description', '').lower(),
            'cli' in repo_data.get('description', '').lower(),
            any(f.endswith(('main.py', 'app.py', 'server.py', 'cli.py'))
                for f in repo_data.get('files', []) if isinstance(f, str)),
        ]
        return sum(bool(i) for i in indicators) >= 2

    def perform_clustering(self, method: Optional[str] = None) -> Dict[str, List[str]]:
        """Perform clustering analysis on repositories.

        Args:
            method: Clustering method ('kmeans', 'hierarchical', 'dbscan', 'network').
                   Uses config default if not specified.

        Returns:
            Dictionary mapping cluster IDs to repository paths.
        """
        method = method or self.config['clustering_method']

        if method == 'network':
            return self._network_based_clustering()
        elif method == 'dbscan':
            return self._dbscan_clustering()
        elif method == 'kmeans':
            return self._kmeans_clustering()
        else:  # hierarchical
            return self._hierarchical_clustering()

    def _prepare_feature_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """Prepare feature matrix for clustering algorithms.

        Returns:
            Tuple of (feature_matrix, repo_paths).
        """
        repo_paths = list(self.features.keys())
        if not repo_paths:
            return np.array([]), []

        # Get all feature names
        all_features = set()
        for features in self.features.values():
            all_features.update(features.keys())
        feature_names = sorted(all_features)

        # Build matrix
        matrix = []
        for path in repo_paths:
            row = [self.features[path].get(fname, 0.0) for fname in feature_names]
            matrix.append(row)

        # Standardize features
        matrix = np.array(matrix)
        if matrix.shape[0] > 1:
            scaler = StandardScaler()
            matrix = scaler.fit_transform(matrix)

        return matrix, repo_paths

    def _hierarchical_clustering(self) -> Dict[str, List[str]]:
        """Perform hierarchical clustering."""
        matrix, repo_paths = self._prepare_feature_matrix()

        if len(repo_paths) < 2:
            return {}

        # Perform clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.config['similarity_threshold'],
            linkage='average'
        )
        labels = clustering.fit_predict(matrix)

        # Group by cluster
        clusters = defaultdict(list)
        for path, label in zip(repo_paths, labels):
            clusters[f"cluster_{label}"].append(path)

        # Filter out single-repo clusters
        self.clusters = {
            cid: repos for cid, repos in clusters.items()
            if len(repos) >= self.config['min_cluster_size']
        }

        # Generate metadata for each cluster
        self._generate_cluster_metadata()

        return self.clusters

    def _dbscan_clustering(self) -> Dict[str, List[str]]:
        """Perform DBSCAN clustering."""
        matrix, repo_paths = self._prepare_feature_matrix()

        if len(repo_paths) < 2:
            return {}

        # Perform clustering
        clustering = DBSCAN(
            eps=1 - self.config['similarity_threshold'],
            min_samples=self.config['min_cluster_size']
        )
        labels = clustering.fit_predict(matrix)

        # Group by cluster (ignore noise points with label -1)
        clusters = defaultdict(list)
        for path, label in zip(repo_paths, labels):
            if label >= 0:
                clusters[f"cluster_{label}"].append(path)

        self.clusters = dict(clusters)
        self._generate_cluster_metadata()

        return self.clusters

    def _kmeans_clustering(self) -> Dict[str, List[str]]:
        """Perform K-means clustering with optimal k detection."""
        matrix, repo_paths = self._prepare_feature_matrix()

        if len(repo_paths) < 2:
            return {}

        # Determine optimal k if not specified
        k = self.config.get('k_clusters')
        if k is None:
            k = self._find_optimal_k(matrix, min_k=2, max_k=min(10, len(repo_paths) // 2))

        # Perform clustering
        clustering = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = clustering.fit_predict(matrix)

        # Group by cluster
        clusters = defaultdict(list)
        for path, label in zip(repo_paths, labels):
            clusters[f"cluster_{label}"].append(path)

        # Filter out single-repo clusters
        self.clusters = {
            cid: repos for cid, repos in clusters.items()
            if len(repos) >= self.config['min_cluster_size']
        }

        self._generate_cluster_metadata()
        return self.clusters

    def _find_optimal_k(self, matrix: np.ndarray, min_k: int = 2, max_k: int = 10) -> int:
        """Find optimal number of clusters using silhouette score."""
        best_k = min_k
        best_score = -1

        for k in range(min_k, min(max_k + 1, matrix.shape[0])):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(matrix)
                score = silhouette_score(matrix, labels)

                if score > best_score:
                    best_score = score
                    best_k = k
            except:
                continue

        logger.info(f"Optimal k={best_k} with silhouette score={best_score:.3f}")
        return best_k

    def _network_based_clustering(self) -> Dict[str, List[str]]:
        """Use network analysis for clustering."""
        # Build network
        network = RepositoryNetwork()
        for path, data in self.repositories.items():
            network.add_repository(data)

        network.build_network()
        self.clusters = network.find_clusters()
        self._generate_cluster_metadata()

        return self.clusters

    def _generate_cluster_metadata(self):
        """Generate metadata and insights for each cluster."""
        self.cluster_metadata = {}

        for cluster_id, repo_paths in self.clusters.items():
            metadata = {
                'id': cluster_id,
                'size': len(repo_paths),
                'repositories': repo_paths,
                'common_languages': self._find_common_languages(repo_paths),
                'common_topics': self._find_common_topics(repo_paths),
                'cluster_type': self._determine_cluster_type(repo_paths),
                'consolidation_potential': self._assess_consolidation(repo_paths),
                'suggested_name': self._suggest_cluster_name(repo_paths),
                'insights': self._generate_cluster_insights(repo_paths),
            }
            self.cluster_metadata[cluster_id] = metadata

    def _find_common_languages(self, repo_paths: List[str]) -> List[str]:
        """Find common programming languages in cluster."""
        lang_counts = defaultdict(int)
        for path in repo_paths:
            repo = self.repositories.get(path, {})
            for lang in repo.get('languages', {}):
                lang_counts[lang] += 1

        # Return languages present in >50% of repos
        threshold = len(repo_paths) / 2
        return [lang for lang, count in lang_counts.items() if count >= threshold]

    def _find_common_topics(self, repo_paths: List[str]) -> List[str]:
        """Find common topics/tags in cluster."""
        topic_counts = defaultdict(int)
        for path in repo_paths:
            repo = self.repositories.get(path, {})
            for topic in repo.get('topics', []):
                topic_counts[topic] += 1
            for tag in repo.get('tags', []):
                topic_counts[tag] += 1

        # Return topics present in >50% of repos
        threshold = len(repo_paths) / 2
        return [topic for topic, count in topic_counts.items() if count >= threshold]

    def _determine_cluster_type(self, repo_paths: List[str]) -> str:
        """Determine the type of cluster (duplicates, family, etc.)."""
        if self._are_duplicates(repo_paths):
            return 'duplicates'
        elif self._is_project_family(repo_paths):
            return 'project_family'
        elif self._is_monorepo_candidate(repo_paths):
            return 'monorepo_candidate'
        elif self._is_split_candidate(repo_paths):
            return 'split_candidate'
        else:
            return 'related'

    def _are_duplicates(self, repo_paths: List[str]) -> bool:
        """Check if repositories are likely duplicates."""
        if len(repo_paths) < 2:
            return False

        names = [self.repositories[p].get('name', '') for p in repo_paths]

        # Check for very similar names
        for i, name1 in enumerate(names):
            for name2 in names[i+1:]:
                similarity = fuzz.ratio(name1, name2)
                if similarity > 85:  # Very high similarity
                    return True

        # Check for identical README content
        readmes = [self.repositories[p].get('readme_content', '') for p in repo_paths]
        if len(set(readmes)) == 1 and readmes[0]:  # All identical and non-empty
            return True

        return False

    def _is_project_family(self, repo_paths: List[str]) -> bool:
        """Check if repositories form a project family."""
        names = [self.repositories[p].get('name', '') for p in repo_paths]

        # Check for common prefix/suffix
        if len(names) < 2:
            return False

        # Find common prefix
        prefix = names[0]
        for name in names[1:]:
            while not name.startswith(prefix) and prefix:
                prefix = prefix[:-1]

        # Find common suffix
        suffix = names[0][::-1]
        for name in names[1:]:
            reversed_name = name[::-1]
            while not reversed_name.startswith(suffix) and suffix:
                suffix = suffix[:-1]
        suffix = suffix[::-1]

        # If significant common prefix or suffix exists
        return len(prefix) > 3 or len(suffix) > 3

    def _is_monorepo_candidate(self, repo_paths: List[str]) -> bool:
        """Check if repositories could be combined into a monorepo."""
        if len(repo_paths) < 2:
            return False

        # Check for small, related repositories
        sizes = []
        for path in repo_paths:
            repo = self.repositories.get(path, {})
            file_count = len(repo.get('files', []))
            sizes.append(file_count)

        # Small repos with shared dependencies
        avg_size = sum(sizes) / len(sizes)
        if avg_size < 50:  # Small repositories
            # Check for shared dependencies
            all_deps = []
            for path in repo_paths:
                deps = self.repositories[path].get('package', {}).get('dependencies', [])
                all_deps.extend(deps)

            # High overlap in dependencies
            unique_deps = set(all_deps)
            if len(all_deps) > 0:
                overlap_ratio = 1 - (len(unique_deps) / len(all_deps))
                return overlap_ratio > 0.5

        return False

    def _is_split_candidate(self, repo_paths: List[str]) -> bool:
        """Check if a repository should be split."""
        # This would typically only have one repo in the cluster
        if len(repo_paths) != 1:
            return False

        repo = self.repositories.get(repo_paths[0], {})
        file_count = len(repo.get('files', []))

        # Large repository with multiple distinct components
        if file_count > 500:
            # Check for multiple top-level directories
            top_dirs = set()
            for f in repo.get('files', []):
                path = f if isinstance(f, str) else f.get('path', '')
                if '/' in path:
                    top_dir = path.split('/')[0]
                    top_dirs.add(top_dir)

            # Many top-level directories suggest multiple components
            return len(top_dirs) > 10

        return False

    def _assess_consolidation(self, repo_paths: List[str]) -> Dict[str, Any]:
        """Assess consolidation potential for a cluster."""
        assessment = {
            'score': 0.0,
            'recommendation': 'none',
            'benefits': [],
            'risks': [],
            'effort': 'low',
        }

        cluster_type = self._determine_cluster_type(repo_paths)

        if cluster_type == 'duplicates':
            assessment['score'] = 0.9
            assessment['recommendation'] = 'merge_duplicates'
            assessment['benefits'] = [
                'Eliminate redundant maintenance',
                'Consolidate issues and contributions',
                'Reduce confusion for users',
            ]
            assessment['risks'] = [
                'May break existing dependencies',
                'Need to migrate issues/PRs',
            ]
            assessment['effort'] = 'low'

        elif cluster_type == 'monorepo_candidate':
            assessment['score'] = 0.7
            assessment['recommendation'] = 'create_monorepo'
            assessment['benefits'] = [
                'Simplified dependency management',
                'Atomic commits across components',
                'Easier refactoring',
            ]
            assessment['risks'] = [
                'Increased repository complexity',
                'Larger clone size',
                'Need for better tooling',
            ]
            assessment['effort'] = 'medium'

        elif cluster_type == 'project_family':
            assessment['score'] = 0.5
            assessment['recommendation'] = 'organize_family'
            assessment['benefits'] = [
                'Better organization',
                'Shared documentation',
                'Consistent tooling',
            ]
            assessment['risks'] = [
                'May not need consolidation',
                'Each project might have different requirements',
            ]
            assessment['effort'] = 'low'

        elif cluster_type == 'split_candidate':
            assessment['score'] = 0.8
            assessment['recommendation'] = 'split_repository'
            assessment['benefits'] = [
                'Better modularity',
                'Independent versioning',
                'Clearer boundaries',
            ]
            assessment['risks'] = [
                'Breaking existing integrations',
                'More repositories to manage',
            ]
            assessment['effort'] = 'high'

        return assessment

    def _suggest_cluster_name(self, repo_paths: List[str]) -> str:
        """Suggest a name for the cluster based on common patterns."""
        names = [self.repositories[p].get('name', '') for p in repo_paths]

        if not names:
            return 'unnamed-cluster'

        # Find common prefix
        prefix = names[0]
        for name in names[1:]:
            while not name.startswith(prefix) and prefix:
                prefix = prefix[:-1]

        if prefix and len(prefix) > 3:
            return f"{prefix}-family"

        # Use most common topic
        topics = self._find_common_topics(repo_paths)
        if topics:
            return f"{topics[0]}-group"

        # Use most common language
        languages = self._find_common_languages(repo_paths)
        if languages:
            return f"{languages[0].lower()}-projects"

        return f"cluster-{len(repo_paths)}-repos"

    def _generate_cluster_insights(self, repo_paths: List[str]) -> List[str]:
        """Generate actionable insights for a cluster."""
        insights = []

        cluster_type = self._determine_cluster_type(repo_paths)

        if cluster_type == 'duplicates':
            insights.append(f"Found {len(repo_paths)} potential duplicate repositories")
            insights.append("Consider merging into a single repository")
            insights.append("Review git history to identify the most complete version")

        elif cluster_type == 'monorepo_candidate':
            total_files = sum(len(self.repositories[p].get('files', [])) for p in repo_paths)
            insights.append(f"These {len(repo_paths)} small repositories could be combined")
            insights.append(f"Total combined size would be approximately {total_files} files")
            insights.append("Consider using a monorepo structure with workspaces")

        elif cluster_type == 'project_family':
            insights.append(f"Identified a family of {len(repo_paths)} related projects")
            insights.append("Consider creating a parent organization or namespace")
            insights.append("Standardize tooling and documentation across the family")

        elif cluster_type == 'split_candidate':
            repo = self.repositories.get(repo_paths[0], {})
            file_count = len(repo.get('files', []))
            insights.append(f"Large repository with {file_count} files may benefit from splitting")
            insights.append("Consider extracting independent modules")
            insights.append("Use git subtree or filter-branch to preserve history")

        # Add language-specific insights
        languages = self._find_common_languages(repo_paths)
        if languages:
            insights.append(f"Primary languages: {', '.join(languages)}")
            if 'Python' in languages:
                insights.append("Consider using Poetry or pip-tools for dependency management")
            elif 'JavaScript' in languages or 'TypeScript' in languages:
                insights.append("Consider using Lerna or Nx for monorepo management")

        return insights

    def export_clusters_jsonl(self):
        """Generate JSONL output for clusters.

        Yields:
            JSON strings, one per line, for each cluster.
        """
        for cluster_id, metadata in self.cluster_metadata.items():
            # Add repository details
            repos_detail = []
            for path in metadata['repositories']:
                repo = self.repositories.get(path, {})
                repos_detail.append({
                    'path': path,
                    'name': repo.get('name'),
                    'description': repo.get('description'),
                    'language': repo.get('language'),
                    'stars': repo.get('stars', 0),
                })

            output = {
                'type': 'cluster',
                'id': cluster_id,
                'name': metadata['suggested_name'],
                'size': metadata['size'],
                'cluster_type': metadata['cluster_type'],
                'repositories': repos_detail,
                'common_languages': metadata['common_languages'],
                'common_topics': metadata['common_topics'],
                'consolidation': metadata['consolidation_potential'],
                'insights': metadata['insights'],
            }

            yield json.dumps(output)

    def find_duplicate_code(self) -> List[Dict[str, Any]]:
        """Find duplicate code patterns across repositories.

        Returns:
            List of duplicate code findings with similarity scores.
        """
        duplicates = []

        # Track identical files
        file_hashes = defaultdict(list)

        # Track similar code blocks
        code_blocks = []

        for repo_path, repo_data in self.repositories.items():
            for file_info in repo_data.get('files', []):
                if isinstance(file_info, dict):
                    content = file_info.get('content', '')
                    file_path = file_info.get('path', '')

                    if content and self._is_code_file(file_path):
                        # Hash for identical detection
                        normalized = self._normalize_code(content)
                        file_hash = hashlib.md5(normalized.encode()).hexdigest()

                        file_hashes[file_hash].append({
                            'repo': repo_path,
                            'file': file_path,
                            'lines': len(content.splitlines()),
                        })

                        # Extract significant code blocks
                        blocks = self._extract_code_blocks(content, file_path)
                        for block in blocks:
                            code_blocks.append({
                                'repo': repo_path,
                                'file': file_path,
                                'block': block,
                                'hash': hashlib.md5(block['normalized'].encode()).hexdigest(),
                            })

        # Find identical files across repos
        for file_hash, locations in file_hashes.items():
            if len(locations) > 1:
                repos = defaultdict(list)
                total_lines = 0
                for loc in locations:
                    repos[loc['repo']].append({
                        'file': loc['file'],
                        'lines': loc['lines'],
                    })
                    total_lines += loc['lines']

                if len(repos) > 1:  # Same file in multiple repos
                    duplicates.append({
                        'type': 'identical_files',
                        'severity': 'high',
                        'hash': file_hash,
                        'repositories': dict(repos),
                        'file_count': len(locations),
                        'total_lines': total_lines,
                        'recommendation': 'Consider creating a shared library',
                    })

        # Find similar code blocks
        block_groups = defaultdict(list)
        for block_info in code_blocks:
            block_groups[block_info['hash']].append(block_info)

        for block_hash, blocks in block_groups.items():
            if len(blocks) > 1:
                # Group by repository
                repos = defaultdict(list)
                for b in blocks:
                    repos[b['repo']].append({
                        'file': b['file'],
                        'function': b['block'].get('name', 'unknown'),
                        'lines': b['block']['lines'],
                        'start_line': b['block'].get('start_line', 0),
                    })

                if len(repos) > 1:  # Same block in multiple repos
                    duplicates.append({
                        'type': 'duplicate_code_block',
                        'severity': 'medium',
                        'hash': block_hash,
                        'repositories': dict(repos),
                        'block_count': len(blocks),
                        'lines_duplicated': blocks[0]['block']['lines'],
                        'recommendation': 'Extract into shared function or module',
                    })

        # Calculate duplication metrics
        self._calculate_duplication_metrics(duplicates)

        return duplicates

    def _normalize_code(self, content: str) -> str:
        """Normalize code for comparison (remove whitespace, comments)."""
        if not self.config['code_similarity']['ignore_whitespace']:
            return content

        lines = []
        for line in content.splitlines():
            # Remove leading/trailing whitespace
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip comment lines (simple heuristic)
            if self.config['code_similarity']['ignore_comments']:
                if line.startswith(('#', '//', '/*', '*', '"', "'")):
                    continue

            lines.append(line)

        return '\n'.join(lines)

    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file based on extension."""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.scala',
            '.r', '.m', '.mm', '.sh', '.bash', '.zsh', '.fish',
        }

        for ext in code_extensions:
            if file_path.lower().endswith(ext):
                return True

        return False

    def _extract_code_blocks(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract significant code blocks (functions, classes) from content."""
        blocks = []

        # Language-specific extraction
        if file_path.endswith('.py'):
            blocks.extend(self._extract_python_blocks(content))
        elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
            blocks.extend(self._extract_javascript_blocks(content))
        elif file_path.endswith('.go'):
            blocks.extend(self._extract_go_blocks(content))

        return blocks

    def _extract_python_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract Python functions and classes."""
        blocks = []
        lines = content.splitlines()

        import_end = 0
        for i, line in enumerate(lines):
            if not line.strip().startswith(('import ', 'from ', '#')) and line.strip():
                import_end = i
                break

        # Simple pattern matching for functions and classes
        for i, line in enumerate(lines[import_end:], import_end):
            if line.startswith('def ') or line.startswith('class '):
                # Find the end of the block
                indent_level = len(line) - len(line.lstrip())
                end_line = i + 1

                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith(' ' * (indent_level + 1)):
                        end_line = j
                        break
                else:
                    end_line = len(lines)

                block_lines = lines[i:end_line]
                block_content = '\n'.join(block_lines)

                if len(block_lines) >= self.config['code_similarity']['min_lines']:
                    blocks.append({
                        'name': line.split('(')[0].replace('def ', '').replace('class ', ''),
                        'type': 'function' if line.startswith('def ') else 'class',
                        'content': block_content,
                        'normalized': self._normalize_code(block_content),
                        'lines': len(block_lines),
                        'start_line': i,
                    })

        return blocks

    def _extract_javascript_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript/TypeScript functions and classes."""
        blocks = []
        # Simple pattern matching - could be enhanced with proper parsing
        patterns = [
            r'function\s+(\w+)\s*\([^)]*\)\s*{',
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{',
            r'class\s+(\w+)\s*{',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Extract block content (simplified)
                start = match.start()
                name = match.group(1)

                # Find matching closing brace
                brace_count = 1
                i = match.end()
                while i < len(content) and brace_count > 0:
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                    i += 1

                block_content = content[start:i]
                lines = block_content.splitlines()

                if len(lines) >= self.config['code_similarity']['min_lines']:
                    blocks.append({
                        'name': name,
                        'type': 'function' if 'function' in pattern else 'class',
                        'content': block_content,
                        'normalized': self._normalize_code(block_content),
                        'lines': len(lines),
                        'start_line': content[:start].count('\n'),
                    })

        return blocks

    def _extract_go_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract Go functions and types."""
        blocks = []
        patterns = [
            r'func\s+(\w+)\s*\([^)]*\)\s*[^{]*{',
            r'type\s+(\w+)\s+struct\s*{',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                start = match.start()
                name = match.group(1)

                # Find matching closing brace
                brace_count = 1
                i = match.end()
                while i < len(content) and brace_count > 0:
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                    i += 1

                block_content = content[start:i]
                lines = block_content.splitlines()

                if len(lines) >= self.config['code_similarity']['min_lines']:
                    blocks.append({
                        'name': name,
                        'type': 'function' if 'func' in pattern else 'type',
                        'content': block_content,
                        'normalized': self._normalize_code(block_content),
                        'lines': len(lines),
                        'start_line': content[:start].count('\n'),
                    })

        return blocks

    def _calculate_duplication_metrics(self, duplicates: List[Dict[str, Any]]):
        """Calculate and add duplication metrics to the findings."""
        total_repos = len(self.repositories)

        for dup in duplicates:
            affected_repos = len(dup.get('repositories', {}))
            dup['impact_score'] = affected_repos / total_repos if total_repos > 0 else 0
            dup['affected_percentage'] = (affected_repos / total_repos * 100) if total_repos > 0 else 0

            # Priority based on impact and severity
            if dup['impact_score'] > 0.5 or dup['severity'] == 'high':
                dup['priority'] = 'critical'
            elif dup['impact_score'] > 0.3 or dup['severity'] == 'medium':
                dup['priority'] = 'high'
            else:
                dup['priority'] = 'medium'

    def suggest_project_structure(self) -> Dict[str, Any]:
        """Suggest an optimal project structure based on cluster analysis.

        Returns:
            Dictionary with structure recommendations.
        """
        structure = {
            'total_repositories': len(self.repositories),
            'clusters_found': len(self.clusters),
            'recommendations': [],
            'proposed_structure': {},
        }

        # Analyze each cluster
        for cluster_id, metadata in self.cluster_metadata.items():
            cluster_type = metadata['cluster_type']
            consolidation = metadata['consolidation_potential']

            if consolidation['score'] > 0.7:
                structure['recommendations'].append({
                    'cluster': cluster_id,
                    'action': consolidation['recommendation'],
                    'affected_repos': metadata['repositories'],
                    'priority': 'high' if consolidation['score'] > 0.8 else 'medium',
                    'effort': consolidation['effort'],
                    'benefits': consolidation['benefits'],
                })

        # Propose new structure
        if self.cluster_metadata:
            # Group by cluster type
            by_type = defaultdict(list)
            for cluster_id, metadata in self.cluster_metadata.items():
                by_type[metadata['cluster_type']].append(cluster_id)

            structure['proposed_structure'] = {
                'monorepos': [
                    self.cluster_metadata[cid]['suggested_name']
                    for cid in by_type.get('monorepo_candidate', [])
                ],
                'to_merge': [
                    self.cluster_metadata[cid]['repositories']
                    for cid in by_type.get('duplicates', [])
                ],
                'families': [
                    {
                        'name': self.cluster_metadata[cid]['suggested_name'],
                        'members': self.cluster_metadata[cid]['repositories'],
                    }
                    for cid in by_type.get('project_family', [])
                ],
                'to_split': by_type.get('split_candidate', []),
            }

        # Add statistics
        structure['statistics'] = {
            'duplicate_clusters': len([
                c for c in self.cluster_metadata.values()
                if c['cluster_type'] == 'duplicates'
            ]),
            'monorepo_opportunities': len([
                c for c in self.cluster_metadata.values()
                if c['cluster_type'] == 'monorepo_candidate'
            ]),
            'project_families': len([
                c for c in self.cluster_metadata.values()
                if c['cluster_type'] == 'project_family'
            ]),
        }

        return structure