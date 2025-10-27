"""
Workflow definition parser for YAML files.
"""

import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkflowParser:
    """Parse and validate workflow definitions from YAML."""

    @staticmethod
    def load_workflow(file_path: str) -> Dict[str, Any]:
        """Load workflow definition from YAML file.

        Args:
            file_path: Path to workflow YAML file.

        Returns:
            Parsed workflow definition.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")

        with open(path, 'r') as f:
            workflow = yaml.safe_load(f)

        # Validate structure
        WorkflowParser.validate_workflow(workflow)

        # Process includes
        if 'include' in workflow:
            workflow = WorkflowParser._process_includes(workflow, path.parent)

        # Process templates
        if 'templates' in workflow and 'tasks' in workflow:
            workflow['tasks'] = WorkflowParser._expand_templates(
                workflow['tasks'],
                workflow['templates']
            )

        return workflow

    @staticmethod
    def validate_workflow(workflow: Dict[str, Any]):
        """Validate workflow definition structure.

        Args:
            workflow: Workflow definition dictionary.

        Raises:
            ValueError: If workflow is invalid.
        """
        if not isinstance(workflow, dict):
            raise ValueError("Workflow must be a dictionary")

        # Required fields
        if 'name' not in workflow:
            raise ValueError("Workflow missing required field 'name'")

        if 'tasks' not in workflow:
            raise ValueError("Workflow missing required field 'tasks'")

        if not isinstance(workflow['tasks'], list):
            raise ValueError("Workflow 'tasks' must be a list")

        # Validate each task
        for i, task in enumerate(workflow['tasks']):
            WorkflowParser._validate_task(task, i)

    @staticmethod
    def _validate_task(task: Dict[str, Any], index: int):
        """Validate individual task definition.

        Args:
            task: Task definition.
            index: Task index in list.

        Raises:
            ValueError: If task is invalid.
        """
        if not isinstance(task, dict):
            raise ValueError(f"Task {index} must be a dictionary")

        if 'id' not in task:
            raise ValueError(f"Task {index} missing required field 'id'")

        if 'type' not in task:
            raise ValueError(f"Task '{task['id']}' missing required field 'type'")

        valid_types = ['shell', 'ghops', 'python', 'parallel', 'template']
        if task['type'] not in valid_types:
            raise ValueError(f"Task '{task['id']}' has invalid type '{task['type']}'")

        # Type-specific validation
        if task['type'] == 'shell' and 'command' not in task:
            raise ValueError(f"Shell task '{task['id']}' missing required field 'command'")

        if task['type'] == 'ghops' and 'command' not in task:
            raise ValueError(f"Ghops task '{task['id']}' missing required field 'command'")

        if task['type'] == 'python' and 'code' not in task:
            raise ValueError(f"Python task '{task['id']}' missing required field 'code'")

        if task['type'] == 'parallel' and 'tasks' not in task:
            raise ValueError(f"Parallel task '{task['id']}' missing required field 'tasks'")

    @staticmethod
    def _process_includes(workflow: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
        """Process include directives in workflow.

        Args:
            workflow: Workflow definition.
            base_dir: Base directory for relative paths.

        Returns:
            Workflow with includes processed.
        """
        includes = workflow.get('include', [])
        if isinstance(includes, str):
            includes = [includes]

        for include_path in includes:
            full_path = base_dir / include_path
            if full_path.exists():
                with open(full_path, 'r') as f:
                    include_data = yaml.safe_load(f)

                # Merge included data
                if 'templates' in include_data:
                    workflow.setdefault('templates', {}).update(include_data['templates'])

                if 'variables' in include_data:
                    workflow.setdefault('variables', {}).update(include_data['variables'])

                if 'tasks' in include_data:
                    # Prepend included tasks
                    workflow['tasks'] = include_data['tasks'] + workflow.get('tasks', [])

        return workflow

    @staticmethod
    def _expand_templates(tasks: List[Dict[str, Any]],
                         templates: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Expand template references in tasks.

        Args:
            tasks: List of task definitions.
            templates: Template definitions.

        Returns:
            Tasks with templates expanded.
        """
        expanded = []

        for task in tasks:
            if task.get('type') == 'template':
                template_name = task.get('template')
                if template_name and template_name in templates:
                    # Create task from template
                    template = templates[template_name].copy()

                    # Override with task-specific values
                    for key, value in task.items():
                        if key not in ['type', 'template']:
                            template[key] = value

                    # Ensure task has an ID
                    if 'id' not in template:
                        template['id'] = task.get('id', template_name)

                    expanded.append(template)
                else:
                    # Template not found, keep original task
                    expanded.append(task)
            else:
                expanded.append(task)

        return expanded

    @staticmethod
    def create_example_workflow(workflow_type: str = 'basic') -> str:
        """Generate example workflow YAML.

        Args:
            workflow_type: Type of example ('basic', 'morning', 'release', 'dependency').

        Returns:
            YAML string of example workflow.
        """
        examples = {
            'basic': {
                'name': 'basic-workflow',
                'description': 'A basic example workflow',
                'variables': {
                    'repo_path': '.',
                    'branch': 'main',
                },
                'tasks': [
                    {
                        'id': 'status',
                        'type': 'ghops',
                        'name': 'Check repository status',
                        'command': 'status',
                        'args': ['--path', '${repo_path}'],
                    },
                    {
                        'id': 'update',
                        'type': 'shell',
                        'name': 'Update repository',
                        'command': 'git pull origin ${branch}',
                        'cwd': '${repo_path}',
                        'depends_on': ['status'],
                    },
                ]
            },
            'morning': {
                'name': 'morning-routine',
                'description': 'Daily morning repository maintenance',
                'schedule': '0 9 * * *',  # 9 AM daily
                'variables': {
                    'notification_email': 'dev@example.com',
                },
                'tasks': [
                    {
                        'id': 'fetch_all',
                        'type': 'parallel',
                        'name': 'Fetch all repository updates',
                        'tasks': [
                            {
                                'type': 'shell',
                                'command': 'git fetch --all --prune',
                                'cwd': '${repo}',
                            }
                        ],
                    },
                    {
                        'id': 'check_status',
                        'type': 'ghops',
                        'name': 'Check all repository statuses',
                        'command': 'status',
                        'args': ['--format', 'json'],
                        'parse_output': True,
                        'output_var': 'repo_statuses',
                        'depends_on': ['fetch_all'],
                    },
                    {
                        'id': 'check_updates',
                        'type': 'python',
                        'name': 'Check for available updates',
                        'code': '''
repos_needing_update = []
for status in context['repo_statuses']:
    if status.get('behind', 0) > 0:
        repos_needing_update.append(status['path'])
context['repos_to_update'] = repos_needing_update
context['update_count'] = len(repos_needing_update)
''',
                        'depends_on': ['check_status'],
                    },
                    {
                        'id': 'notify',
                        'type': 'shell',
                        'name': 'Send notification',
                        'command': 'echo "${update_count} repositories need updates" | mail -s "Morning Report" ${notification_email}',
                        'condition': 'update_count > 0',
                        'depends_on': ['check_updates'],
                    },
                ]
            },
            'release': {
                'name': 'release-pipeline',
                'description': 'Automated release workflow',
                'variables': {
                    'version': '${VERSION}',
                    'repo_path': '.',
                },
                'tasks': [
                    {
                        'id': 'validate',
                        'type': 'parallel',
                        'name': 'Run validation checks',
                        'tasks': [
                            {
                                'id': 'lint',
                                'type': 'shell',
                                'command': 'npm run lint',
                            },
                            {
                                'id': 'test',
                                'type': 'shell',
                                'command': 'npm test',
                            },
                            {
                                'id': 'build',
                                'type': 'shell',
                                'command': 'npm run build',
                            },
                        ],
                    },
                    {
                        'id': 'bump_version',
                        'type': 'shell',
                        'name': 'Bump version number',
                        'command': 'npm version ${version}',
                        'depends_on': ['validate'],
                    },
                    {
                        'id': 'create_tag',
                        'type': 'shell',
                        'name': 'Create git tag',
                        'command': 'git tag -a v${version} -m "Release version ${version}"',
                        'depends_on': ['bump_version'],
                    },
                    {
                        'id': 'push',
                        'type': 'shell',
                        'name': 'Push to remote',
                        'command': 'git push origin main --tags',
                        'depends_on': ['create_tag'],
                    },
                    {
                        'id': 'publish',
                        'type': 'parallel',
                        'name': 'Publish to registries',
                        'tasks': [
                            {
                                'type': 'shell',
                                'command': 'npm publish',
                            },
                            {
                                'type': 'ghops',
                                'command': 'social post',
                                'args': ['--message', 'Released version ${version}!'],
                            },
                        ],
                        'depends_on': ['push'],
                    },
                ]
            },
            'dependency': {
                'name': 'dependency-update',
                'description': 'Update all dependencies across repositories',
                'variables': {
                    'update_type': 'minor',  # major, minor, patch
                },
                'tasks': [
                    {
                        'id': 'scan',
                        'type': 'ghops',
                        'name': 'Scan for outdated dependencies',
                        'command': 'list',
                        'args': ['--filter', 'has_outdated_deps'],
                        'parse_output': True,
                        'output_var': 'repos_with_outdated',
                    },
                    {
                        'id': 'create_branches',
                        'type': 'python',
                        'name': 'Create update branches',
                        'code': '''
import subprocess
for repo in context['repos_with_outdated']:
    branch_name = f"deps-update-{context['update_type']}"
    subprocess.run(['git', 'checkout', '-b', branch_name], cwd=repo['path'])
    context[f'branch_{repo["name"]}'] = branch_name
''',
                        'depends_on': ['scan'],
                    },
                    {
                        'id': 'update_deps',
                        'type': 'python',
                        'name': 'Update dependencies',
                        'code': '''
import subprocess
for repo in context['repos_with_outdated']:
    if repo['package_type'] == 'npm':
        cmd = f"npm update --save-{context['update_type']}"
    elif repo['package_type'] == 'pip':
        cmd = "pip-compile --upgrade"
    subprocess.run(cmd.split(), cwd=repo['path'])
''',
                        'depends_on': ['create_branches'],
                    },
                    {
                        'id': 'test_updates',
                        'type': 'python',
                        'name': 'Test updated dependencies',
                        'code': '''
import subprocess
test_results = {}
for repo in context['repos_with_outdated']:
    result = subprocess.run(['npm', 'test'], cwd=repo['path'], capture_output=True)
    test_results[repo['name']] = result.returncode == 0
context['test_results'] = test_results
''',
                        'depends_on': ['update_deps'],
                    },
                    {
                        'id': 'create_prs',
                        'type': 'python',
                        'name': 'Create pull requests',
                        'code': '''
import subprocess
for repo_name, test_passed in context['test_results'].items():
    if test_passed:
        branch = context[f'branch_{repo_name}']
        subprocess.run(['gh', 'pr', 'create',
                       '--title', f'Update {context["update_type"]} dependencies',
                       '--body', 'Automated dependency update'],
                      cwd=f'./{repo_name}')
''',
                        'depends_on': ['test_updates'],
                    },
                ]
            }
        }

        workflow = examples.get(workflow_type, examples['basic'])
        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)

    @staticmethod
    def validate_cron_schedule(schedule: str) -> bool:
        """Validate cron schedule string.

        Args:
            schedule: Cron schedule string.

        Returns:
            True if valid, False otherwise.
        """
        parts = schedule.split()
        if len(parts) != 5:
            return False

        # Basic validation - could be enhanced
        ranges = [
            (0, 59),  # minute
            (0, 23),  # hour
            (1, 31),  # day
            (1, 12),  # month
            (0, 7),   # weekday
        ]

        for part, (min_val, max_val) in zip(parts, ranges):
            if part == '*':
                continue

            try:
                if '/' in part:
                    # Handle step values like */5
                    continue
                elif '-' in part:
                    # Handle ranges like 1-5
                    start, end = map(int, part.split('-'))
                    if not (min_val <= start <= end <= max_val):
                        return False
                elif ',' in part:
                    # Handle lists like 1,3,5
                    for val in part.split(','):
                        if not (min_val <= int(val) <= max_val):
                            return False
                else:
                    # Single value
                    if not (min_val <= int(part) <= max_val):
                        return False
            except (ValueError, TypeError):
                return False

        return True