# Repository Clustering Integration

Advanced clustering and duplication analysis for repository portfolios. This integration helps identify related repositories, find duplicate code, and suggest consolidation opportunities.

## Features

### 🔍 Multiple Clustering Algorithms
- **K-Means**: Fast clustering with automatic k detection using silhouette scoring
- **DBSCAN**: Density-based clustering for finding arbitrarily shaped clusters
- **Hierarchical**: Tree-based clustering with dendrogram visualization
- **Network**: Graph-based clustering using repository relationships
- **Ensemble**: Combine multiple algorithms for consensus clustering

### 📊 Code Duplication Analysis
- Function and class-level code block extraction
- Cross-repository duplicate detection
- Similarity scoring with actionable recommendations
- Support for Python, JavaScript, Java, and Go

### 💡 Consolidation Suggestions
- Intelligent repository consolidation recommendations
- Confidence scoring for suggestions
- Effort estimation (low/medium/high)
- Specific benefits and rationale

## Installation

The clustering integration requires additional dependencies:

```bash
pip install scikit-learn scipy rapidfuzz numpy
```

## Usage

### Basic Clustering

```bash
# Analyze repositories in current directory
ghops cluster analyze

# Use specific clustering method
ghops cluster analyze --method kmeans --n-clusters 5

# Analyze specific directories
ghops cluster analyze -p ~/projects -p ~/work -r

# Output to file
ghops cluster analyze -o clusters.jsonl

# Pretty display
ghops cluster analyze --pretty
```

### Find Duplicate Code

```bash
# Find duplicates in current directory
ghops cluster find-duplicates -r

# Set minimum similarity threshold
ghops cluster find-duplicates --min-similarity 0.7

# Analyze specific repositories
ghops cluster find-duplicates -p repo1 -p repo2 -p repo3
```

### Consolidation Suggestions

```bash
# Get consolidation suggestions
ghops cluster suggest-consolidation -r

# Set confidence threshold
ghops cluster suggest-consolidation --confidence 0.8

# Pretty display with detailed recommendations
ghops cluster suggest-consolidation --pretty
```

### Export Results

```bash
# Export as JSON
ghops cluster export -o results.json

# Export as interactive HTML visualization
ghops cluster export -f html -o visualization.html

# Export as GraphML for graph tools
ghops cluster export -f graphml -o graph.graphml
```

## JSONL Output Format

All commands output JSONL by default for Unix pipeline compatibility:

```bash
# Find Python repositories with high duplication
ghops cluster find-duplicates | jq 'select(.similarity > 0.8)'

# Get cluster statistics
ghops cluster analyze | jq 'select(.action == "cluster_result") | .cluster'

# Chain with other ghops commands
ghops list -t "lang:python" | ghops cluster analyze --stdin
```

## Output Schema

### Cluster Result
```json
{
  "action": "cluster_result",
  "cluster": {
    "cluster_id": 0,
    "repositories": ["repo1", "repo2"],
    "coherence_score": 0.85,
    "primary_language": "Python",
    "common_topics": ["api", "web"],
    "description": "Cluster of 2 repositories, primarily Python"
  }
}
```

### Duplication Report
```json
{
  "repo1": "/path/to/repo1",
  "repo2": "/path/to/repo2",
  "similarity": 0.75,
  "shared_lines": 450,
  "recommendation": "High duplication (75%). Consider merging..."
}
```

### Consolidation Suggestion
```json
{
  "repositories": ["repo1", "repo2", "repo3"],
  "confidence": 0.82,
  "suggested_name": "consolidated_project",
  "estimated_effort": "medium",
  "rationale": "High similarity (82%) between repositories...",
  "benefits": [
    "Reduced maintenance overhead",
    "Simplified dependency management",
    "Easier code reuse"
  ]
}
```

## Examples

### Morning Maintenance Routine

```bash
#!/bin/bash
# Find and handle duplicate code
ghops cluster find-duplicates -r | \
  jq 'select(.similarity > 0.7)' | \
  while read -r dup; do
    echo "High duplication found: $dup"
    # Take action based on recommendation
  done
```

### Portfolio Analysis

```bash
# Analyze entire portfolio and generate report
ghops cluster analyze -r -o analysis.jsonl
ghops cluster find-duplicates -r -o duplicates.jsonl
ghops cluster suggest-consolidation -r -o suggestions.jsonl

# Generate HTML report
ghops cluster export -f html -o portfolio-analysis.html
```

### Integration with CI/CD

```yaml
# GitHub Actions example
- name: Check for code duplication
  run: |
    ghops cluster find-duplicates -r | \
    jq 'select(.similarity > 0.8)' | \
    jq -s 'if length > 0 then error("High duplication detected") else empty end'
```

## Advanced Features

### Custom Clustering Configuration

Create a configuration file for fine-tuned clustering:

```json
{
  "clustering": {
    "min_cluster_size": 2,
    "max_iterations": 100,
    "tolerance": 0.0001,
    "features": {
      "use_language": true,
      "use_dependencies": true,
      "use_readme": true,
      "use_topics": true
    }
  },
  "duplication": {
    "min_block_size": 10,
    "languages": ["python", "javascript", "go"],
    "ignore_patterns": ["test_*", "*_test"]
  }
}
```

### Ensemble Clustering

Combine multiple algorithms for better results:

```python
from ghops.integrations.clustering import EnsembleClustering
from ghops.integrations.clustering import KMeansClustering, DBSCANClustering

# Create ensemble
ensemble = EnsembleClustering([
    KMeansClustering(n_clusters=5),
    DBSCANClustering(eps=0.3),
    HierarchicalClustering(n_clusters=5)
])

# Get consensus clustering
labels = ensemble.fit_predict(feature_matrix)
```

## Integration with ghops Core

The clustering integration seamlessly works with ghops core commands:

```bash
# Cluster only Python repositories
ghops list -t "lang:python" | \
  jq -r '.path' | \
  xargs ghops cluster analyze --input-list

# Find duplicates in repositories with issues
ghops query "open_issues > 0" | \
  jq -r '.path' | \
  xargs ghops cluster find-duplicates --input-list

# Export clusters as ghops catalog tags
ghops cluster analyze | \
  jq 'select(.action == "cluster_result")' | \
  ghops catalog import --format cluster
```

## Performance Considerations

- **Memory Usage**: Feature matrix size is O(n_repos × n_features)
- **Time Complexity**: K-means is O(n × k × iterations), DBSCAN is O(n²)
- **Parallelization**: Code block extraction is parallelized by default
- **Caching**: Results are cached in `.ghops/cache/clustering/`

## Troubleshooting

### Large Repository Collections

For >1000 repositories, use sampling or filtering:

```bash
# Sample 100 random repositories
ghops list | shuf -n 100 | ghops cluster analyze --stdin

# Filter by size
ghops list | jq 'select(.file_count < 1000)' | ghops cluster analyze --stdin
```

### Memory Issues

Reduce feature dimensions or use network clustering:

```bash
# Use lightweight network clustering
ghops cluster analyze --method network

# Disable README analysis
ghops cluster analyze --no-readme-analysis
```

## Contributing

See the main ghops contributing guide. Key areas for improvement:

1. Additional language support for code block extraction
2. More sophisticated consolidation algorithms
3. Integration with code quality metrics
4. Machine learning-based similarity detection
5. Real-time clustering updates