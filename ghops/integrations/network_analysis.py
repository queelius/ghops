"""
Repository network analysis plugin.

Builds a graph of repository relationships based on:
- Keyword similarity
- README semantic similarity
- Direct repository links/references
- Shared dependencies
- Common topics/tags
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
import math

import numpy as np
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class RepositoryNetwork:
    """Analyzes relationships between repositories to build a network graph."""
    
    def __init__(self, config: Optional[Dict[str, float]] = None):
        """Initialize the network analyzer with weight configuration.
        
        Args:
            config: Weight configuration for different link types.
                   Defaults to equal weights if not provided.
        """
        self.config = config or self.get_default_config()
        self.nodes = {}  # repo_path -> repo_data
        self.edges = defaultdict(lambda: defaultdict(float))  # source -> target -> weight
        self.link_details = defaultdict(lambda: defaultdict(dict))  # source -> target -> {type: score}
        
    @staticmethod
    def get_default_config() -> Dict[str, float]:
        """Get default weight configuration for link types."""
        return {
            'keyword_weight': 0.3,
            'readme_weight': 0.25,
            'link_weight': 0.2,
            'dependency_weight': 0.15,
            'topic_weight': 0.1,
            'min_link_strength': 0.1,  # Minimum strength to create an edge
        }
    
    def add_repository(self, repo_data: Dict[str, Any]):
        """Add a repository to the network.
        
        Args:
            repo_data: Repository metadata including path, name, description, etc.
        """
        path = repo_data.get('path', repo_data.get('name'))
        if not path:
            return
        
        self.nodes[path] = repo_data
    
    def build_network(self, progress_callback=None):
        """Build the network by computing all edge weights.
        
        Args:
            progress_callback: Optional callback for progress updates.
        """
        repo_list = list(self.nodes.keys())
        total = len(repo_list) * (len(repo_list) - 1) // 2
        processed = 0
        
        for i, repo1 in enumerate(repo_list):
            for repo2 in repo_list[i+1:]:
                if progress_callback:
                    progress_callback(processed, total, f"Analyzing {repo1} <-> {repo2}")
                
                # Calculate different types of similarity
                scores = {}
                
                # Keyword similarity
                scores['keywords'] = self._compute_keyword_similarity(repo1, repo2)
                
                # README similarity (if available)
                scores['readme'] = self._compute_readme_similarity(repo1, repo2)
                
                # Direct links between repos
                scores['links'] = self._compute_link_score(repo1, repo2)
                
                # Shared dependencies
                scores['dependencies'] = self._compute_dependency_similarity(repo1, repo2)
                
                # Topic/tag similarity
                scores['topics'] = self._compute_topic_similarity(repo1, repo2)
                
                # Compute weighted total
                total_weight = sum(
                    scores.get(key, 0) * self.config.get(f'{key}_weight', 0)
                    for key in ['keywords', 'readme', 'links', 'dependencies', 'topics']
                )
                
                if total_weight >= self.config['min_link_strength']:
                    self.edges[repo1][repo2] = total_weight
                    self.edges[repo2][repo1] = total_weight
                    self.link_details[repo1][repo2] = scores
                    self.link_details[repo2][repo1] = scores
                
                processed += 1
        
        if progress_callback:
            progress_callback(total, total, "Network analysis complete")
    
    def _compute_keyword_similarity(self, repo1: str, repo2: str) -> float:
        """Compute keyword similarity between two repositories.
        
        Uses repository names, descriptions, and topics for keyword extraction.
        """
        data1 = self.nodes.get(repo1, {})
        data2 = self.nodes.get(repo2, {})
        
        # Extract keywords from various fields
        keywords1 = self._extract_keywords(data1)
        keywords2 = self._extract_keywords(data2)
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # Compute Jaccard similarity
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        
        if not union:
            return 0.0
        
        jaccard = len(intersection) / len(union)
        
        # Also consider fuzzy matching for similar keywords
        fuzzy_score = 0
        for k1 in keywords1:
            for k2 in keywords2:
                if k1 != k2:
                    similarity = fuzz.ratio(k1, k2) / 100.0
                    if similarity > 0.8:  # High similarity threshold
                        fuzzy_score += similarity
        
        # Normalize fuzzy score
        if keywords1 and keywords2:
            fuzzy_score = fuzzy_score / (len(keywords1) * len(keywords2))
        
        # Combine exact and fuzzy matching
        return 0.7 * jaccard + 0.3 * fuzzy_score
    
    def _extract_keywords(self, repo_data: Dict) -> Set[str]:
        """Extract keywords from repository metadata."""
        keywords = set()
        
        # From name (split on common separators)
        name = repo_data.get('name', '')
        if name:
            parts = re.split(r'[-_\s]+', name.lower())
            keywords.update(p for p in parts if len(p) > 2)
        
        # From description
        desc = repo_data.get('description', '')
        if desc:
            # Simple keyword extraction - could be enhanced with NLP
            words = re.findall(r'\b[a-z]+\b', desc.lower())
            # Filter common words and short words
            keywords.update(w for w in words if len(w) > 3 and w not in COMMON_WORDS)
        
        # From topics/tags
        topics = repo_data.get('topics', [])
        if topics:
            keywords.update(t.lower() for t in topics)
        
        tags = repo_data.get('tags', [])
        if tags:
            for tag in tags:
                # Extract tag value after prefix (e.g., 'lang:python' -> 'python')
                if ':' in tag:
                    keywords.add(tag.split(':', 1)[1].lower())
                else:
                    keywords.add(tag.lower())
        
        # From language
        lang = repo_data.get('language', '')
        if lang:
            keywords.add(lang.lower())
        
        return keywords
    
    def _compute_readme_similarity(self, repo1: str, repo2: str) -> float:
        """Compute semantic similarity between README files.
        
        For now, uses keyword similarity from README content.
        Could be enhanced with embeddings for true semantic similarity.
        """
        data1 = self.nodes.get(repo1, {})
        data2 = self.nodes.get(repo2, {})
        
        readme1 = data1.get('readme_content', '')
        readme2 = data2.get('readme_content', '')
        
        if not readme1 or not readme2:
            return 0.0
        
        # Extract keywords from READMEs
        words1 = set(re.findall(r'\b[a-z]+\b', readme1.lower()))
        words2 = set(re.findall(r'\b[a-z]+\b', readme2.lower()))
        
        # Filter common words
        words1 = {w for w in words1 if len(w) > 3 and w not in COMMON_WORDS}
        words2 = {w for w in words2 if len(w) > 3 and w not in COMMON_WORDS}
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _compute_link_score(self, repo1: str, repo2: str) -> float:
        """Check if repositories directly link to each other.
        
        Looks for GitHub URLs in README, dependencies, etc.
        """
        data1 = self.nodes.get(repo1, {})
        data2 = self.nodes.get(repo2, {})
        
        score = 0.0
        
        # Check if repo1 links to repo2
        if self._repo_links_to(data1, data2):
            score += 0.5
        
        # Check if repo2 links to repo1
        if self._repo_links_to(data2, data1):
            score += 0.5
        
        return score
    
    def _repo_links_to(self, source: Dict, target: Dict) -> bool:
        """Check if source repository links to target repository."""
        target_url = target.get('remote', {}).get('url', '')
        target_name = target.get('name', '')
        
        if not target_url and not target_name:
            return False
        
        # Check in README
        readme = source.get('readme_content', '')
        if readme:
            if target_url and target_url in readme:
                return True
            if target_name and f'github.com/{target_name}' in readme.lower():
                return True
        
        # Check in package dependencies (for Python projects)
        package_data = source.get('package', {})
        if package_data:
            deps = package_data.get('dependencies', [])
            if target_name in deps:
                return True
        
        return False
    
    def _compute_dependency_similarity(self, repo1: str, repo2: str) -> float:
        """Compute similarity based on shared dependencies."""
        data1 = self.nodes.get(repo1, {})
        data2 = self.nodes.get(repo2, {})
        
        deps1 = set(data1.get('package', {}).get('dependencies', []))
        deps2 = set(data2.get('package', {}).get('dependencies', []))
        
        if not deps1 or not deps2:
            return 0.0
        
        intersection = deps1.intersection(deps2)
        union = deps1.union(deps2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _compute_topic_similarity(self, repo1: str, repo2: str) -> float:
        """Compute similarity based on shared topics/tags."""
        data1 = self.nodes.get(repo1, {})
        data2 = self.nodes.get(repo2, {})
        
        topics1 = set(data1.get('topics', []))
        topics2 = set(data2.get('topics', []))
        
        tags1 = set(data1.get('tags', []))
        tags2 = set(data2.get('tags', []))
        
        all1 = topics1.union(tags1)
        all2 = topics2.union(tags2)
        
        if not all1 or not all2:
            return 0.0
        
        intersection = all1.intersection(all2)
        union = all1.union(all2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def find_hubs(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Find hub repositories (highly connected).
        
        Args:
            top_n: Number of top hubs to return.
        
        Returns:
            List of (repo_path, centrality_score) tuples.
        """
        centrality = {}
        
        for repo in self.nodes:
            # Degree centrality weighted by edge strengths
            total_weight = sum(self.edges[repo].values())
            centrality[repo] = total_weight
        
        # Sort by centrality
        sorted_repos = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return sorted_repos[:top_n]
    
    def find_bridges(self) -> List[Tuple[str, str, float]]:
        """Find bridge connections between repository clusters.
        
        Returns:
            List of (repo1, repo2, importance) tuples for bridge edges.
        """
        bridges = []
        
        # Simple approach: find edges that connect repositories with few common neighbors
        for repo1 in self.edges:
            for repo2, weight in self.edges[repo1].items():
                if repo1 < repo2:  # Avoid duplicates
                    # Check common neighbors
                    neighbors1 = set(self.edges[repo1].keys())
                    neighbors2 = set(self.edges[repo2].keys())
                    common = neighbors1.intersection(neighbors2)
                    
                    # If few common neighbors, this might be a bridge
                    if len(common) < 2:
                        importance = weight * (1 + 1 / (len(common) + 1))
                        bridges.append((repo1, repo2, importance))
        
        # Sort by importance
        bridges.sort(key=lambda x: x[2], reverse=True)
        return bridges
    
    def find_clusters(self) -> Dict[str, List[str]]:
        """Find clusters of related repositories.
        
        Returns:
            Dictionary mapping cluster IDs to lists of repository paths.
        """
        # Simple community detection using connected components
        visited = set()
        clusters = {}
        cluster_id = 0
        
        for repo in self.nodes:
            if repo not in visited:
                # BFS to find connected component
                cluster = []
                queue = [repo]
                
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    
                    visited.add(current)
                    cluster.append(current)
                    
                    # Add strongly connected neighbors
                    for neighbor, weight in self.edges[current].items():
                        if weight > self.config['min_link_strength'] * 2:  # Strong connections only
                            if neighbor not in visited:
                                queue.append(neighbor)
                
                if len(cluster) > 1:  # Only keep clusters with multiple repos
                    clusters[f"cluster_{cluster_id}"] = cluster
                    cluster_id += 1
        
        return clusters
    
    def export_to_json(self) -> Dict:
        """Export network data to JSON format for visualization."""
        nodes_list = []
        edges_list = []
        
        # Export nodes
        for path, data in self.nodes.items():
            node = {
                'id': path,
                'label': data.get('name', path),
                'language': data.get('language', 'unknown'),
                'stars': data.get('stars', 0),
                'topics': data.get('topics', []),
                'description': data.get('description', ''),
            }
            nodes_list.append(node)
        
        # Export edges
        seen = set()
        for source in self.edges:
            for target, weight in self.edges[source].items():
                edge_key = tuple(sorted([source, target]))
                if edge_key not in seen:
                    seen.add(edge_key)
                    edge = {
                        'source': source,
                        'target': target,
                        'weight': weight,
                        'details': self.link_details[source][target],
                    }
                    edges_list.append(edge)
        
        return {
            'nodes': nodes_list,
            'edges': edges_list,
            'metadata': {
                'total_nodes': len(nodes_list),
                'total_edges': len(edges_list),
                'config': self.config,
            }
        }
    
    def export_to_html(self, output_path: str):
        """Export network visualization to interactive HTML.
        
        Args:
            output_path: Path to save the HTML file.
        """
        network_data = self.export_to_json()
        
        html_template = '''<!DOCTYPE html>
<html>
<head>
    <title>Repository Network Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        #graph {{ width: 100%; height: 600px; border: 1px solid #ccc; }}
        .node {{ stroke: #fff; stroke-width: 1.5px; cursor: pointer; }}
        .link {{ stroke: #999; stroke-opacity: 0.6; }}
        .node-label {{ font-size: 10px; pointer-events: none; }}
        #info {{ margin-top: 20px; padding: 10px; background: #f0f0f0; }}
        .controls {{ margin-bottom: 10px; }}
        .controls label {{ margin-right: 10px; }}
    </style>
</head>
<body>
    <h1>Repository Network Graph</h1>
    <div class="controls">
        <label>Min Link Strength: <input type="range" id="linkStrength" min="0" max="1" step="0.05" value="0.1"></label>
        <label>Show Labels: <input type="checkbox" id="showLabels" checked></label>
    </div>
    <svg id="graph"></svg>
    <div id="info">
        <h3>Network Statistics</h3>
        <p>Nodes: {total_nodes} | Edges: {total_edges}</p>
        <p>Click on nodes to see details</p>
    </div>
    
    <script>
        const data = {network_json};
        
        const width = window.innerWidth - 40;
        const height = 600;
        
        const svg = d3.select("#graph")
            .attr("width", width)
            .attr("height", height);
        
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.edges).id(d => d.id).distance(50))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append("g")
            .selectAll("line")
            .data(data.edges)
            .enter().append("line")
            .attr("class", "link")
            .style("stroke-width", d => Math.sqrt(d.weight * 10));
        
        const node = svg.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => 5 + Math.sqrt(d.stars))
            .style("fill", d => d3.schemeCategory10[hashCode(d.language) % 10])
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        const label = svg.append("g")
            .selectAll("text")
            .data(data.nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .text(d => d.label);
        
        node.on("click", function(event, d) {{
            const info = document.getElementById("info");
            info.innerHTML = `
                <h3>${{d.label}}</h3>
                <p><strong>Language:</strong> ${{d.language}}</p>
                <p><strong>Stars:</strong> ${{d.stars}}</p>
                <p><strong>Description:</strong> ${{d.description || 'No description'}}</p>
                <p><strong>Topics:</strong> ${{d.topics.join(', ') || 'None'}}</p>
            `;
        }});
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            label
                .attr("x", d => d.x + 10)
                .attr("y", d => d.y + 3);
        }});
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        function hashCode(str) {{
            let hash = 0;
            for (let i = 0; i < str.length; i++) {{
                hash = ((hash << 5) - hash) + str.charCodeAt(i);
                hash = hash & hash;
            }}
            return Math.abs(hash);
        }}
        
        // Controls
        document.getElementById("showLabels").addEventListener("change", function() {{
            label.style("display", this.checked ? "block" : "none");
        }});
        
        document.getElementById("linkStrength").addEventListener("input", function() {{
            const minStrength = parseFloat(this.value);
            link.style("display", d => d.weight >= minStrength ? "block" : "none");
        }});
    </script>
</body>
</html>'''
        
        # Format the HTML with data
        html_content = html_template.format(
            total_nodes=network_data['metadata']['total_nodes'],
            total_edges=network_data['metadata']['total_edges'],
            network_json=json.dumps(network_data, indent=2)
        )
        
        # Save to file
        Path(output_path).write_text(html_content)
        logger.info(f"Network visualization saved to {output_path}")


# Common words to filter out from keyword extraction
COMMON_WORDS = {
    'the', 'and', 'for', 'with', 'from', 'this', 'that', 'have', 'will',
    'your', 'which', 'when', 'what', 'where', 'there', 'their', 'than',
    'been', 'being', 'about', 'after', 'before', 'under', 'over', 'between',
    'through', 'during', 'without', 'within', 'along', 'following', 'behind',
    'since', 'until', 'while', 'beside', 'besides', 'into', 'onto', 'upon',
    'toward', 'towards', 'against', 'among', 'throughout', 'despite', 'towards',
    'upon', 'also', 'just', 'only', 'very', 'most', 'more', 'some', 'such',
    'each', 'every', 'these', 'those', 'them', 'other', 'another', 'much',
    'many', 'little', 'less', 'least', 'either', 'neither', 'both', 'half',
    'quite', 'such', 'rather', 'whether', 'whose', 'whom', 'then', 'thus',
    'therefore', 'however', 'moreover', 'furthermore', 'nonetheless', 'still',
    'already', 'always', 'never', 'often', 'sometimes', 'perhaps', 'maybe'
}