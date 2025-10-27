"""
Clustering algorithms for repository analysis.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Iterator
from abc import ABC, abstractmethod
from dataclasses import dataclass
import json


@dataclass
class ClusteringConfig:
    """Configuration for clustering algorithms."""
    min_cluster_size: int = 2
    max_iterations: int = 100
    tolerance: float = 1e-4
    random_state: int = 42


class ClusteringAlgorithm(ABC):
    """Base class for clustering algorithms."""

    def __init__(self, config: Optional[ClusteringConfig] = None):
        """Initialize clustering algorithm.

        Args:
            config: Algorithm configuration
        """
        self.config = config or ClusteringConfig()
        self.labels_ = None
        self.n_clusters_ = None

    @abstractmethod
    def fit(self, X: np.ndarray) -> 'ClusteringAlgorithm':
        """Fit the clustering algorithm to data.

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Self for chaining
        """
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict cluster labels for data.

        Args:
            X: Feature matrix

        Returns:
            Cluster labels
        """
        pass

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit and predict in one step.

        Args:
            X: Feature matrix

        Returns:
            Cluster labels
        """
        return self.fit(X).predict(X)


class KMeansClustering(ClusteringAlgorithm):
    """K-Means clustering implementation."""

    def __init__(self, n_clusters: int, config: Optional[ClusteringConfig] = None):
        """Initialize K-Means clustering.

        Args:
            n_clusters: Number of clusters
            config: Algorithm configuration
        """
        super().__init__(config)
        self.n_clusters = n_clusters
        self.centroids_ = None
        self.inertia_ = None

    def fit(self, X: np.ndarray) -> 'KMeansClustering':
        """Fit K-Means to data."""
        try:
            from sklearn.cluster import KMeans

            kmeans = KMeans(
                n_clusters=self.n_clusters,
                max_iter=self.config.max_iterations,
                tol=self.config.tolerance,
                random_state=self.config.random_state,
                n_init=10
            )

            kmeans.fit(X)
            self.labels_ = kmeans.labels_
            self.centroids_ = kmeans.cluster_centers_
            self.inertia_ = kmeans.inertia_
            self.n_clusters_ = self.n_clusters

        except ImportError:
            # Fallback to simple implementation
            self._simple_kmeans(X)

        return self

    def _simple_kmeans(self, X: np.ndarray):
        """Simple K-Means implementation without sklearn."""
        n_samples, n_features = X.shape

        # Initialize centroids randomly
        np.random.seed(self.config.random_state)
        indices = np.random.choice(n_samples, self.n_clusters, replace=False)
        self.centroids_ = X[indices].copy()

        for _ in range(self.config.max_iterations):
            # Assign points to nearest centroid
            distances = np.zeros((n_samples, self.n_clusters))
            for k in range(self.n_clusters):
                distances[:, k] = np.linalg.norm(X - self.centroids_[k], axis=1)

            new_labels = np.argmin(distances, axis=1)

            # Update centroids
            new_centroids = np.zeros_like(self.centroids_)
            for k in range(self.n_clusters):
                mask = new_labels == k
                if np.any(mask):
                    new_centroids[k] = X[mask].mean(axis=0)
                else:
                    # Empty cluster, reinitialize
                    new_centroids[k] = X[np.random.randint(n_samples)]

            # Check convergence
            if np.allclose(self.centroids_, new_centroids, atol=self.config.tolerance):
                break

            self.centroids_ = new_centroids
            self.labels_ = new_labels

        # Calculate inertia
        self.inertia_ = sum(
            np.linalg.norm(X[self.labels_ == k] - self.centroids_[k]) ** 2
            for k in range(self.n_clusters)
        )
        self.n_clusters_ = self.n_clusters

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict cluster labels for new data."""
        if self.centroids_ is None:
            raise ValueError("Model must be fitted before prediction")

        distances = np.zeros((X.shape[0], self.n_clusters))
        for k in range(self.n_clusters):
            distances[:, k] = np.linalg.norm(X - self.centroids_[k], axis=1)

        return np.argmin(distances, axis=1)


