"""
Standard export component implementations.

These components provide the default export functionality and serve
as examples for custom component development.
"""

from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime

from .export_components import (
    BaseExportComponent,
    ExportContext,
    ExportFormat,
    ComponentConfig,
    register_component
)


@register_component()
class HeaderComponent(BaseExportComponent):
    """Renders document header with title and metadata."""
    
    @property
    def name(self) -> str:
        return "header"
    
    @property
    def description(self) -> str:
        return "Document header with title and generation info"
    
    def render(self, context: ExportContext) -> str:
        title = context.config.get('title', 'Repository Portfolio')
        subtitle = context.config.get('subtitle', '')
        
        lines = [f"# {title}"]
        if subtitle:
            lines.append(f"*{subtitle}*")
        lines.append("")
        lines.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return '\n'.join(lines)
    
    def render_html(self, context: ExportContext) -> str:
        title = context.config.get('title', 'Repository Portfolio')
        subtitle = context.config.get('subtitle', '')
        
        html = f"""
        <header class="export-header">
            <h1>{title}</h1>
            {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
            <p class="generated">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        """
        return html


@register_component()
class SummaryStatisticsComponent(BaseExportComponent):
    """Renders summary statistics about the repositories."""
    
    @property
    def name(self) -> str:
        return "summary_stats"
    
    @property
    def description(self) -> str:
        return "Summary statistics and metrics"
    
    def should_render(self, context: ExportContext) -> bool:
        # Only render if we have enough repos to make it interesting
        return super().should_render(context) and context.total_repos > 3
    
    def get_data(self, context: ExportContext) -> Dict[str, Any]:
        """Extract statistics data for rendering."""
        repos = context.repositories
        
        # Calculate statistics
        total_stars = sum(r.get('stargazers_count', 0) for r in repos)
        total_forks = sum(r.get('forks_count', 0) for r in repos)
        
        # Language distribution
        lang_dist = context.language_distribution
        top_languages = sorted(lang_dist.items(), key=lambda x: -x[1])[:5]
        
        # License distribution
        license_counts = Counter()
        for repo in repos:
            license_info = repo.get('license')
            if license_info and isinstance(license_info, dict):
                license_name = license_info.get('spdx_id') or license_info.get('key', 'Unknown')
            else:
                license_name = 'None'
            license_counts[license_name] += 1
        
        # Activity metrics
        active_repos = sum(1 for r in repos if not r.get('archived', False))
        private_repos = sum(1 for r in repos if r.get('private', False))
        
        return {
            'total_repos': context.total_repos,
            'total_stars': total_stars,
            'total_forks': total_forks,
            'top_languages': top_languages,
            'license_distribution': license_counts.most_common(5),
            'active_repos': active_repos,
            'private_repos': private_repos
        }
    
    def render(self, context: ExportContext) -> str:
        data = self.get_data(context)
        
        # Build output
        lines = ["## 📊 Summary Statistics", ""]
        
        # Basic metrics
        lines.append("### Metrics")
        lines.append(f"- **Total Repositories:** {data['total_repos']}")
        lines.append(f"- **Total Stars:** ⭐ {data['total_stars']:,}")
        lines.append(f"- **Total Forks:** 🔀 {data['total_forks']:,}")
        
        # Activity metrics
        lines.append(f"- **Active Repositories:** {data['active_repos']}")
        if data['private_repos']:
            lines.append(f"- **Private Repositories:** 🔒 {data['private_repos']}")
        
        # Language breakdown
        if data['top_languages']:
            lines.append("")
            lines.append("### Top Languages")
            for lang, count in data['top_languages']:
                percentage = (count / data['total_repos']) * 100
                lines.append(f"- **{lang}:** {count} repos ({percentage:.1f}%)")
        
        # License breakdown
        if len(data['license_distribution']) > 1:
            lines.append("")
            lines.append("### License Distribution")
            for license_name, count in data['license_distribution']:
                lines.append(f"- **{license_name}:** {count} repos")
        
        return '\n'.join(lines)


