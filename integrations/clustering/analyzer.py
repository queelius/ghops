"""
Advanced analysis tools for repository clustering.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Iterator
from collections import defaultdict
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class CodeBlock:
    """Represents a reusable code block."""
    hash: str
    content: str
    language: str
    file_path: str
    line_start: int
    line_end: int
    type: str  # "function", "class", "module"


@dataclass
class DuplicationReport:
    """Report of code duplication between repositories."""
    repo1: str
    repo2: str
    similarity_score: float
    shared_blocks: List[CodeBlock]
    total_shared_lines: int
    recommendation: str


class DuplicationAnalyzer:
    """Analyzes code duplication across repositories."""

    def __init__(self, min_block_size: int = 10):
        """Initialize duplication analyzer.

        Args:
            min_block_size: Minimum lines for a code block to be considered
        """
        self.min_block_size = min_block_size
        self.code_blocks = defaultdict(list)  # hash -> list of (repo, block)
        self.repo_hashes = defaultdict(set)   # repo -> set of hashes

    def analyze_repository(self, repo_path: str) -> Iterator[Dict]:
        """Analyze a repository for code blocks.

        Args:
            repo_path: Path to repository

        Yields:
            Progress updates
        """
        repo = Path(repo_path)
        if not repo.exists():
            yield {
                "action": "error",
                "repo": repo_path,
                "error": "Repository path does not exist"
            }
            return

        yield {
            "action": "analyzing",
            "repo": repo_path,
            "status": "started"
        }

        # Extract code blocks from various file types
        patterns = {
            "**/*.py": self._extract_python_blocks,
            "**/*.js": self._extract_javascript_blocks,
            "**/*.java": self._extract_java_blocks,
            "**/*.go": self._extract_go_blocks,
        }

        total_blocks = 0
        for pattern, extractor in patterns.items():
            for file_path in repo.glob(pattern):
                if self._should_skip_file(file_path):
                    continue

                try:
                    blocks = extractor(file_path)
                    for block in blocks:
                        block_hash = self._hash_block(block.content)
                        block.hash = block_hash
                        self.code_blocks[block_hash].append((repo_path, block))
                        self.repo_hashes[repo_path].add(block_hash)
                        total_blocks += 1

                        yield {
                            "action": "block_found",
                            "repo": repo_path,
                            "file": str(file_path.relative_to(repo)),
                            "block_type": block.type,
                            "lines": block.line_end - block.line_start
                        }
                except Exception as e:
                    yield {
                        "action": "error",
                        "repo": repo_path,
                        "file": str(file_path),
                        "error": str(e)
                    }

        yield {
            "action": "analyzing",
            "repo": repo_path,
            "status": "completed",
            "total_blocks": total_blocks
        }

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_dirs = {
            "node_modules", "venv", "env", ".git", "__pycache__",
            "dist", "build", ".pytest_cache", "target"
        }
        return any(part in skip_dirs for part in file_path.parts)

    def _hash_block(self, content: str) -> str:
        """Generate hash for code block."""
        # Normalize whitespace and remove comments for better matching
        normalized = re.sub(r'\s+', ' ', content)
        normalized = re.sub(r'#.*$', '', normalized, flags=re.MULTILINE)  # Python comments
        normalized = re.sub(r'//.*$', '', normalized, flags=re.MULTILINE)  # JS/Java comments
        return hashlib.md5(normalized.encode()).hexdigest()

    def _extract_python_blocks(self, file_path: Path) -> List[CodeBlock]:
        """Extract code blocks from Python file."""
        blocks = []
        try:
            content = file_path.read_text()
            lines = content.splitlines()

            # Find functions and classes
            import ast
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.end_lineno - node.lineno >= self.min_block_size:
                        block_content = '\n'.join(lines[node.lineno - 1:node.end_lineno])
                        blocks.append(CodeBlock(
                            hash="",  # Will be set later
                            content=block_content,
                            language="Python",
                            file_path=str(file_path),
                            line_start=node.lineno,
                            line_end=node.end_lineno,
                            type="function"
                        ))
                elif isinstance(node, ast.ClassDef):
                    if node.end_lineno - node.lineno >= self.min_block_size:
                        block_content = '\n'.join(lines[node.lineno - 1:node.end_lineno])
                        blocks.append(CodeBlock(
                            hash="",
                            content=block_content,
                            language="Python",
                            file_path=str(file_path),
                            line_start=node.lineno,
                            line_end=node.end_lineno,
                            type="class"
                        ))
        except Exception:
            pass  # Ignore files that can't be parsed

        return blocks

    def _extract_javascript_blocks(self, file_path: Path) -> List[CodeBlock]:
        """Extract code blocks from JavaScript file."""
        blocks = []
        try:
            content = file_path.read_text()
            lines = content.splitlines()

            # Simple regex-based extraction for functions
            function_pattern = r'function\s+(\w+)\s*\([^)]*\)\s*\{'
            class_pattern = r'class\s+(\w+)\s*(?:extends\s+\w+)?\s*\{'

            for match in re.finditer(function_pattern, content):
                start = content[:match.start()].count('\n') + 1
                # Find matching closing brace
                end = self._find_block_end(lines, start - 1)
                if end - start >= self.min_block_size:
                    blocks.append(CodeBlock(
                        hash="",
                        content='\n'.join(lines[start - 1:end]),
                        language="JavaScript",
                        file_path=str(file_path),
                        line_start=start,
                        line_end=end,
                        type="function"
                    ))

            for match in re.finditer(class_pattern, content):
                start = content[:match.start()].count('\n') + 1
                end = self._find_block_end(lines, start - 1)
                if end - start >= self.min_block_size:
                    blocks.append(CodeBlock(
                        hash="",
                        content='\n'.join(lines[start - 1:end]),
                        language="JavaScript",
                        file_path=str(file_path),
                        line_start=start,
                        line_end=end,
                        type="class"
                    ))
        except Exception:
            pass

        return blocks

    def _extract_java_blocks(self, file_path: Path) -> List[CodeBlock]:
        """Extract code blocks from Java file."""
        # Similar to JavaScript but with Java-specific patterns
        return self._extract_javascript_blocks(file_path)  # Simplified for now

    def _extract_go_blocks(self, file_path: Path) -> List[CodeBlock]:
        """Extract code blocks from Go file."""
        blocks = []
        try:
            content = file_path.read_text()
            lines = content.splitlines()

            # Extract Go functions
            func_pattern = r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\([^)]*\)'

            for match in re.finditer(func_pattern, content):
                start = content[:match.start()].count('\n') + 1
                end = self._find_block_end(lines, start - 1)
                if end - start >= self.min_block_size:
                    blocks.append(CodeBlock(
                        hash="",
                        content='\n'.join(lines[start - 1:end]),
                        language="Go",
                        file_path=str(file_path),
                        line_start=start,
                        line_end=end,
                        type="function"
                    ))
        except Exception:
            pass

        return blocks

    def _find_block_end(self, lines: List[str], start: int) -> int:
        """Find the end of a code block by matching braces."""
        brace_count = 0
        in_block = False

        for i in range(start, len(lines)):
            line = lines[i]
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_block = True
                elif char == '}':
                    brace_count -= 1
                    if in_block and brace_count == 0:
                        return i + 1

        return len(lines)

    def find_duplications(self) -> Iterator[DuplicationReport]:
        """Find duplications between repositories.

        Yields:
            Duplication reports
        """
        repos = list(self.repo_hashes.keys())

        for i in range(len(repos)):
            for j in range(i + 1, len(repos)):
                repo1, repo2 = repos[i], repos[j]
                shared_hashes = self.repo_hashes[repo1] & self.repo_hashes[repo2]

                if shared_hashes:
                    shared_blocks = []
                    total_lines = 0

                    for hash_val in shared_hashes:
                        for repo, block in self.code_blocks[hash_val]:
                            if repo == repo1:
                                shared_blocks.append(block)
                                total_lines += block.line_end - block.line_start
                                break

                    similarity = len(shared_hashes) / max(
                        len(self.repo_hashes[repo1]),
                        len(self.repo_hashes[repo2])
                    )

                    recommendation = self._generate_recommendation(similarity, total_lines)

                    yield DuplicationReport(
                        repo1=repo1,
                        repo2=repo2,
                        similarity_score=similarity,
                        shared_blocks=shared_blocks,
                        total_shared_lines=total_lines,
                        recommendation=recommendation
                    )

    def _generate_recommendation(self, similarity: float, shared_lines: int) -> str:
        """Generate recommendation based on duplication analysis."""
        if similarity > 0.7:
            return f"High duplication ({similarity:.1%}). Consider merging these repositories or extracting shared code into a library."
        elif similarity > 0.4:
            return f"Moderate duplication ({similarity:.1%}). Review shared code ({shared_lines} lines) for potential extraction."
        elif similarity > 0.2:
            return f"Some duplication ({similarity:.1%}). Monitor for increasing duplication over time."
        else:
            return f"Low duplication ({similarity:.1%}). Repositories are sufficiently distinct."


class ConsolidationAdvisor:
    """Provides consolidation recommendations for repositories."""

    def __init__(self, clusterer, duplication_analyzer):
        """Initialize consolidation advisor.

        Args:
            clusterer: Repository clusterer instance
            duplication_analyzer: Duplication analyzer instance
        """
        self.clusterer = clusterer
        self.duplication_analyzer = duplication_analyzer

    def generate_suggestions(self) -> Iterator[Dict]:
        """Generate consolidation suggestions.

        Yields:
            Consolidation suggestions
        """
        # Analyze clusters for consolidation opportunities
        for cluster_id, repos in self.clusterer.clusters.items():
            if len(repos) < 2:
                continue

            # Check for high similarity within cluster
            suggestions = self._analyze_cluster_for_consolidation(cluster_id, repos)
            for suggestion in suggestions:
                yield {
                    "action": "consolidation_suggestion",
                    "suggestion": asdict(suggestion)
                }

    def _analyze_cluster_for_consolidation(
        self, cluster_id: int, repos: List[str]
    ) -> List[ConsolidationSuggestion]:
        """Analyze a cluster for consolidation opportunities."""
        suggestions = []

        # Find highly similar repository pairs
        for i in range(len(repos)):
            for j in range(i + 1, len(repos)):
                repo1, repo2 = repos[i], repos[j]

                # Get similarity from clusterer's similarity matrix
                if self.clusterer.similarity_matrix is not None:
                    repo_list = list(self.clusterer.repositories.keys())
                    idx1 = repo_list.index(repo1)
                    idx2 = repo_list.index(repo2)
                    similarity = self.clusterer.similarity_matrix[idx1, idx2]

                    if similarity > 0.8:  # High similarity threshold
                        suggestion = self._create_consolidation_suggestion(
                            [repo1, repo2], similarity
                        )
                        suggestions.append(suggestion)

        # Check for small, similar repos that could be combined
        small_repos = [
            r for r in repos
            if self.clusterer.repositories[r].get("file_count", 0) < 50
        ]

        if len(small_repos) > 2:
            # Suggest combining small related repos
            suggestion = self._create_consolidation_suggestion(
                small_repos, 0.7  # Moderate confidence
            )
            suggestion.rationale = (
                f"These {len(small_repos)} small repositories share similar "
                f"characteristics and could be combined into a single project "
                f"with multiple modules."
            )
            suggestions.append(suggestion)

        return suggestions

    def _create_consolidation_suggestion(
        self, repos: List[str], confidence: float
    ) -> ConsolidationSuggestion:
        """Create a consolidation suggestion."""
        # Find common patterns in repo names
        names = [Path(r).name for r in repos]
        common_prefix = self._find_common_prefix(names)

        suggested_name = common_prefix if common_prefix else "consolidated_project"

        # Estimate effort based on repo sizes
        total_files = sum(
            self.clusterer.repositories[r].get("file_count", 0)
            for r in repos
        )

        if total_files < 100:
            effort = "low"
        elif total_files < 500:
            effort = "medium"
        else:
            effort = "high"

        # Generate benefits
        benefits = [
            "Reduced maintenance overhead",
            "Simplified dependency management",
            "Easier code reuse",
            "Unified testing and CI/CD",
            "Clearer project structure"
        ]

        # Find common code blocks
        common_blocks = []
        if hasattr(self.duplication_analyzer, 'repo_hashes'):
            all_hashes = set()
            for repo in repos:
                all_hashes.update(self.duplication_analyzer.repo_hashes.get(repo, set()))

            # Find hashes present in multiple repos
            for hash_val in all_hashes:
                repos_with_hash = [
                    r for r in repos
                    if hash_val in self.duplication_analyzer.repo_hashes.get(r, set())
                ]
                if len(repos_with_hash) > 1:
                    # Get the actual block
                    for repo, block in self.duplication_analyzer.code_blocks.get(hash_val, []):
                        if repo in repos:
                            common_blocks.append(f"{block.type}: {block.file_path}")
                            break

        return ConsolidationSuggestion(
            repositories=repos,
            confidence=confidence,
            rationale=f"High similarity ({confidence:.1%}) between repositories suggests consolidation opportunity",
            common_code_blocks=common_blocks[:10],  # Limit to 10 examples
            suggested_name=suggested_name,
            estimated_effort=effort,
            benefits=benefits
        )

    def _find_common_prefix(self, strings: List[str]) -> str:
        """Find common prefix among strings."""
        if not strings:
            return ""

        shortest = min(strings, key=len)
        for i, char in enumerate(shortest):
            for string in strings:
                if string[i] != char:
                    return shortest[:i].rstrip("-_")

        return shortest