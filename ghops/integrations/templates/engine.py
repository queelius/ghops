"""
Template engine for applying and creating projects from templates.
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import subprocess
import yaml
import toml

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Engine for template application and project generation."""

    def __init__(self, template: Dict[str, Any]):
        """Initialize template engine.

        Args:
            template: Template definition dictionary.
        """
        self.template = template
        self.variables = {}
        self.resolved_files = {}

    def set_variables(self, variables: Dict[str, str]):
        """Set template variables.

        Args:
            variables: Dictionary of variable values.
        """
        # Set provided variables
        self.variables = variables.copy()

        # Add automatic variables
        self.variables.update({
            'year': str(datetime.now().year),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
        })

        # Apply defaults for missing variables
        defaults = self._get_default_variables()
        for key, value in defaults.items():
            if key not in self.variables:
                self.variables[key] = value

    def _get_default_variables(self) -> Dict[str, str]:
        """Get default values for template variables."""
        defaults = {
            'project_name': 'my_project',
            'project_description': 'A new project',
            'version': '0.1.0',
            'author': os.environ.get('USER', 'author'),
            'email': f"{os.environ.get('USER', 'user')}@example.com",
            'license': 'MIT',
            'project_url': 'https://github.com/user/project',
            'source_dir': 'src',
            'test_dir': 'tests',
            'docs_dir': 'docs',
            'build_dir': 'build',
        }
        return defaults

    def apply_template(self, target_path: str, interactive: bool = False) -> Dict[str, Any]:
        """Apply template to create a new project.

        Args:
            target_path: Path where to create the project.
            interactive: Whether to prompt for variable values.

        Returns:
            Application result.
        """
        target = Path(target_path)

        # Interactive variable configuration
        if interactive:
            self._configure_variables_interactive()

        # Create project structure
        result = {
            'target_path': str(target),
            'created_files': [],
            'created_directories': [],
            'executed_commands': [],
            'status': 'success',
        }

        try:
            # Create target directory
            target.mkdir(parents=True, exist_ok=True)

            # Create directory structure
            structure = self.template.get('structure', {})
            for parent, dirs in structure.get('directories', {}).items():
                for dir_info in dirs:
                    dir_path = target / self._resolve_template(dir_info['name'])
                    dir_path.mkdir(parents=True, exist_ok=True)
                    result['created_directories'].append(str(dir_path))

            # Create files from templates
            file_templates = self.template.get('files', {})
            for file_path, content in file_templates.items():
                resolved_path = self._resolve_template(file_path)
                full_path = target / resolved_path

                # Ensure parent directory exists
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Write resolved content
                resolved_content = self._resolve_template(content)
                with open(full_path, 'w') as f:
                    f.write(resolved_content)

                result['created_files'].append(str(full_path))

            # Create additional files based on patterns
            self._create_pattern_files(target, result)

            # Initialize git repository if not exists
            if not (target / '.git').exists():
                subprocess.run(['git', 'init'], cwd=target, capture_output=True)
                result['executed_commands'].append('git init')

            # Install dependencies if specified
            if self.variables.get('install_dependencies', False):
                self._install_dependencies(target, result)

            # Run post-creation hooks
            self._run_post_creation_hooks(target, result)

        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"Template application failed: {e}")

        return result

    def _configure_variables_interactive(self):
        """Interactively configure template variables."""
        print("\nTemplate Variable Configuration")
        print("=" * 40)

        # Get variable definitions from template
        var_defs = self.template.get('variables', {})

        for category, variables in var_defs.items():
            if not variables:
                continue

            print(f"\n{category.upper()} Variables:")

            for var_name, var_template in variables.items():
                # Get current value or default
                current_value = self.variables.get(var_name, var_template.strip('{{}}'))

                # Prompt for new value
                prompt = f"  {var_name} [{current_value}]: "
                new_value = input(prompt).strip()

                if new_value:
                    self.variables[var_name] = new_value

    def _resolve_template(self, text: str) -> str:
        """Resolve template variables in text.

        Args:
            text: Text containing template variables.

        Returns:
            Resolved text.
        """
        resolved = text

        # Replace {{variable}} patterns
        for var_name, var_value in self.variables.items():
            patterns = [
                f'{{{{{var_name}}}}}',  # {{variable}}
                f'${{{var_name}}}',  # ${variable}
                f'${var_name}',  # $variable
            ]

            for pattern in patterns:
                resolved = resolved.replace(pattern, str(var_value))

        # Handle special transformations
        resolved = self._apply_transformations(resolved)

        return resolved

    def _apply_transformations(self, text: str) -> str:
        """Apply special transformations to resolved text."""
        # Convert project_name to different cases
        if 'project_name' in self.variables:
            name = self.variables['project_name']

            # Snake case
            snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
            text = text.replace('{{project_name_snake}}', snake_case)

            # Kebab case
            kebab_case = re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()
            text = text.replace('{{project_name_kebab}}', kebab_case)

            # Pascal case
            pascal_case = ''.join(word.capitalize() for word in re.split(r'[-_\s]', name))
            text = text.replace('{{project_name_pascal}}', pascal_case)

            # Camel case
            camel_case = pascal_case[0].lower() + pascal_case[1:]
            text = text.replace('{{project_name_camel}}', camel_case)

        return text

    def _create_pattern_files(self, target: Path, result: Dict):
        """Create files based on template patterns."""
        patterns = self.template.get('patterns', {})

        # Create test files if testing pattern detected
        if patterns.get('testing', {}).get('test_framework'):
            framework = patterns['testing']['test_framework']
            self._create_test_files(target, framework, result)

        # Create CI/CD files if workflow patterns detected
        workflows = self.template.get('workflows', [])
        if workflows:
            self._create_workflow_files(target, workflows, result)

        # Create configuration files
        configs = self.template.get('configurations', {})
        if configs:
            self._create_config_files(target, configs, result)

    def _create_test_files(self, target: Path, framework: str, result: Dict):
        """Create test files based on framework."""
        test_dir = target / self.variables.get('test_dir', 'tests')
        test_dir.mkdir(parents=True, exist_ok=True)

        if framework == 'pytest':
            # Create pytest.ini
            pytest_ini = target / 'pytest.ini'
            content = """[pytest]
testpaths = {test_dir}
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov={source_dir} --cov-report=html
""".format(**self.variables)

            with open(pytest_ini, 'w') as f:
                f.write(content)
            result['created_files'].append(str(pytest_ini))

            # Create sample test
            sample_test = test_dir / f"test_{self.variables.get('project_name', 'sample')}.py"
            test_content = f"""\"\"\"Tests for {self.variables.get('project_name', 'project')}.\"\"\"

import pytest


def test_example():
    \"\"\"Example test.\"\"\"
    assert True


class Test{self.variables.get('project_name_pascal', 'Project')}:
    \"\"\"Test class for {self.variables.get('project_name', 'project')}.\"\"\"

    def test_initialization(self):
        \"\"\"Test initialization.\"\"\"
        assert True
"""
            with open(sample_test, 'w') as f:
                f.write(test_content)
            result['created_files'].append(str(sample_test))

        elif framework == 'jest':
            # Create jest.config.js
            jest_config = target / 'jest.config.js'
            content = """module.exports = {{
  testEnvironment: 'node',
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coveragePathIgnorePatterns: ['/node_modules/'],
  testMatch: ['**/__tests__/**/*.js', '**/?(*.)+(spec|test).js'],
}};
"""
            with open(jest_config, 'w') as f:
                f.write(content)
            result['created_files'].append(str(jest_config))

    def _create_workflow_files(self, target: Path, workflows: List[Dict], result: Dict):
        """Create CI/CD workflow files."""
        for workflow in workflows:
            if workflow.get('type') == 'github_actions':
                # Create GitHub Actions workflow
                workflow_dir = target / '.github' / 'workflows'
                workflow_dir.mkdir(parents=True, exist_ok=True)

                workflow_file = workflow_dir / 'ci.yml'
                content = self._generate_github_workflow()

                with open(workflow_file, 'w') as f:
                    f.write(content)
                result['created_files'].append(str(workflow_file))

    def _generate_github_workflow(self) -> str:
        """Generate GitHub Actions workflow."""
        language = self.template.get('metadata', {}).get('language', 'Python')

        if language == 'Python':
            return f"""name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10']

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: ${{{{ matrix.python-version }}}}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        pytest
    - name: Upload coverage
      uses: codecov/codecov-action@v2
"""
        elif language == 'JavaScript':
            return """name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [14.x, 16.x, 18.x]

    steps:
    - uses: actions/checkout@v2
    - name: Use Node.js
      uses: actions/setup-node@v2
      with:
        node-version: ${{ matrix.node-version }}
    - run: npm ci
    - run: npm test
    - run: npm run build --if-present
"""
        else:
            return """name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2
    - name: Build
      run: |
        echo "Add build steps here"
    - name: Test
      run: |
        echo "Add test steps here"
"""

    def _create_config_files(self, target: Path, configs: Dict, result: Dict):
        """Create configuration files."""
        # Create .env.example if environment variables are used
        if configs.get('environment_variables'):
            env_example = target / '.env.example'
            content = "# Environment Variables\n"
            for var in configs['environment_variables']:
                content += f"{var}=your_{var.lower()}_here\n"

            with open(env_example, 'w') as f:
                f.write(content)
            result['created_files'].append(str(env_example))

        # Create config directory and sample config
        if configs.get('config_patterns'):
            config_dir = target / 'config'
            config_dir.mkdir(parents=True, exist_ok=True)

            if 'yaml_config' in configs['config_patterns']:
                config_file = config_dir / 'config.yml'
                content = f"""# {self.variables.get('project_name', 'Project')} Configuration

app:
  name: {self.variables.get('project_name', 'app')}
  version: {self.variables.get('version', '0.1.0')}
  debug: false

database:
  host: localhost
  port: 5432
  name: {self.variables.get('project_name_snake', 'app_db')}

logging:
  level: info
  format: json
"""
                with open(config_file, 'w') as f:
                    f.write(content)
                result['created_files'].append(str(config_file))

    def _install_dependencies(self, target: Path, result: Dict):
        """Install project dependencies."""
        deps = self.template.get('dependencies', {})

        if 'python' in deps:
            # Create requirements.txt
            req_file = target / 'requirements.txt'
            with open(req_file, 'w') as f:
                for dep in deps['python']:
                    f.write(f"{dep}\n")
            result['created_files'].append(str(req_file))

            # Install if pip is available
            try:
                subprocess.run(['pip', 'install', '-r', 'requirements.txt'],
                              cwd=target, capture_output=True, check=True)
                result['executed_commands'].append('pip install -r requirements.txt')
            except:
                logger.warning("Could not install Python dependencies")

        if 'node' in deps:
            # Create package.json if not exists
            package_json = target / 'package.json'
            if not package_json.exists():
                package_data = {
                    'name': self.variables.get('project_name_kebab', 'project'),
                    'version': self.variables.get('version', '0.1.0'),
                    'description': self.variables.get('project_description', ''),
                    'dependencies': {},
                }

                for dep in deps['node']:
                    package_data['dependencies'][dep] = '*'

                with open(package_json, 'w') as f:
                    json.dump(package_data, f, indent=2)
                result['created_files'].append(str(package_json))

            # Install if npm is available
            try:
                subprocess.run(['npm', 'install'], cwd=target, capture_output=True, check=True)
                result['executed_commands'].append('npm install')
            except:
                logger.warning("Could not install Node dependencies")

    def _run_post_creation_hooks(self, target: Path, result: Dict):
        """Run post-creation hooks."""
        # Initial git commit
        if self.variables.get('create_initial_commit', True):
            try:
                subprocess.run(['git', 'add', '-A'], cwd=target, capture_output=True)
                subprocess.run(['git', 'commit', '-m', 'Initial commit from template'],
                              cwd=target, capture_output=True)
                result['executed_commands'].append('git commit')
            except:
                logger.warning("Could not create initial commit")

        # Run custom hooks from template
        hooks = self.template.get('hooks', [])
        for hook in hooks:
            if hook.get('type') == 'command':
                command = self._resolve_template(hook['command'])
                try:
                    subprocess.run(command, shell=True, cwd=target, capture_output=True)
                    result['executed_commands'].append(command)
                except:
                    logger.warning(f"Hook failed: {command}")

    def validate_template(self) -> Dict[str, Any]:
        """Validate template definition.

        Returns:
            Validation results.
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
        }

        # Check required fields
        if not self.template.get('name'):
            validation['errors'].append('Template missing name')
            validation['valid'] = False

        # Check file templates
        for file_path, content in self.template.get('files', {}).items():
            if not content:
                validation['warnings'].append(f"Empty template for {file_path}")

        # Check variables
        variables = self.template.get('variables', {})
        for category, vars_dict in variables.items():
            if not isinstance(vars_dict, dict):
                validation['errors'].append(f"Invalid variables in category: {category}")
                validation['valid'] = False

        # Check patterns
        patterns = self.template.get('patterns', {})
        if patterns and not isinstance(patterns, dict):
            validation['errors'].append("Invalid patterns format")
            validation['valid'] = False

        return validation

    def merge_templates(self, other_template: Dict[str, Any]) -> Dict[str, Any]:
        """Merge another template into this one.

        Args:
            other_template: Template to merge.

        Returns:
            Merged template.
        """
        merged = self.template.copy()

        # Merge metadata
        if 'metadata' not in merged:
            merged['metadata'] = {}
        merged['metadata'].update(other_template.get('metadata', {}))

        # Merge structure
        if 'structure' not in merged:
            merged['structure'] = {}
        other_structure = other_template.get('structure', {})
        for key, value in other_structure.items():
            if key in merged['structure'] and isinstance(value, dict):
                merged['structure'][key].update(value)
            else:
                merged['structure'][key] = value

        # Merge files
        if 'files' not in merged:
            merged['files'] = {}
        merged['files'].update(other_template.get('files', {}))

        # Merge patterns
        if 'patterns' not in merged:
            merged['patterns'] = {}
        merged['patterns'].update(other_template.get('patterns', {}))

        # Merge variables
        if 'variables' not in merged:
            merged['variables'] = {}
        for category, vars_dict in other_template.get('variables', {}).items():
            if category not in merged['variables']:
                merged['variables'][category] = {}
            merged['variables'][category].update(vars_dict)

        return merged

    def export_jsonl(self) -> str:
        """Export template operations as JSONL.

        Returns:
            JSONL string of template data.
        """
        lines = []

        # Template metadata
        lines.append(json.dumps({
            'type': 'template',
            'name': self.template.get('name'),
            'source': self.template.get('source'),
            'language': self.template.get('metadata', {}).get('language'),
            'framework': self.template.get('metadata', {}).get('framework'),
        }))

        # Variables
        for var_name, var_value in self.variables.items():
            lines.append(json.dumps({
                'type': 'variable',
                'name': var_name,
                'value': var_value,
            }))

        # Files
        for file_path in self.template.get('files', {}).keys():
            lines.append(json.dumps({
                'type': 'file_template',
                'path': file_path,
            }))

        return '\n'.join(lines)