@register_component(depends_on=['summary_stats'])
class TagCloudComponent(BaseExportComponent):
    """Renders a tag cloud from repository topics and tags."""
    
    @property
    def name(self) -> str:
        return "tag_cloud"
    
    @property
    def description(self) -> str:
        return "Tag cloud visualization of topics and classifications"
    
    def render(self, context: ExportContext) -> str:
        # Collect all tags
        tag_counts = Counter()
        
        for repo in context.repositories:
            # GitHub topics
            for topic in repo.get('topics', []):
                tag_counts[topic] += 1
            
            # Custom tags
            for tag in repo.get('_tags', []):
                # Skip repo: tags as they're redundant
                if not tag.startswith('repo:'):
                    tag_counts[tag] += 1
        
        if not tag_counts:
            return ""
        
        # Sort by frequency
        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])
        
        lines = ["## 🏷️ Topics & Tags", ""]
        
        # Group by frequency for visual hierarchy
        very_common = [t for t, c in sorted_tags if c >= context.total_repos * 0.5]
        common = [t for t, c in sorted_tags if context.total_repos * 0.2 <= c < context.total_repos * 0.5]
        occasional = [t for t, c in sorted_tags if c < context.total_repos * 0.2]
        
        if very_common:
            lines.append("**Most Common:** " + ', '.join(f'`{t}`' for t in very_common[:10]))
        if common:
            lines.append("**Common:** " + ', '.join(f'`{t}`' for t in common[:15]))
        if occasional and len(occasional) <= 20:
            lines.append("**Other:** " + ', '.join(f'`{t}`' for t in occasional))
        
        return '\n'.join(lines)
    
    def render_html(self, context: ExportContext) -> str:
        # Collect tags with counts
        tag_counts = Counter()
        for repo in context.repositories:
            for topic in repo.get('topics', []):
                tag_counts[topic] += 1
            for tag in repo.get('_tags', []):
                if not tag.startswith('repo:'):
                    tag_counts[tag] += 1
        
        if not tag_counts:
            return ""
        
        # Generate tag cloud with varying sizes
        max_count = max(tag_counts.values())
        tags_html = []
        
        for tag, count in sorted(tag_counts.items()):
            # Calculate relative size (1-5)
            size = min(5, max(1, int((count / max_count) * 5)))
            tags_html.append(f'<span class="tag tag-size-{size}" data-count="{count}">{tag}</span>')
        
        return f"""
        <div class="tag-cloud">
            <h2>🏷️ Topics & Tags</h2>
            <div class="tags">
                {' '.join(tags_html)}
            </div>
        </div>
        """


@register_component()
class RepositoryCardsComponent(BaseExportComponent):
    """Renders individual repository cards with details."""
    
    @property
    def name(self) -> str:
        return "repository_cards"
    
    @property
    def description(self) -> str:
        return "Detailed cards for each repository"
    
    def render(self, context: ExportContext) -> str:
        lines = ["## 📚 Repositories", ""]
        
        # Group repositories if specified
        group_by = context.config.get('group_by')
        if group_by:
            grouped = self._group_repositories(context.repositories, group_by)
        else:
            grouped = {'All': context.repositories}
        
        # Sort repos by stars by default
        sort_by = context.config.get('sort_by', 'stars')
        
        for group_name, repos in sorted(grouped.items()):
            if len(grouped) > 1:
                lines.append(f"### {group_name}")
                lines.append(f"*{len(repos)} repositories*")
                lines.append("")
            
            # Sort repositories
            sorted_repos = self._sort_repositories(repos, sort_by)
            
            for repo in sorted_repos:
                lines.extend(self._render_repository_card(repo, context))
        
        return '\n'.join(lines)
    
    def _group_repositories(self, repos: List[Dict], group_by: str) -> Dict[str, List[Dict]]:
        """Group repositories by specified criteria."""
        grouped = {}
        
        for repo in repos:
            if group_by == 'language':
                key = repo.get('language', 'Unknown')
            elif group_by == 'license':
                license_info = repo.get('license')
                if license_info and isinstance(license_info, dict):
                    key = license_info.get('spdx_id', 'Unknown')
                else:
                    key = 'No License'
            elif group_by == 'year':
                created = repo.get('created_at', '')
                key = created[:4] if created else 'Unknown'
            elif group_by.startswith('tag:'):
                # Group by specific tag prefix
                tag_prefix = group_by[4:] + ':'
                key = 'Other'
                for tag in repo.get('_tags', []):
                    if tag.startswith(tag_prefix):
                        key = tag.split(':', 1)[1]
                        break
            else:
                key = 'All'
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(repo)
        
        return grouped
    
    def _sort_repositories(self, repos: List[Dict], sort_by: str) -> List[Dict]:
        """Sort repositories by specified criteria."""
        if sort_by == 'stars':
            return sorted(repos, key=lambda r: r.get('stargazers_count', 0), reverse=True)
        elif sort_by == 'name':
            return sorted(repos, key=lambda r: r.get('name', '').lower())
        elif sort_by == 'updated':
            return sorted(repos, key=lambda r: r.get('updated_at', ''), reverse=True)
        elif sort_by == 'created':
            return sorted(repos, key=lambda r: r.get('created_at', ''), reverse=True)
        else:
            return repos
    
    def _render_repository_card(self, repo: Dict, context: ExportContext) -> List[str]:
        """Render a single repository card."""
        lines = []
        name = repo.get('name', 'Unknown')
        
        # Title with badges
        badges = []
        if repo.get('stargazers_count', 0) > 0:
            badges.append(f"⭐ {repo['stargazers_count']}")
        if repo.get('forks_count', 0) > 0:
            badges.append(f"🔀 {repo['forks_count']}")
        if repo.get('language'):
            badges.append(f"💻 {repo['language']}")
        
        title_line = f"#### {name}"
        if badges:
            title_line += f" · {' · '.join(badges)}"
        lines.append(title_line)
        
        # Status indicators
        status = []
        if repo.get('private'):
            status.append("🔒 Private")
        if repo.get('archived'):
            status.append("📦 Archived")
        if repo.get('is_template'):
            status.append("📋 Template")
        
        if status:
            lines.append(' · '.join(status))
        
        # Description
        if repo.get('description'):
            lines.append("")
            lines.append(f"> {repo['description']}")
        
        # Quick links
        links = []
        if repo.get('html_url'):
            links.append(f"[GitHub]({repo['html_url']})")
        if repo.get('homepage') and repo['homepage'] != repo.get('html_url'):
            links.append(f"[Website]({repo['homepage']})")
        
        # Check for package registries
        if repo.get('has_pypi') or 'pypi' in repo.get('_tags', []):
            pypi_name = repo.get('pypi_package', name.replace('_', '-'))
            links.append(f"[PyPI](https://pypi.org/project/{pypi_name}/)")
        
        if links:
            lines.append("")
            lines.append("**Links:** " + " | ".join(links))
        
        # Collapsible details
        show_details = context.config.get('show_details', True)
        if show_details and self._has_extended_info(repo):
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>More details</summary>")
            lines.append("")
            lines.extend(self._render_extended_details(repo))
            lines.append("</details>")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        return lines
    
    def _has_extended_info(self, repo: Dict) -> bool:
        """Check if repo has extended information worth showing."""
        return any([
            repo.get('languages'),
            repo.get('topics'),
            repo.get('_tags'),
            repo.get('created_at'),
            repo.get('has_issues'),
            repo.get('has_wiki')
        ])
    
    def _render_extended_details(self, repo: Dict) -> List[str]:
        """Render extended repository details."""
        lines = []
        
        # Dates
        if repo.get('created_at'):
            lines.append(f"**Created:** {repo['created_at'][:10]}")
        if repo.get('updated_at'):
            lines.append(f"**Last Updated:** {repo['updated_at'][:10]}")
        
        # Languages breakdown
        if repo.get('languages') and isinstance(repo['languages'], dict):
            lines.append("")
            lines.append("**Languages:**")
            for lang, data in sorted(repo['languages'].items(), 
                                    key=lambda x: x[1] if isinstance(x[1], int) else 0, 
                                    reverse=True)[:5]:
                lines.append(f"- {lang}")
        
        # Topics and tags
        all_tags = set()
        all_tags.update(repo.get('topics', []))
        all_tags.update(t for t in repo.get('_tags', []) if not t.startswith('repo:'))
        
        if all_tags:
            lines.append("")
            lines.append("**Topics:** " + ', '.join(f'`{t}`' for t in sorted(all_tags)))
        
        return lines


