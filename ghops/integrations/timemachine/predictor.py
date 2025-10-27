"""
Predictive analytics for repository maintenance.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import statistics
import math

logger = logging.getLogger(__name__)


class MaintenancePredictor:
    """Predicts future maintenance needs and issues."""

    def __init__(self, historical_data: Dict[str, Any]):
        """Initialize predictor with historical analysis data.

        Args:
            historical_data: Output from TimeMachineAnalyzer.
        """
        self.data = historical_data
        self.predictions = {}

    def predict_all(self) -> Dict[str, Any]:
        """Generate all predictions.

        Returns:
            Dictionary containing all predictions.
        """
        return {
            'maintenance_schedule': self.predict_maintenance_schedule(),
            'technical_debt': self.predict_technical_debt(),
            'resource_needs': self.predict_resource_needs(),
            'risk_assessment': self.assess_risks(),
            'optimization_opportunities': self.identify_optimizations(),
            'milestone_predictions': self.predict_milestones(),
            'health_forecast': self.forecast_health(),
        }

    def predict_maintenance_schedule(self) -> Dict[str, Any]:
        """Predict optimal maintenance schedule.

        Returns:
            Maintenance schedule recommendations.
        """
        schedule = {
            'immediate': [],
            'short_term': [],  # Next 30 days
            'medium_term': [],  # Next 90 days
            'long_term': [],  # Next year
        }

        # Analyze hotspots for immediate attention
        hotspots = self.data.get('hotspots', [])
        if hotspots:
            high_complexity = [h for h in hotspots if h.get('complexity_score', 0) > 100]
            if high_complexity:
                schedule['immediate'].append({
                    'task': 'refactor_complex_files',
                    'priority': 'critical',
                    'files': [h['file'] for h in high_complexity[:5]],
                    'estimated_hours': len(high_complexity) * 4,
                    'reason': 'High complexity and change frequency',
                })

        # Predict refactoring needs
        refactoring_prediction = self.data.get('predictions', {}).get('next_refactoring')
        if refactoring_prediction:
            days_until = refactoring_prediction.get('days_until', 365)
            task = {
                'task': 'major_refactoring',
                'priority': 'medium',
                'estimated_date': refactoring_prediction.get('estimated_date'),
                'estimated_hours': 40,
                'reason': 'Based on historical refactoring patterns',
            }

            if days_until < 30:
                schedule['short_term'].append(task)
            elif days_until < 90:
                schedule['medium_term'].append(task)
            else:
                schedule['long_term'].append(task)

        # Dependency updates based on age
        evolution = self.data.get('evolution_patterns', {})
        stagnation = evolution.get('stagnation_periods', [])
        if stagnation:
            schedule['short_term'].append({
                'task': 'dependency_update',
                'priority': 'high',
                'estimated_hours': 8,
                'reason': 'Repository showing signs of stagnation',
            })

        # Documentation updates
        file_lifecycle = self.data.get('file_lifecycle', {})
        volatile_files = file_lifecycle.get('volatile_files_count', 0)
        if volatile_files > 10:
            schedule['medium_term'].append({
                'task': 'documentation_update',
                'priority': 'medium',
                'estimated_hours': 16,
                'reason': f'{volatile_files} files change frequently and may need documentation',
            })

        # Testing improvements
        stability_score = self.data.get('stability_score', 100)
        if stability_score < 70:
            schedule['immediate'].append({
                'task': 'improve_test_coverage',
                'priority': 'high',
                'estimated_hours': 24,
                'reason': f'Low stability score ({stability_score:.1f}/100)',
            })

        return schedule

    def predict_technical_debt(self) -> Dict[str, Any]:
        """Predict and quantify technical debt.

        Returns:
            Technical debt assessment.
        """
        debt_indicators = []
        total_debt_score = 0

        # Code duplication debt
        hotspots = self.data.get('hotspots', [])
        if hotspots:
            duplication_score = len([h for h in hotspots if h.get('changes', 0) > 20])
            debt_indicators.append({
                'type': 'code_duplication',
                'severity': 'high' if duplication_score > 5 else 'medium',
                'score': duplication_score * 10,
                'impact': 'Increased maintenance cost',
                'remediation_cost_hours': duplication_score * 8,
            })
            total_debt_score += duplication_score * 10

        # Architecture debt
        file_lifecycle = self.data.get('file_lifecycle', {})
        avg_file_age = file_lifecycle.get('average_file_age_days', 0)
        if avg_file_age > 730:  # Files older than 2 years
            age_score = min(50, avg_file_age / 50)
            debt_indicators.append({
                'type': 'legacy_code',
                'severity': 'medium',
                'score': age_score,
                'impact': 'Difficulty in modernization',
                'remediation_cost_hours': age_score * 4,
            })
            total_debt_score += age_score

        # Testing debt
        stability_score = self.data.get('stability_score', 100)
        if stability_score < 70:
            testing_debt = (100 - stability_score) / 2
            debt_indicators.append({
                'type': 'insufficient_testing',
                'severity': 'high',
                'score': testing_debt,
                'impact': 'Increased bug risk',
                'remediation_cost_hours': testing_debt * 3,
            })
            total_debt_score += testing_debt

        # Documentation debt
        contributor_patterns = self.data.get('contributor_patterns', {})
        bus_factor = contributor_patterns.get('bus_factor', 1)
        if bus_factor < 3:
            doc_debt = (3 - bus_factor) * 20
            debt_indicators.append({
                'type': 'knowledge_concentration',
                'severity': 'critical' if bus_factor == 1 else 'high',
                'score': doc_debt,
                'impact': 'High risk if key contributors leave',
                'remediation_cost_hours': 40,
            })
            total_debt_score += doc_debt

        # Calculate interest rate (how fast debt grows)
        velocity = self.data.get('code_velocity', {})
        current_velocity = velocity.get('current_velocity', 0)
        if current_velocity > 1000:
            interest_rate = 0.05  # 5% per month for high velocity projects
        elif current_velocity > 500:
            interest_rate = 0.03
        else:
            interest_rate = 0.01

        return {
            'total_score': total_debt_score,
            'severity': self._classify_debt_severity(total_debt_score),
            'indicators': debt_indicators,
            'total_remediation_hours': sum(d.get('remediation_cost_hours', 0) for d in debt_indicators),
            'monthly_interest_rate': interest_rate,
            'projected_debt_6_months': total_debt_score * (1 + interest_rate * 6),
            'recommendations': self._generate_debt_recommendations(debt_indicators),
        }

    def _classify_debt_severity(self, score: float) -> str:
        """Classify technical debt severity."""
        if score > 150:
            return 'critical'
        elif score > 100:
            return 'high'
        elif score > 50:
            return 'medium'
        else:
            return 'low'

    def _generate_debt_recommendations(self, indicators: List[Dict]) -> List[str]:
        """Generate recommendations for addressing technical debt."""
        recommendations = []

        for indicator in indicators:
            if indicator['type'] == 'code_duplication':
                recommendations.append('Extract common code into shared libraries')
            elif indicator['type'] == 'legacy_code':
                recommendations.append('Plan gradual modernization of old components')
            elif indicator['type'] == 'insufficient_testing':
                recommendations.append('Implement comprehensive test suite')
            elif indicator['type'] == 'knowledge_concentration':
                recommendations.append('Document critical systems and rotate responsibilities')

        return recommendations

    def predict_resource_needs(self) -> Dict[str, Any]:
        """Predict future resource needs.

        Returns:
            Resource requirement predictions.
        """
        needs = {
            'developer_hours': {},
            'skill_requirements': [],
            'infrastructure': [],
        }

        # Calculate developer hours needed
        maintenance_schedule = self.predict_maintenance_schedule()
        for timeframe, tasks in maintenance_schedule.items():
            total_hours = sum(task.get('estimated_hours', 0) for task in tasks)
            needs['developer_hours'][timeframe] = total_hours

        # Predict skill requirements
        migrations = self.data.get('technology_migrations', [])
        current_tech = set()
        for migration in migrations:
            if migration.get('type') == 'technology_adoption':
                tech = migration.get('technology', '')
                if tech:
                    current_tech.add(tech)

        if current_tech:
            needs['skill_requirements'] = [
                {'skill': tech, 'level': 'intermediate', 'priority': 'high'}
                for tech in current_tech
            ]

        # Infrastructure needs based on growth
        growth = self.data.get('growth_metrics', {})
        growth_rate = growth.get('average_growth_rate', 0)

        if growth_rate > 0.1:  # 10% growth
            needs['infrastructure'].append({
                'type': 'ci_capacity',
                'reason': 'Repository growing rapidly',
                'timeline': 'short_term',
            })

        velocity = self.data.get('code_velocity', {})
        if velocity.get('average_weekly_changes', 0) > 1000:
            needs['infrastructure'].append({
                'type': 'testing_infrastructure',
                'reason': 'High code velocity requires robust testing',
                'timeline': 'immediate',
            })

        return needs

    def assess_risks(self) -> Dict[str, List[Dict[str, Any]]]:
        """Assess various project risks.

        Returns:
            Risk assessment by category.
        """
        risks = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
        }

        # Contributor risk
        contributor_risk = self.data.get('predictions', {}).get('contributor_risk', {})
        if contributor_risk.get('level') == 'high':
            risks['critical'].append({
                'type': 'bus_factor',
                'description': f"Bus factor is {contributor_risk.get('bus_factor', 'unknown')}",
                'impact': 'Project could stall if key contributors leave',
                'mitigation': 'Increase contributor diversity and documentation',
                'probability': 'medium',
            })

        # Stagnation risk
        evolution = self.data.get('evolution_patterns', {})
        stagnation_periods = evolution.get('stagnation_periods', [])
        if len(stagnation_periods) > 3:
            risks['high'].append({
                'type': 'project_abandonment',
                'description': f'Multiple stagnation periods detected ({len(stagnation_periods)})',
                'impact': 'Project may become unmaintained',
                'mitigation': 'Re-engage contributors or plan migration',
                'probability': 'high',
            })

        # Technical debt risk
        tech_debt = self.predict_technical_debt()
        if tech_debt['severity'] in ['critical', 'high']:
            risks['high'].append({
                'type': 'technical_debt_crisis',
                'description': f"Technical debt score: {tech_debt['total_score']:.1f}",
                'impact': 'Development velocity will decrease significantly',
                'mitigation': 'Allocate dedicated time for debt reduction',
                'probability': 'high',
            })

        # Security risk
        file_age = self.data.get('file_lifecycle', {}).get('average_file_age_days', 0)
        if file_age > 1095:  # 3 years
            risks['medium'].append({
                'type': 'security_vulnerabilities',
                'description': 'Old codebase may have unpatched vulnerabilities',
                'impact': 'Potential security breaches',
                'mitigation': 'Conduct security audit and update dependencies',
                'probability': 'medium',
            })

        # Scalability risk
        hotspots = self.data.get('hotspots', [])
        if len(hotspots) > 10:
            risks['medium'].append({
                'type': 'scalability_bottleneck',
                'description': f'{len(hotspots)} code hotspots identified',
                'impact': 'Performance degradation as project grows',
                'mitigation': 'Refactor hotspot files',
                'probability': 'medium',
            })

        return risks

    def identify_optimizations(self) -> List[Dict[str, Any]]:
        """Identify optimization opportunities.

        Returns:
            List of optimization recommendations.
        """
        optimizations = []

        # File structure optimization
        hotspots = self.data.get('hotspots', [])
        if hotspots:
            coupled_files = self._identify_coupled_files(hotspots)
            if coupled_files:
                optimizations.append({
                    'type': 'decouple_modules',
                    'priority': 'high',
                    'impact': 'Reduce change propagation',
                    'effort': 'medium',
                    'files': coupled_files[:5],
                    'expected_benefit': 'Reduce maintenance cost by 20%',
                })

        # Workflow optimization
        velocity = self.data.get('code_velocity', {})
        if velocity.get('velocity_trend') == 'decreasing':
            optimizations.append({
                'type': 'improve_dev_workflow',
                'priority': 'high',
                'impact': 'Increase development velocity',
                'effort': 'low',
                'suggestions': [
                    'Automate repetitive tasks',
                    'Improve CI/CD pipeline',
                    'Add pre-commit hooks',
                ],
                'expected_benefit': 'Increase velocity by 30%',
            })

        # Team optimization
        contributors = self.data.get('contributor_patterns', {})
        inequality = contributors.get('contribution_inequality', 0)
        if inequality > 0.7:
            optimizations.append({
                'type': 'balance_contributions',
                'priority': 'medium',
                'impact': 'Improve team efficiency',
                'effort': 'medium',
                'suggestions': [
                    'Implement code review rotation',
                    'Pair programming sessions',
                    'Knowledge sharing workshops',
                ],
                'expected_benefit': 'Reduce bus factor and improve team morale',
            })

        # Architecture optimization
        migrations = self.data.get('technology_migrations', [])
        mixed_tech = len(set(m.get('technology') for m in migrations if m.get('type') == 'technology_adoption'))
        if mixed_tech > 3:
            optimizations.append({
                'type': 'standardize_technology',
                'priority': 'medium',
                'impact': 'Reduce complexity',
                'effort': 'high',
                'suggestions': [
                    'Consolidate to fewer technologies',
                    'Define technology standards',
                    'Create migration plan',
                ],
                'expected_benefit': 'Reduce onboarding time by 50%',
            })

        return optimizations

    def _identify_coupled_files(self, hotspots: List[Dict]) -> List[str]:
        """Identify files that change together frequently."""
        # Simple heuristic: files in same directory with high change frequency
        directories = defaultdict(list)
        for hotspot in hotspots:
            file_path = hotspot.get('file', '')
            if '/' in file_path:
                directory = '/'.join(file_path.split('/')[:-1])
                directories[directory].append(file_path)

        coupled = []
        for directory, files in directories.items():
            if len(files) > 2:
                coupled.extend(files)

        return coupled

    def predict_milestones(self) -> List[Dict[str, Any]]:
        """Predict future project milestones.

        Returns:
            List of predicted milestones.
        """
        milestones = []
        now = datetime.now()

        # Version release prediction
        growth = self.data.get('growth_metrics', {})
        if growth.get('average_monthly_additions', 0) > 500:
            milestones.append({
                'type': 'major_release',
                'estimated_date': (now + timedelta(days=90)).isoformat(),
                'confidence': 'medium',
                'basis': 'High development activity',
            })

        # Refactoring milestone
        tech_debt = self.predict_technical_debt()
        if tech_debt['severity'] == 'critical':
            milestones.append({
                'type': 'debt_reduction_sprint',
                'estimated_date': (now + timedelta(days=30)).isoformat(),
                'confidence': 'high',
                'basis': 'Critical technical debt level',
            })

        # Team growth milestone
        contributors = self.data.get('contributor_patterns', {})
        if contributors.get('bus_factor', 1) < 3:
            milestones.append({
                'type': 'team_expansion',
                'estimated_date': (now + timedelta(days=60)).isoformat(),
                'confidence': 'medium',
                'basis': 'Low bus factor requires team growth',
            })

        # Stability milestone
        stability = self.data.get('stability_score', 100)
        if stability < 50:
            milestones.append({
                'type': 'stability_improvement',
                'estimated_date': (now + timedelta(days=45)).isoformat(),
                'confidence': 'high',
                'basis': 'Low stability score needs addressing',
            })

        return milestones

    def forecast_health(self) -> Dict[str, Any]:
        """Forecast overall project health.

        Returns:
            Health forecast for different time periods.
        """
        current_health = self._calculate_current_health()

        # Project health trajectory
        velocity_trend = self.data.get('code_velocity', {}).get('velocity_trend', 'stable')
        contributor_trend = self._calculate_contributor_trend()
        debt_trend = self._calculate_debt_trend()

        # Calculate health scores for future periods
        health_30_days = current_health
        health_90_days = current_health
        health_1_year = current_health

        # Adjust based on trends
        if velocity_trend == 'decreasing':
            health_30_days -= 5
            health_90_days -= 10
            health_1_year -= 20

        if contributor_trend == 'declining':
            health_30_days -= 10
            health_90_days -= 20
            health_1_year -= 30

        if debt_trend == 'increasing':
            health_30_days -= 5
            health_90_days -= 15
            health_1_year -= 25

        return {
            'current_health': current_health,
            'health_30_days': max(0, health_30_days),
            'health_90_days': max(0, health_90_days),
            'health_1_year': max(0, health_1_year),
            'trend': self._classify_health_trend(current_health, health_1_year),
            'factors': {
                'velocity_trend': velocity_trend,
                'contributor_trend': contributor_trend,
                'debt_trend': debt_trend,
            },
            'recommendations': self._generate_health_recommendations(current_health),
        }

    def _calculate_current_health(self) -> float:
        """Calculate current project health score (0-100)."""
        factors = []

        # Stability factor
        stability = self.data.get('stability_score', 50)
        factors.append(stability)

        # Contributor health
        contributors = self.data.get('contributor_patterns', {})
        bus_factor = contributors.get('bus_factor', 1)
        contributor_score = min(100, bus_factor * 20)
        factors.append(contributor_score)

        # Technical debt impact
        tech_debt = self.predict_technical_debt()
        debt_severity = tech_debt.get('severity', 'medium')
        debt_scores = {'low': 80, 'medium': 60, 'high': 40, 'critical': 20}
        factors.append(debt_scores.get(debt_severity, 50))

        # Activity level
        velocity = self.data.get('code_velocity', {})
        if velocity.get('current_velocity', 0) > 0:
            factors.append(70)
        else:
            factors.append(30)

        return statistics.mean(factors) if factors else 50

    def _calculate_contributor_trend(self) -> str:
        """Calculate contributor trend."""
        contributors = self.data.get('contributor_patterns', {})
        active = contributors.get('active_contributors', 0)
        total = contributors.get('total_contributors', 1)

        if active < total * 0.3:
            return 'declining'
        elif active > total * 0.7:
            return 'growing'
        else:
            return 'stable'

    def _calculate_debt_trend(self) -> str:
        """Calculate technical debt trend."""
        tech_debt = self.predict_technical_debt()
        interest_rate = tech_debt.get('monthly_interest_rate', 0)

        if interest_rate > 0.03:
            return 'increasing'
        elif interest_rate < 0.01:
            return 'decreasing'
        else:
            return 'stable'

    def _classify_health_trend(self, current: float, future: float) -> str:
        """Classify health trend."""
        change = future - current

        if change > 10:
            return 'improving'
        elif change < -10:
            return 'declining'
        else:
            return 'stable'

    def _generate_health_recommendations(self, health_score: float) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []

        if health_score < 30:
            recommendations.append('URGENT: Project health is critical - immediate intervention required')
            recommendations.append('Consider project restructuring or migration')
        elif health_score < 50:
            recommendations.append('Prioritize technical debt reduction')
            recommendations.append('Increase test coverage and documentation')
        elif health_score < 70:
            recommendations.append('Focus on improving development workflow')
            recommendations.append('Address identified hotspots')
        else:
            recommendations.append('Maintain current practices')
            recommendations.append('Consider optimizations for further improvement')

        return recommendations

    def export_predictions_jsonl(self) -> str:
        """Export predictions as JSONL.

        Returns:
            JSONL string of all predictions.
        """
        all_predictions = self.predict_all()
        output_lines = []

        # Flatten predictions into JSONL format
        for category, predictions in all_predictions.items():
            if isinstance(predictions, dict):
                output_lines.append(json.dumps({
                    'type': 'prediction',
                    'category': category,
                    **predictions
                }))
            elif isinstance(predictions, list):
                for item in predictions:
                    output_lines.append(json.dumps({
                        'type': 'prediction',
                        'category': category,
                        **item
                    }))

        return '\n'.join(output_lines)