class DBSCANClustering(ClusteringAlgorithm):
    """DBSCAN clustering implementation."""

    def __init__(self, eps: float = 0.3, min_samples: int = 2,
                 config: Optional[ClusteringConfig] = None):
        """Initialize DBSCAN clustering.

        Args:
            eps: Maximum distance between samples in neighborhood
            min_samples: Minimum samples in neighborhood for core point
            config: Algorithm configuration
        """
        super().__init__(config)
        self.eps = eps
        self.min_samples = min_samples
        self.core_sample_indices_ = None

    def fit(self, X: np.ndarray) -> 'DBSCANClustering':
        """Fit DBSCAN to data."""
        try:
            from sklearn.cluster import DBSCAN

            dbscan = DBSCAN(
                eps=self.eps,
                min_samples=self.min_samples
            )

            self.labels_ = dbscan.fit_predict(X)
            self.core_sample_indices_ = dbscan.core_sample_indices_
            self.n_clusters_ = len(set(self.labels_)) - (1 if -1 in self.labels_ else 0)

        except ImportError:
            # Fallback to simple implementation
            self._simple_dbscan(X)

        return self

    def _simple_dbscan(self, X: np.ndarray):
        """Simple DBSCAN implementation without sklearn."""
        n_samples = X.shape[0]
        labels = np.full(n_samples, -1)  # -1 for noise

        # Find neighbors for each point
        neighbors = []
        for i in range(n_samples):
            distances = np.linalg.norm(X - X[i], axis=1)
            neighbors.append(np.where(distances <= self.eps)[0])

        # Find core points
        core_points = [i for i, neigh in enumerate(neighbors)
                      if len(neigh) >= self.min_samples]
        self.core_sample_indices_ = np.array(core_points)

        # Assign clusters
        cluster_id = 0
        visited = set()

        for core_point in core_points:
            if core_point in visited:
                continue

            # Start new cluster
            cluster = set()
            queue = [core_point]

            while queue:
                point = queue.pop(0)
                if point in visited:
                    continue

                visited.add(point)
                cluster.add(point)

                # Add neighbors of core points to queue
                if point in core_points:
                    for neighbor in neighbors[point]:
                        if neighbor not in visited:
                            queue.append(neighbor)

            # Assign cluster labels
            for point in cluster:
                labels[point] = cluster_id

            cluster_id += 1

        self.labels_ = labels
        self.n_clusters_ = cluster_id

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict is not available for DBSCAN."""
        raise NotImplementedError("DBSCAN does not support prediction on new data")


class HierarchicalClustering(ClusteringAlgorithm):
    """Hierarchical clustering implementation."""

    def __init__(self, n_clusters: Optional[int] = None,
                 distance_threshold: Optional[float] = None,
                 linkage: str = 'ward',
                 config: Optional[ClusteringConfig] = None):
        """Initialize hierarchical clustering.

        Args:
            n_clusters: Number of clusters
            distance_threshold: Distance threshold for clustering
            linkage: Linkage method ('ward', 'complete', 'average', 'single')
            config: Algorithm configuration
        """
        super().__init__(config)
        self.n_clusters = n_clusters
        self.distance_threshold = distance_threshold
        self.linkage = linkage
        self.linkage_matrix_ = None

    def fit(self, X: np.ndarray) -> 'HierarchicalClustering':
        """Fit hierarchical clustering to data."""
        try:
            from sklearn.cluster import AgglomerativeClustering

            clustering = AgglomerativeClustering(
                n_clusters=self.n_clusters,
                distance_threshold=self.distance_threshold,
                linkage=self.linkage
            )

            self.labels_ = clustering.fit_predict(X)
            self.n_clusters_ = clustering.n_clusters_

        except ImportError:
            # Fallback to scipy
            self._scipy_hierarchical(X)

        return self

    def _scipy_hierarchical(self, X: np.ndarray):
        """Hierarchical clustering using scipy."""
        try:
            from scipy.cluster.hierarchy import linkage, fcluster
            from scipy.spatial.distance import pdist

            # Compute linkage matrix
            distance_matrix = pdist(X)
            self.linkage_matrix_ = linkage(distance_matrix, method=self.linkage)

            # Extract clusters
            if self.n_clusters is not None:
                self.labels_ = fcluster(
                    self.linkage_matrix_,
                    self.n_clusters,
                    criterion='maxclust'
                ) - 1  # Convert to 0-based indexing
            elif self.distance_threshold is not None:
                self.labels_ = fcluster(
                    self.linkage_matrix_,
                    self.distance_threshold,
                    criterion='distance'
                ) - 1
            else:
                # Default: use distance threshold at 70% of max
                threshold = 0.7 * self.linkage_matrix_[:, 2].max()
                self.labels_ = fcluster(
                    self.linkage_matrix_,
                    threshold,
                    criterion='distance'
                ) - 1

            self.n_clusters_ = len(set(self.labels_))

        except ImportError:
            raise ImportError("Either sklearn or scipy is required for hierarchical clustering")

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict is not directly available for hierarchical clustering."""
        raise NotImplementedError("Hierarchical clustering does not support prediction on new data")

    def get_dendrogram_data(self) -> Dict:
        """Get data for dendrogram visualization."""
        if self.linkage_matrix_ is None:
            return {}

        return {
            'linkage_matrix': self.linkage_matrix_.tolist(),
            'n_clusters': self.n_clusters_,
            'linkage_method': self.linkage
        }