@register_component()
class ReadmeContentComponent(BaseExportComponent):
    """Renders README content for repositories."""
    
    @property
    def name(self) -> str:
        return "readme_content"
    
    @property
    def description(self) -> str:
        return "README content sections for each repository"
    
    def render(self, context: ExportContext) -> str:
        # Check if READMEs should be included
        if not context.config.get('include_readme', False):
            return ""
        
        lines = ["## 📄 README Content", ""]
        max_length = context.config.get('readme_length', 500)
        
        repos_with_readme = [r for r in context.repositories if r.get('has_readme')]
        
        if not repos_with_readme:
            return ""
        
        for repo in repos_with_readme:
            name = repo.get('name', 'Unknown')
            readme_content = repo.get('readme_preview') or repo.get('readme_content', '')
            
            if not readme_content:
                continue
            
            lines.append(f"### {name}")
            lines.append("")
            
            # Truncate if needed
            if max_length and len(readme_content) > max_length:
                readme_content = readme_content[:max_length] + "..."
            
            # Add the content in a blockquote for better formatting
            for line in readme_content.split('\n'):
                lines.append(f"> {line}")
            
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return '\n'.join(lines)
    
    def render_html(self, context: ExportContext) -> str:
        if not context.config.get('include_readme', False):
            return ""
        
        repos_with_readme = [r for r in context.repositories if r.get('has_readme')]
        if not repos_with_readme:
            return ""
        
        max_length = context.config.get('readme_length', 500)
        
        html_parts = ['<div class="readme-content">', '<h2>📄 README Content</h2>']
        
        for repo in repos_with_readme:
            name = repo.get('name', 'Unknown')
            readme_content = repo.get('readme_preview') or repo.get('readme_content', '')
            
            if not readme_content:
                continue
            
            if max_length and len(readme_content) > max_length:
                readme_content = readme_content[:max_length] + "..."
            
            # Escape HTML characters
            import html
            readme_content = html.escape(readme_content)
            
            html_parts.append(f"""
            <div class="readme-item">
                <h3>{name}</h3>
                <blockquote class="readme-preview">
                    <pre>{readme_content}</pre>
                </blockquote>
            </div>
            """)
        
        html_parts.append('</div>')
        return '\n'.join(html_parts)


# Register default components on import
__all__ = [
    'HeaderComponent',
    'SummaryStatisticsComponent', 
    'TagCloudComponent',
    'RepositoryCardsComponent',
    'ReadmeContentComponent'
]