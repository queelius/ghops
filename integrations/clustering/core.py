"""
Core clustering functionality for repository analysis.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Set, Tuple
from collections import defaultdict
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ClusteringMethod(Enum):
    KMEANS = "kmeans"
    DBSCAN = "dbscan"
    HIERARCHICAL = "hierarchical"
    NETWORK = "network"
    AUTO = "auto"


@dataclass
class ClusterResult:
    """Result of clustering operation."""
    cluster_id: int
    repositories: List[str]
    centroid_repo: Optional[str]
    coherence_score: float
    primary_language: Optional[str]
    common_topics: List[str]
    description: str


@dataclass
class SimilarityScore:
    """Similarity score between two repositories."""
    repo1: str
    repo2: str
    overall_score: float
    code_similarity: float
    structure_similarity: float
    dependency_similarity: float
    topic_similarity: float
    reasons: List[str]


@dataclass
class ConsolidationSuggestion:
    """Suggestion for repository consolidation."""
    repositories: List[str]
    confidence: float
    rationale: str
    common_code_blocks: List[str]
    suggested_name: str
    estimated_effort: str  # "low", "medium", "high"
    benefits: List[str]


class RepositoryClusterer:
    """Main class for repository clustering operations."""

    def __init__(self, metadata_store: Optional[Dict] = None):
        """Initialize the clusterer.

        Args:
            metadata_store: Optional pre-loaded repository metadata
        """
        self.metadata_store = metadata_store or {}
        self.repositories = {}
        self.feature_matrix = None
        self.similarity_matrix = None
        self.clusters = {}

    def load_repositories(self, repo_paths: List[str]) -> Iterator[Dict]:
        """Load repository metadata for clustering.

        Args:
            repo_paths: List of repository paths to analyze

        Yields:
            Repository metadata dictionaries
        """
        for path in repo_paths:
            try:
                repo_data = self._load_repo_metadata(path)
                self.repositories[path] = repo_data
                yield {
                    "action": "loading",
                    "path": path,
                    "status": "success"
                }
            except Exception as e:
                yield {
                    "action": "loading",
                    "path": path,
                    "status": "error",
                    "error": str(e)
                }

    def _load_repo_metadata(self, path: str) -> Dict:
        """Load metadata for a single repository."""
        repo_path = Path(path)

        # Check metadata store first
        if path in self.metadata_store:
            return self.metadata_store[path]

        metadata = {
            "path": path,
            "name": repo_path.name,
            "exists": repo_path.exists()
        }

        if not repo_path.exists():
            return metadata

        # Extract repository features
        metadata.update(self._extract_features(repo_path))

        return metadata

    def _extract_features(self, repo_path: Path) -> Dict:
        """Extract features from repository for clustering."""
        features = {
            "languages": [],
            "file_count": 0,
            "total_size": 0,
            "has_tests": False,
            "has_docs": False,
            "has_ci": False,
            "dependencies": [],
            "topics": [],
            "file_structure": {},
            "readme_keywords": []
        }

        # Detect languages
        language_extensions = defaultdict(int)
        for file in repo_path.rglob("*"):
            if file.is_file():
                features["file_count"] += 1
                features["total_size"] += file.stat().st_size

                ext = file.suffix.lower()
                if ext in LANGUAGE_MAP:
                    language_extensions[LANGUAGE_MAP[ext]] += 1

        features["languages"] = sorted(
            language_extensions.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]  # Top 3 languages

        # Detect common patterns
        features["has_tests"] = any(
            repo_path.glob(pattern)
            for pattern in ["**/test_*.py", "**/tests/", "**/*_test.go", "**/spec/"]
        )
        features["has_docs"] = (repo_path / "docs").exists() or (repo_path / "documentation").exists()
        features["has_ci"] = (repo_path / ".github" / "workflows").exists() or (repo_path / ".gitlab-ci.yml").exists()

        # Extract dependencies (Python example)
        requirements = repo_path / "requirements.txt"
        if requirements.exists():
            try:
                deps = requirements.read_text().splitlines()
                features["dependencies"] = [
                    dep.split("==")[0].split(">=")[0].strip()
                    for dep in deps if dep and not dep.startswith("#")
                ]
            except:
                pass

        # Extract README keywords
        readme_files = list(repo_path.glob("README*"))
        if readme_files:
            try:
                readme_text = readme_files[0].read_text()[:1000]  # First 1000 chars
                # Simple keyword extraction
                import re
                words = re.findall(r'\b[a-z]+\b', readme_text.lower())
                features["readme_keywords"] = [
                    w for w in words
                    if len(w) > 4 and w not in COMMON_WORDS
                ][:20]
            except:
                pass

        return features

    def build_feature_matrix(self) -> np.ndarray:
        """Build feature matrix for clustering algorithms."""
        if not self.repositories:
            raise ValueError("No repositories loaded")

        # Create feature vectors
        all_languages = set()
        all_dependencies = set()
        all_keywords = set()

        for repo_data in self.repositories.values():
            for lang, _ in repo_data.get("languages", []):
                all_languages.add(lang)
            all_dependencies.update(repo_data.get("dependencies", []))
            all_keywords.update(repo_data.get("readme_keywords", []))

        # Create feature indices
        lang_index = {lang: i for i, lang in enumerate(all_languages)}
        dep_index = {dep: i + len(lang_index) for i, dep in enumerate(all_dependencies)}
        keyword_index = {kw: i + len(lang_index) + len(dep_index) for i, kw in enumerate(all_keywords)}

        feature_dim = len(lang_index) + len(dep_index) + len(keyword_index) + 5  # +5 for boolean features

        # Build matrix
        repo_list = list(self.repositories.keys())
        matrix = np.zeros((len(repo_list), feature_dim))

        for i, repo_path in enumerate(repo_list):
            repo_data = self.repositories[repo_path]

            # Language features
            for lang, count in repo_data.get("languages", []):
                if lang in lang_index:
                    matrix[i, lang_index[lang]] = min(count / 100.0, 1.0)  # Normalize

            # Dependency features
            for dep in repo_data.get("dependencies", []):
                if dep in dep_index:
                    matrix[i, dep_index[dep]] = 1.0

            # Keyword features
            for kw in repo_data.get("readme_keywords", []):
                if kw in keyword_index:
                    matrix[i, keyword_index[kw]] = 1.0

            # Boolean features
            bool_start = len(lang_index) + len(dep_index) + len(keyword_index)
            matrix[i, bool_start] = float(repo_data.get("has_tests", False))
            matrix[i, bool_start + 1] = float(repo_data.get("has_docs", False))
            matrix[i, bool_start + 2] = float(repo_data.get("has_ci", False))
            matrix[i, bool_start + 3] = min(repo_data.get("file_count", 0) / 1000.0, 1.0)
            matrix[i, bool_start + 4] = min(repo_data.get("total_size", 0) / 10000000.0, 1.0)

        self.feature_matrix = matrix
        return matrix

    def compute_similarity_matrix(self) -> np.ndarray:
        """Compute pairwise similarity matrix between repositories."""
        if self.feature_matrix is None:
            self.build_feature_matrix()

        # Compute cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        self.similarity_matrix = cosine_similarity(self.feature_matrix)
        return self.similarity_matrix

    def cluster(self, method: ClusteringMethod = ClusteringMethod.AUTO,
                n_clusters: Optional[int] = None) -> Iterator[Dict]:
        """Perform clustering on repositories.

        Args:
            method: Clustering method to use
            n_clusters: Number of clusters (for methods that require it)

        Yields:
            Progress updates and results
        """
        if method == ClusteringMethod.AUTO:
            method = self._select_best_method()
            yield {
                "action": "method_selection",
                "selected": method.value,
                "reason": "Automatically selected based on repository characteristics"
            }

        # Build feature matrix if needed
        if self.feature_matrix is None:
            yield {"action": "building_features", "status": "started"}
            self.build_feature_matrix()
            yield {"action": "building_features", "status": "completed"}

        # Run clustering
        if method == ClusteringMethod.KMEANS:
            yield from self._cluster_kmeans(n_clusters)
        elif method == ClusteringMethod.DBSCAN:
            yield from self._cluster_dbscan()
        elif method == ClusteringMethod.HIERARCHICAL:
            yield from self._cluster_hierarchical(n_clusters)
        elif method == ClusteringMethod.NETWORK:
            yield from self._cluster_network()

    def _select_best_method(self) -> ClusteringMethod:
        """Select the best clustering method based on data characteristics."""
        n_repos = len(self.repositories)

        if n_repos < 10:
            return ClusteringMethod.HIERARCHICAL
        elif n_repos < 50:
            return ClusteringMethod.KMEANS
        elif n_repos < 200:
            return ClusteringMethod.DBSCAN
        else:
            return ClusteringMethod.NETWORK

    def _cluster_kmeans(self, n_clusters: Optional[int]) -> Iterator[Dict]:
        """Perform K-means clustering."""
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        if n_clusters is None:
            # Find optimal k using silhouette score
            yield {"action": "finding_optimal_k", "status": "started"}
            best_k = 2
            best_score = -1

            for k in range(2, min(10, len(self.repositories))):
                kmeans = KMeans(n_clusters=k, random_state=42)
                labels = kmeans.fit_predict(self.feature_matrix)
                score = silhouette_score(self.feature_matrix, labels)

                yield {
                    "action": "testing_k",
                    "k": k,
                    "silhouette_score": score
                }

                if score > best_score:
                    best_score = score
                    best_k = k

            n_clusters = best_k
            yield {
                "action": "finding_optimal_k",
                "status": "completed",
                "optimal_k": n_clusters,
                "score": best_score
            }

        # Run final clustering
        yield {"action": "clustering", "method": "kmeans", "status": "started"}
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(self.feature_matrix)

        # Organize results
        repo_list = list(self.repositories.keys())
        clusters = defaultdict(list)

        for i, label in enumerate(labels):
            clusters[int(label)].append(repo_list[i])

        self.clusters = dict(clusters)

        # Generate cluster descriptions
        for cluster_id, repos in self.clusters.items():
            result = self._describe_cluster(cluster_id, repos)
            yield {
                "action": "cluster_result",
                "cluster": asdict(result)
            }

    def _describe_cluster(self, cluster_id: int, repos: List[str]) -> ClusterResult:
        """Generate description for a cluster."""
        # Find common characteristics
        all_languages = defaultdict(int)
        all_topics = defaultdict(int)
        has_tests = 0
        has_docs = 0

        for repo_path in repos:
            repo_data = self.repositories[repo_path]
            for lang, count in repo_data.get("languages", []):
                all_languages[lang] += 1
            for topic in repo_data.get("topics", []):
                all_topics[topic] += 1
            if repo_data.get("has_tests"):
                has_tests += 1
            if repo_data.get("has_docs"):
                has_docs += 1

        # Find most common language
        primary_language = None
        if all_languages:
            primary_language = max(all_languages, key=all_languages.get)

        # Find common topics
        common_topics = [
            topic for topic, count in all_topics.items()
            if count > len(repos) * 0.3  # Present in >30% of repos
        ]

        # Generate description
        description = f"Cluster of {len(repos)} repositories"
        if primary_language:
            description += f", primarily {primary_language}"
        if common_topics:
            description += f", focused on {', '.join(common_topics[:3])}"

        # Calculate coherence score (how similar repos are within cluster)
        if self.similarity_matrix is not None:
            repo_indices = [list(self.repositories.keys()).index(r) for r in repos]
            if len(repo_indices) > 1:
                cluster_similarities = []
                for i in range(len(repo_indices)):
                    for j in range(i + 1, len(repo_indices)):
                        cluster_similarities.append(
                            self.similarity_matrix[repo_indices[i], repo_indices[j]]
                        )
                coherence_score = np.mean(cluster_similarities) if cluster_similarities else 0.0
            else:
                coherence_score = 1.0
        else:
            coherence_score = 0.0

        return ClusterResult(
            cluster_id=cluster_id,
            repositories=repos,
            centroid_repo=repos[0] if repos else None,
            coherence_score=float(coherence_score),
            primary_language=primary_language,
            common_topics=common_topics,
            description=description
        )

    def _cluster_dbscan(self) -> Iterator[Dict]:
        """Perform DBSCAN clustering."""
        from sklearn.cluster import DBSCAN

        yield {"action": "clustering", "method": "dbscan", "status": "started"}

        # DBSCAN on similarity matrix
        dbscan = DBSCAN(eps=0.3, min_samples=2, metric="precomputed")
        # Convert similarity to distance
        distance_matrix = 1 - self.compute_similarity_matrix()
        labels = dbscan.fit_predict(distance_matrix)

        # Organize results
        repo_list = list(self.repositories.keys())
        clusters = defaultdict(list)
        noise_points = []

        for i, label in enumerate(labels):
            if label == -1:
                noise_points.append(repo_list[i])
            else:
                clusters[int(label)].append(repo_list[i])

        self.clusters = dict(clusters)

        # Report noise points
        if noise_points:
            yield {
                "action": "noise_detected",
                "count": len(noise_points),
                "repositories": noise_points,
                "description": "Repositories that don't fit into any cluster"
            }

        # Generate cluster descriptions
        for cluster_id, repos in self.clusters.items():
            result = self._describe_cluster(cluster_id, repos)
            yield {
                "action": "cluster_result",
                "cluster": asdict(result)
            }

    def _cluster_hierarchical(self, n_clusters: Optional[int]) -> Iterator[Dict]:
        """Perform hierarchical clustering."""
        from scipy.cluster.hierarchy import dendrogram, linkage, fcluster

        yield {"action": "clustering", "method": "hierarchical", "status": "started"}

        # Perform hierarchical clustering
        linkage_matrix = linkage(self.feature_matrix, method='ward')

        if n_clusters is None:
            # Use distance threshold
            threshold = 0.7 * max(linkage_matrix[:, 2])
            labels = fcluster(linkage_matrix, threshold, criterion='distance')
        else:
            labels = fcluster(linkage_matrix, n_clusters, criterion='maxclust')

        # Organize results
        repo_list = list(self.repositories.keys())
        clusters = defaultdict(list)

        for i, label in enumerate(labels):
            clusters[int(label) - 1].append(repo_list[i])  # fcluster uses 1-based indexing

        self.clusters = dict(clusters)

        # Generate cluster descriptions
        for cluster_id, repos in self.clusters.items():
            result = self._describe_cluster(cluster_id, repos)
            yield {
                "action": "cluster_result",
                "cluster": asdict(result)
            }

    def _cluster_network(self) -> Iterator[Dict]:
        """Perform network-based clustering using the existing network analysis."""
        # This would integrate with the network_analysis.py module
        yield {
            "action": "clustering",
            "method": "network",
            "status": "started",
            "note": "Using repository relationship network for clustering"
        }

        # Import and use the existing network analysis
        from ghops.integrations.network_analysis import RepositoryNetwork

        network = RepositoryNetwork()
        for repo_path, repo_data in self.repositories.items():
            network.add_repository(repo_data)

        # Build network
        network.build_network()

        # Find clusters using network community detection
        clusters = network.find_clusters()
        self.clusters = {}

        for cluster_id, cluster_name in enumerate(clusters):
            repos = clusters[cluster_name]
            self.clusters[cluster_id] = repos
            result = self._describe_cluster(cluster_id, repos)
            yield {
                "action": "cluster_result",
                "cluster": asdict(result)
            }


# Language mapping for detection
LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".jl": "Julia",
    ".m": "MATLAB",
    ".lua": "Lua",
    ".pl": "Perl",
    ".sh": "Shell",
    ".ps1": "PowerShell"
}

# Common words to filter
COMMON_WORDS = {
    'the', 'and', 'for', 'with', 'from', 'this', 'that', 'have', 'will',
    'your', 'which', 'when', 'what', 'where', 'there', 'their', 'than',
    'been', 'being', 'about', 'after', 'before', 'under', 'over'
}