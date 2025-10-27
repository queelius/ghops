"""
Time machine analyzer for repository evolution tracking.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
import statistics

logger = logging.getLogger(__name__)


class TimeMachineAnalyzer:
    """Analyzes repository history to track evolution patterns."""

    def __init__(self, repo_path: str):
        """Initialize analyzer for a repository.

        Args:
            repo_path: Path to the git repository.
        """
        self.repo_path = Path(repo_path)
        self.commits = []
        self.file_history = defaultdict(list)
        self.contributor_stats = defaultdict(dict)
        self.technology_timeline = []
        self.evolution_metrics = {}

    def analyze_full_history(self) -> Dict[str, Any]:
        """Perform comprehensive history analysis.

        Returns:
            Dictionary containing all analysis results.
        """
        # Load commit history
        self.commits = self._get_commit_history()

        # Analyze different aspects
        results = {
            'repository': str(self.repo_path),
            'total_commits': len(self.commits),
            'date_range': self._get_date_range(),
            'evolution_patterns': self._analyze_evolution_patterns(),
            'technology_migrations': self._detect_technology_migrations(),
            'code_velocity': self._calculate_code_velocity(),
            'contributor_patterns': self._analyze_contributor_patterns(),
            'file_lifecycle': self._analyze_file_lifecycle(),
            'hotspots': self._identify_hotspots(),
            'refactoring_events': self._detect_refactoring_events(),
            'growth_metrics': self._calculate_growth_metrics(),
            'stability_score': self._calculate_stability_score(),
            'predictions': self._generate_predictions(),
        }

        return results

    def _get_commit_history(self) -> List[Dict[str, Any]]:
        """Retrieve full commit history with statistics.

        Returns:
            List of commit dictionaries.
        """
        cmd = [
            'git', '-C', str(self.repo_path), 'log',
            '--all', '--format=%H|%an|%ae|%at|%s|%b',
            '--numstat', '--no-merges'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        commits = []
        current_commit = None

        for line in result.stdout.split('\n'):
            if '|' in line and not '\t' in line:
                # New commit line
                parts = line.split('|', 5)
                if len(parts) >= 5:
                    current_commit = {
                        'hash': parts[0],
                        'author': parts[1],
                        'email': parts[2],
                        'timestamp': int(parts[3]),
                        'date': datetime.fromtimestamp(int(parts[3])),
                        'subject': parts[4],
                        'body': parts[5] if len(parts) > 5 else '',
                        'files': [],
                        'additions': 0,
                        'deletions': 0,
                    }
                    commits.append(current_commit)
            elif '\t' in line and current_commit:
                # File change line
                parts = line.split('\t')
                if len(parts) == 3:
                    additions = int(parts[0]) if parts[0] != '-' else 0
                    deletions = int(parts[1]) if parts[1] != '-' else 0
                    filename = parts[2]

                    current_commit['files'].append({
                        'name': filename,
                        'additions': additions,
                        'deletions': deletions,
                    })
                    current_commit['additions'] += additions
                    current_commit['deletions'] += deletions

        return commits

    def _get_date_range(self) -> Dict[str, str]:
        """Get the date range of the repository.

        Returns:
            Dictionary with first and last commit dates.
        """
        if not self.commits:
            return {'first': None, 'last': None}

        dates = [c['date'] for c in self.commits]
        return {
            'first': min(dates).isoformat(),
            'last': max(dates).isoformat(),
            'age_days': (max(dates) - min(dates)).days,
        }

    def _analyze_evolution_patterns(self) -> Dict[str, Any]:
        """Analyze how the repository has evolved over time.

        Returns:
            Evolution pattern analysis.
        """
        patterns = {
            'growth_phases': [],
            'stagnation_periods': [],
            'burst_periods': [],
            'refactoring_waves': [],
        }

        # Group commits by month
        monthly_commits = defaultdict(list)
        for commit in self.commits:
            month_key = commit['date'].strftime('%Y-%m')
            monthly_commits[month_key].append(commit)

        # Analyze monthly patterns
        months = sorted(monthly_commits.keys())
        for i, month in enumerate(months):
            commits = monthly_commits[month]
            commit_count = len(commits)
            additions = sum(c['additions'] for c in commits)
            deletions = sum(c['deletions'] for c in commits)

            # Detect patterns
            if commit_count > 50:  # High activity
                patterns['burst_periods'].append({
                    'month': month,
                    'commits': commit_count,
                    'reason': 'High commit activity',
                })

            if i > 0:
                prev_month = months[i-1]
                prev_commits = len(monthly_commits[prev_month])

                if commit_count > prev_commits * 2:
                    patterns['growth_phases'].append({
                        'month': month,
                        'growth_factor': commit_count / prev_commits if prev_commits > 0 else 0,
                    })

            if deletions > additions * 1.5 and deletions > 100:
                patterns['refactoring_waves'].append({
                    'month': month,
                    'deletions': deletions,
                    'cleanup_ratio': deletions / (additions + 1),
                })

            if commit_count < 5:
                patterns['stagnation_periods'].append({
                    'month': month,
                    'commits': commit_count,
                })

        return patterns

    def _detect_technology_migrations(self) -> List[Dict[str, Any]]:
        """Detect major technology changes and migrations.

        Returns:
            List of detected technology migrations.
        """
        migrations = []

        # Track file extensions over time
        extension_timeline = defaultdict(lambda: defaultdict(int))

        for commit in self.commits:
            month = commit['date'].strftime('%Y-%m')
            for file_change in commit['files']:
                ext = Path(file_change['name']).suffix
                if ext:
                    extension_timeline[month][ext] += 1

        # Detect significant changes in technology stack
        months = sorted(extension_timeline.keys())
        for i in range(1, len(months)):
            curr_month = months[i]
            prev_month = months[i-1]

            curr_exts = extension_timeline[curr_month]
            prev_exts = extension_timeline[prev_month]

            # Check for new technologies
            new_exts = set(curr_exts.keys()) - set(prev_exts.keys())
            for ext in new_exts:
                if curr_exts[ext] > 5:  # Significant addition
                    migrations.append({
                        'type': 'technology_adoption',
                        'technology': self._ext_to_technology(ext),
                        'extension': ext,
                        'month': curr_month,
                        'file_count': curr_exts[ext],
                    })

            # Check for technology abandonment
            removed_exts = set(prev_exts.keys()) - set(curr_exts.keys())
            for ext in removed_exts:
                if prev_exts[ext] > 5:  # Significant removal
                    migrations.append({
                        'type': 'technology_abandonment',
                        'technology': self._ext_to_technology(ext),
                        'extension': ext,
                        'month': curr_month,
                    })

        # Detect specific migration patterns
        migrations.extend(self._detect_specific_migrations())

        return migrations

    def _ext_to_technology(self, ext: str) -> str:
        """Map file extension to technology name."""
        tech_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React',
            '.tsx': 'React TypeScript',
            '.java': 'Java',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.r': 'R',
            '.m': 'MATLAB/Objective-C',
            '.vue': 'Vue.js',
            '.svelte': 'Svelte',
        }
        return tech_map.get(ext, ext[1:].upper())

    def _detect_specific_migrations(self) -> List[Dict[str, Any]]:
        """Detect specific technology migrations."""
        migrations = []

        # Python 2 to 3 migration
        py2_patterns = ['print ', 'xrange(', 'raw_input(', 'unicode(']
        py3_patterns = ['print(', 'range(', 'input(', 'async def', 'await ']

        py2_commits = []
        py3_commits = []

        for commit in self.commits:
            commit_str = f"{commit['subject']} {commit['body']}".lower()

            # Check commit messages for migration mentions
            if 'python 3' in commit_str or 'py3' in commit_str:
                migrations.append({
                    'type': 'python_2_to_3',
                    'commit': commit['hash'],
                    'date': commit['date'].isoformat(),
                    'message': commit['subject'],
                })

            # jQuery to modern frameworks
            if 'remove jquery' in commit_str or 'replace jquery' in commit_str:
                migrations.append({
                    'type': 'jquery_removal',
                    'commit': commit['hash'],
                    'date': commit['date'].isoformat(),
                    'message': commit['subject'],
                })

            # Database migrations
            if 'migrate' in commit_str and any(db in commit_str for db in ['mysql', 'postgres', 'mongodb', 'redis']):
                migrations.append({
                    'type': 'database_migration',
                    'commit': commit['hash'],
                    'date': commit['date'].isoformat(),
                    'message': commit['subject'],
                })

        return migrations

    def _calculate_code_velocity(self) -> Dict[str, Any]:
        """Calculate code velocity metrics over time.

        Returns:
            Code velocity analysis.
        """
        # Weekly velocity
        weekly_velocity = defaultdict(lambda: {'additions': 0, 'deletions': 0, 'commits': 0})

        for commit in self.commits:
            week = commit['date'].strftime('%Y-W%U')
            weekly_velocity[week]['additions'] += commit['additions']
            weekly_velocity[week]['deletions'] += commit['deletions']
            weekly_velocity[week]['commits'] += 1

        weeks = sorted(weekly_velocity.keys())
        velocities = [weekly_velocity[w]['additions'] - weekly_velocity[w]['deletions'] for w in weeks]

        # Calculate trends
        recent_weeks = weeks[-12:] if len(weeks) > 12 else weeks
        recent_velocity = [weekly_velocity[w]['additions'] - weekly_velocity[w]['deletions'] for w in recent_weeks]

        return {
            'average_weekly_changes': statistics.mean(velocities) if velocities else 0,
            'peak_week': max(weekly_velocity.items(), key=lambda x: x[1]['additions']) if weekly_velocity else None,
            'current_velocity': recent_velocity[-1] if recent_velocity else 0,
            'velocity_trend': self._calculate_trend(recent_velocity),
            'weeks_analyzed': len(weeks),
            'total_additions': sum(c['additions'] for c in self.commits),
            'total_deletions': sum(c['deletions'] for c in self.commits),
            'net_lines': sum(c['additions'] - c['deletions'] for c in self.commits),
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a list of values."""
        if len(values) < 2:
            return 'insufficient_data'

        # Simple linear regression
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 'stable'

        slope = numerator / denominator

        if slope > 0.5:
            return 'increasing'
        elif slope < -0.5:
            return 'decreasing'
        else:
            return 'stable'

    def _analyze_contributor_patterns(self) -> Dict[str, Any]:
        """Analyze contributor patterns and team dynamics.

        Returns:
            Contributor pattern analysis.
        """
        contributor_commits = defaultdict(list)
        contributor_files = defaultdict(set)
        contributor_lines = defaultdict(lambda: {'added': 0, 'deleted': 0})

        for commit in self.commits:
            author = commit['author']
            contributor_commits[author].append(commit)

            for file_change in commit['files']:
                contributor_files[author].add(file_change['name'])
                contributor_lines[author]['added'] += file_change['additions']
                contributor_lines[author]['deleted'] += file_change['deletions']

        # Calculate statistics
        total_contributors = len(contributor_commits)
        commit_counts = [len(commits) for commits in contributor_commits.values()]

        # Identify contributor types
        contributors = []
        for author, commits in contributor_commits.items():
            first_commit = min(c['date'] for c in commits)
            last_commit = max(c['date'] for c in commits)
            active_days = (last_commit - first_commit).days + 1

            contributor_type = self._classify_contributor(
                len(commits),
                active_days,
                len(contributor_files[author])
            )

            contributors.append({
                'name': author,
                'type': contributor_type,
                'commits': len(commits),
                'files_touched': len(contributor_files[author]),
                'lines_added': contributor_lines[author]['added'],
                'lines_deleted': contributor_lines[author]['deleted'],
                'first_commit': first_commit.isoformat(),
                'last_commit': last_commit.isoformat(),
                'active_days': active_days,
            })

        # Sort by commits
        contributors.sort(key=lambda x: x['commits'], reverse=True)

        # Calculate bus factor
        top_contributors = contributors[:3]
        top_commits = sum(c['commits'] for c in top_contributors)
        total_commits = sum(c['commits'] for c in contributors)

        return {
            'total_contributors': total_contributors,
            'active_contributors': len([c for c in contributors if (datetime.now() - datetime.fromisoformat(c['last_commit'])).days < 90]),
            'top_contributors': top_contributors[:10],
            'contributor_types': Counter(c['type'] for c in contributors),
            'bus_factor': len([c for c in contributors if c['commits'] > total_commits * 0.1]),
            'contribution_inequality': self._calculate_gini_coefficient(commit_counts),
        }

    def _classify_contributor(self, commits: int, active_days: int, files: int) -> str:
        """Classify contributor based on activity patterns."""
        commits_per_day = commits / max(active_days, 1)

        if commits > 100 and commits_per_day > 0.5:
            return 'core_developer'
        elif commits > 50:
            return 'regular_contributor'
        elif commits > 10:
            return 'occasional_contributor'
        elif commits == 1:
            return 'one_time_contributor'
        else:
            return 'sporadic_contributor'

    def _calculate_gini_coefficient(self, values: List[int]) -> float:
        """Calculate Gini coefficient for contribution inequality."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        n = len(values)
        index = range(1, n + 1)

        return (2 * sum(index[i] * sorted_values[i] for i in range(n))) / (n * sum(sorted_values)) - (n + 1) / n

    def _analyze_file_lifecycle(self) -> Dict[str, Any]:
        """Analyze the lifecycle of files in the repository.

        Returns:
            File lifecycle analysis.
        """
        file_births = {}
        file_deaths = {}
        file_changes = defaultdict(int)

        for commit in self.commits:
            for file_change in commit['files']:
                filename = file_change['name']
                file_changes[filename] += 1

                if filename not in file_births:
                    file_births[filename] = commit['date']

                # Track potential file deletion
                if file_change['deletions'] > 0 and file_change['additions'] == 0:
                    file_deaths[filename] = commit['date']

        # Calculate file ages
        file_ages = []
        for filename, birth in file_births.items():
            if filename in file_deaths:
                age = (file_deaths[filename] - birth).days
            else:
                age = (datetime.now() - birth).days
            file_ages.append(age)

        # Identify file categories
        stable_files = [f for f, changes in file_changes.items() if changes < 5]
        volatile_files = [f for f, changes in file_changes.items() if changes > 20]

        return {
            'total_files': len(file_births),
            'deleted_files': len(file_deaths),
            'average_file_age_days': statistics.mean(file_ages) if file_ages else 0,
            'median_file_age_days': statistics.median(file_ages) if file_ages else 0,
            'stable_files_count': len(stable_files),
            'volatile_files_count': len(volatile_files),
            'most_changed_files': sorted(file_changes.items(), key=lambda x: x[1], reverse=True)[:10],
        }

    def _identify_hotspots(self) -> List[Dict[str, Any]]:
        """Identify code hotspots that change frequently.

        Returns:
            List of hotspot files.
        """
        file_stats = defaultdict(lambda: {
            'changes': 0,
            'authors': set(),
            'additions': 0,
            'deletions': 0,
            'commits': [],
        })

        for commit in self.commits:
            for file_change in commit['files']:
                filename = file_change['name']
                stats = file_stats[filename]
                stats['changes'] += 1
                stats['authors'].add(commit['author'])
                stats['additions'] += file_change['additions']
                stats['deletions'] += file_change['deletions']
                stats['commits'].append(commit['date'])

        # Calculate hotspot metrics
        hotspots = []
        for filename, stats in file_stats.items():
            if stats['changes'] < 10:
                continue

            # Calculate change frequency
            commit_dates = sorted(stats['commits'])
            if len(commit_dates) > 1:
                timespan = (commit_dates[-1] - commit_dates[0]).days + 1
                frequency = stats['changes'] / timespan if timespan > 0 else 0
            else:
                frequency = 0

            hotspots.append({
                'file': filename,
                'changes': stats['changes'],
                'authors': len(stats['authors']),
                'total_lines_changed': stats['additions'] + stats['deletions'],
                'change_frequency': frequency,
                'complexity_score': stats['changes'] * len(stats['authors']),
            })

        # Sort by complexity score
        hotspots.sort(key=lambda x: x['complexity_score'], reverse=True)

        return hotspots[:20]

    def _detect_refactoring_events(self) -> List[Dict[str, Any]]:
        """Detect major refactoring events.

        Returns:
            List of detected refactoring events.
        """
        refactorings = []

        for commit in self.commits:
            # Check for refactoring indicators
            indicators = [
                'refactor', 'restructure', 'reorganize', 'cleanup',
                'rename', 'move', 'extract', 'inline', 'simplify',
            ]

            message_lower = f"{commit['subject']} {commit['body']}".lower()

            if any(indicator in message_lower for indicator in indicators):
                # Calculate refactoring impact
                impact = commit['additions'] + commit['deletions']

                if impact > 100:  # Significant refactoring
                    refactorings.append({
                        'commit': commit['hash'],
                        'date': commit['date'].isoformat(),
                        'message': commit['subject'],
                        'impact': impact,
                        'files_affected': len(commit['files']),
                        'type': self._classify_refactoring(message_lower),
                    })

        return refactorings

    def _classify_refactoring(self, message: str) -> str:
        """Classify the type of refactoring."""
        if 'rename' in message:
            return 'rename'
        elif 'move' in message:
            return 'restructure'
        elif 'extract' in message:
            return 'extract_method'
        elif 'cleanup' in message:
            return 'cleanup'
        elif 'simplify' in message:
            return 'simplification'
        else:
            return 'general'

    def _calculate_growth_metrics(self) -> Dict[str, Any]:
        """Calculate repository growth metrics.

        Returns:
            Growth metrics analysis.
        """
        # Monthly growth
        monthly_stats = defaultdict(lambda: {'additions': 0, 'deletions': 0, 'files': set()})

        for commit in self.commits:
            month = commit['date'].strftime('%Y-%m')
            monthly_stats[month]['additions'] += commit['additions']
            monthly_stats[month]['deletions'] += commit['deletions']
            for file_change in commit['files']:
                monthly_stats[month]['files'].add(file_change['name'])

        months = sorted(monthly_stats.keys())
        if not months:
            return {}

        # Calculate growth rate
        growth_rates = []
        for i in range(1, len(months)):
            curr = monthly_stats[months[i]]
            prev = monthly_stats[months[i-1]]

            net_curr = curr['additions'] - curr['deletions']
            net_prev = prev['additions'] - prev['deletions']

            if net_prev != 0:
                growth_rate = (net_curr - net_prev) / abs(net_prev)
                growth_rates.append(growth_rate)

        return {
            'months_active': len(months),
            'average_monthly_additions': statistics.mean([s['additions'] for s in monthly_stats.values()]),
            'average_monthly_deletions': statistics.mean([s['deletions'] for s in monthly_stats.values()]),
            'average_growth_rate': statistics.mean(growth_rates) if growth_rates else 0,
            'peak_growth_month': max(months, key=lambda m: monthly_stats[m]['additions'] - monthly_stats[m]['deletions']) if months else None,
        }

    def _calculate_stability_score(self) -> float:
        """Calculate overall repository stability score.

        Returns:
            Stability score between 0 and 100.
        """
        factors = []

        # Factor 1: Commit regularity
        if self.commits:
            dates = [c['date'] for c in self.commits]
            date_range = (max(dates) - min(dates)).days + 1
            expected_commits = date_range / 7  # Expect at least weekly commits
            actual_commits = len(self.commits)
            regularity_score = min(100, (actual_commits / expected_commits) * 100) if expected_commits > 0 else 0
            factors.append(regularity_score)

        # Factor 2: Contributor stability
        recent_commits = [c for c in self.commits if (datetime.now() - c['date']).days < 180]
        if recent_commits:
            recent_authors = len(set(c['author'] for c in recent_commits))
            total_authors = len(set(c['author'] for c in self.commits))
            retention_score = (recent_authors / total_authors * 100) if total_authors > 0 else 0
            factors.append(retention_score)

        # Factor 3: Code churn rate
        if self.commits:
            total_changes = sum(c['additions'] + c['deletions'] for c in self.commits)
            net_additions = sum(c['additions'] - c['deletions'] for c in self.commits)
            churn_rate = (total_changes - net_additions) / total_changes if total_changes > 0 else 0
            churn_score = max(0, 100 - churn_rate * 100)
            factors.append(churn_score)

        return statistics.mean(factors) if factors else 50.0

    def _generate_predictions(self) -> Dict[str, Any]:
        """Generate predictions about future maintenance needs.

        Returns:
            Predictions and recommendations.
        """
        predictions = {
            'next_refactoring': None,
            'contributor_risk': None,
            'growth_forecast': None,
            'maintenance_recommendations': [],
        }

        # Predict next refactoring based on patterns
        refactorings = self._detect_refactoring_events()
        if len(refactorings) > 2:
            # Calculate average time between refactorings
            refactor_dates = sorted([datetime.fromisoformat(r['date']) for r in refactorings])
            intervals = [(refactor_dates[i+1] - refactor_dates[i]).days for i in range(len(refactor_dates)-1)]
            avg_interval = statistics.mean(intervals)

            last_refactoring = refactor_dates[-1]
            next_refactoring = last_refactoring + timedelta(days=avg_interval)

            predictions['next_refactoring'] = {
                'estimated_date': next_refactoring.isoformat(),
                'days_until': (next_refactoring - datetime.now()).days,
                'confidence': 'medium' if len(refactorings) > 5 else 'low',
            }

        # Assess contributor risk
        contributor_patterns = self._analyze_contributor_patterns()
        bus_factor = contributor_patterns.get('bus_factor', 0)

        if bus_factor < 3:
            predictions['contributor_risk'] = {
                'level': 'high',
                'bus_factor': bus_factor,
                'recommendation': 'Increase contributor diversity',
            }
        elif bus_factor < 5:
            predictions['contributor_risk'] = {
                'level': 'medium',
                'bus_factor': bus_factor,
                'recommendation': 'Monitor contributor engagement',
            }
        else:
            predictions['contributor_risk'] = {
                'level': 'low',
                'bus_factor': bus_factor,
                'recommendation': 'Healthy contributor diversity',
            }

        # Growth forecast
        growth_metrics = self._calculate_growth_metrics()
        if growth_metrics.get('average_growth_rate'):
            predictions['growth_forecast'] = {
                'trend': 'growing' if growth_metrics['average_growth_rate'] > 0 else 'shrinking',
                'rate': growth_metrics['average_growth_rate'],
            }

        # Generate maintenance recommendations
        hotspots = self._identify_hotspots()
        if hotspots:
            predictions['maintenance_recommendations'].append({
                'priority': 'high',
                'action': 'refactor_hotspots',
                'details': f"Consider refactoring {len(hotspots)} hotspot files",
                'files': [h['file'] for h in hotspots[:5]],
            })

        stability_score = self._calculate_stability_score()
        if stability_score < 50:
            predictions['maintenance_recommendations'].append({
                'priority': 'high',
                'action': 'improve_stability',
                'details': f"Stability score is low ({stability_score:.1f}/100)",
            })

        return predictions

    def export_timeline_json(self) -> str:
        """Export analysis results as JSON timeline.

        Returns:
            JSON string of timeline data.
        """
        timeline = {
            'repository': str(self.repo_path),
            'analysis_date': datetime.now().isoformat(),
            'commits': len(self.commits),
            'timeline_events': [],
        }

        # Add commits as events
        for commit in self.commits[:100]:  # Limit to recent 100
            timeline['timeline_events'].append({
                'type': 'commit',
                'date': commit['date'].isoformat(),
                'author': commit['author'],
                'message': commit['subject'],
                'impact': commit['additions'] + commit['deletions'],
            })

        # Add technology migrations
        migrations = self._detect_technology_migrations()
        for migration in migrations:
            timeline['timeline_events'].append({
                'type': 'migration',
                'date': migration.get('month', '') + '-01',
                'description': f"{migration['type']}: {migration.get('technology', '')}",
            })

        # Sort by date
        timeline['timeline_events'].sort(key=lambda x: x['date'])

        return json.dumps(timeline, indent=2)