class NetworkClustering(ClusteringAlgorithm):
    """Network-based clustering using graph algorithms."""

    def __init__(self, similarity_threshold: float = 0.3,
                 config: Optional[ClusteringConfig] = None):
        """Initialize network clustering.

        Args:
            similarity_threshold: Minimum similarity for edge creation
            config: Algorithm configuration
        """
        super().__init__(config)
        self.similarity_threshold = similarity_threshold
        self.communities_ = None

    def fit(self, X: np.ndarray) -> 'NetworkClustering':
        """Fit network clustering to data."""
        # Compute similarity matrix
        from sklearn.metrics.pairwise import cosine_similarity
        similarity_matrix = cosine_similarity(X)

        # Create adjacency matrix
        adjacency = (similarity_matrix >= self.similarity_threshold).astype(int)
        np.fill_diagonal(adjacency, 0)  # No self-loops

        # Find connected components
        self.labels_ = self._find_communities(adjacency)
        self.n_clusters_ = len(set(self.labels_))

        return self

    def _find_communities(self, adjacency: np.ndarray) -> np.ndarray:
        """Find communities using connected components."""
        n_nodes = adjacency.shape[0]
        labels = np.full(n_nodes, -1)
        cluster_id = 0

        for i in range(n_nodes):
            if labels[i] != -1:
                continue

            # BFS to find connected component
            queue = [i]
            while queue:
                node = queue.pop(0)
                if labels[node] != -1:
                    continue

                labels[node] = cluster_id

                # Add neighbors
                neighbors = np.where(adjacency[node] > 0)[0]
                queue.extend(neighbors)

            cluster_id += 1

        return labels

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict is not available for network clustering."""
        raise NotImplementedError("Network clustering does not support prediction on new data")


class EnsembleClustering:
    """Ensemble clustering combining multiple algorithms."""

    def __init__(self, algorithms: List[ClusteringAlgorithm]):
        """Initialize ensemble clustering.

        Args:
            algorithms: List of clustering algorithms to combine
        """
        self.algorithms = algorithms
        self.consensus_labels_ = None
        self.n_clusters_ = None

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit all algorithms and combine results.

        Args:
            X: Feature matrix

        Returns:
            Consensus cluster labels
        """
        # Get predictions from all algorithms
        all_labels = []
        for algo in self.algorithms:
            try:
                labels = algo.fit_predict(X)
                all_labels.append(labels)
            except Exception as e:
                print(f"Warning: {algo.__class__.__name__} failed: {e}")

        if not all_labels:
            raise ValueError("All clustering algorithms failed")

        # Combine using consensus
        self.consensus_labels_ = self._consensus_clustering(all_labels)
        self.n_clusters_ = len(set(self.consensus_labels_))

        return self.consensus_labels_

    def _consensus_clustering(self, all_labels: List[np.ndarray]) -> np.ndarray:
        """Combine multiple clustering results using consensus."""
        n_samples = len(all_labels[0])

        # Build co-association matrix
        co_assoc = np.zeros((n_samples, n_samples))

        for labels in all_labels:
            for i in range(n_samples):
                for j in range(i + 1, n_samples):
                    if labels[i] == labels[j] and labels[i] != -1:
                        co_assoc[i, j] += 1
                        co_assoc[j, i] += 1

        # Normalize
        co_assoc /= len(all_labels)

        # Apply hierarchical clustering to co-association matrix
        from scipy.cluster.hierarchy import linkage, fcluster

        # Convert similarity to distance
        distance_matrix = 1 - co_assoc
        linkage_matrix = linkage(distance_matrix[np.triu_indices(n_samples, k=1)],
                                method='average')

        # Determine optimal number of clusters
        # Use elbow method on linkage distances
        distances = linkage_matrix[:, 2]
        diff = np.diff(distances)
        elbow = np.argmax(diff) + 1
        n_clusters = min(max(2, n_samples - elbow), n_samples // 2)

        return fcluster(linkage_matrix, n_clusters, criterion='maxclust') - 1