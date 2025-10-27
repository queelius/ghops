"""
Template extractor for learning patterns from successful repositories.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
import subprocess
import ast
import yaml
import toml

logger = logging.getLogger(__name__)


class TemplateExtractor:
    """Extracts patterns and templates from successful repositories."""

    def __init__(self, repo_path: str):
        """Initialize template extractor.

        Args:
            repo_path: Path to the repository to extract from.
        """
        self.repo_path = Path(repo_path)
        self.patterns = {}
        self.variables = {}
        self.structure = {}
        self.metadata = {}

    def extract_template(self, template_name: str = None) -> Dict[str, Any]:
        """Extract a complete template from the repository.

        Args:
            template_name: Name for the template.

        Returns:
            Template definition dictionary.
        """
        if not template_name:
            template_name = self.repo_path.name

        # Extract various aspects
        template = {
            'name': template_name,
            'source': str(self.repo_path),
            'metadata': self._extract_metadata(),
            'structure': self._extract_structure(),
            'patterns': self._extract_patterns(),
            'files': self._extract_file_templates(),
            'workflows': self._extract_workflows(),
            'configurations': self._extract_configurations(),
            'variables': self._identify_variables(),
            'dependencies': self._extract_dependencies(),
            'best_practices': self._identify_best_practices(),
        }

        return template

    def _extract_metadata(self) -> Dict[str, Any]:
        """Extract repository metadata."""
        metadata = {
            'language': None,
            'framework': None,
            'type': None,  # library, application, service, etc.
            'license': None,
            'description': None,
        }

        # Detect primary language
        languages = self._detect_languages()
        if languages:
            metadata['language'] = languages[0]

        # Detect framework
        metadata['framework'] = self._detect_framework()

        # Detect project type
        metadata['type'] = self._detect_project_type()

        # Extract license
        license_files = list(self.repo_path.glob('LICENSE*'))
        if license_files:
            metadata['license'] = self._identify_license(license_files[0])

        # Extract description from README
        readme_files = list(self.repo_path.glob('README*'))
        if readme_files:
            with open(readme_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Extract first paragraph
                lines = content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        metadata['description'] = line.strip()
                        break

        return metadata

    def _detect_languages(self) -> List[str]:
        """Detect programming languages used."""
        language_extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
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
        }

        language_counts = Counter()
        for file_path in self.repo_path.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix
                if ext in language_extensions:
                    language_counts[language_extensions[ext]] += 1

        return [lang for lang, _ in language_counts.most_common()]

    def _detect_framework(self) -> Optional[str]:
        """Detect the framework being used."""
        framework_indicators = {
            'Django': ['manage.py', 'wsgi.py', 'django'],
            'Flask': ['app.py', 'flask', 'wsgi.py'],
            'FastAPI': ['main.py', 'fastapi', 'uvicorn'],
            'React': ['package.json', 'react', 'jsx'],
            'Vue': ['vue.config.js', 'vue', '.vue'],
            'Angular': ['angular.json', 'ng', '@angular'],
            'Express': ['app.js', 'express', 'server.js'],
            'Spring': ['pom.xml', 'spring', 'boot'],
            'Rails': ['Gemfile', 'rails', 'config.ru'],
            'Laravel': ['artisan', 'laravel', 'composer.json'],
        }

        for framework, indicators in framework_indicators.items():
            matches = 0
            for indicator in indicators:
                if self._file_or_content_exists(indicator):
                    matches += 1

            if matches >= 2:
                return framework

        return None

    def _file_or_content_exists(self, pattern: str) -> bool:
        """Check if a file exists or pattern appears in files."""
        # Check for file
        if list(self.repo_path.glob(f'**/{pattern}')):
            return True

        # Check in file contents (limited search)
        for file_path in self.repo_path.glob('**/*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.json', '.xml']:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        if pattern in f.read():
                            return True
                except:
                    continue

        return False

    def _detect_project_type(self) -> str:
        """Detect the type of project."""
        indicators = {
            'library': ['setup.py', 'setup.cfg', 'pyproject.toml', 'package.json', 'Cargo.toml'],
            'application': ['main.py', 'app.py', 'server.js', 'index.js', 'main.go'],
            'service': ['Dockerfile', 'docker-compose.yml', 'kubernetes.yml'],
            'cli': ['cli.py', '__main__.py', 'bin/', 'cmd/'],
            'website': ['index.html', 'static/', 'public/'],
        }

        scores = defaultdict(int)
        for type_name, files in indicators.items():
            for file_pattern in files:
                if self._file_or_content_exists(file_pattern):
                    scores[type_name] += 1

        if scores:
            return max(scores, key=scores.get)
        return 'unknown'

    def _identify_license(self, license_file: Path) -> str:
        """Identify the license type from file content."""
        with open(license_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()

        licenses = {
            'MIT': ['mit license', 'permission is hereby granted'],
            'Apache-2.0': ['apache license', 'version 2.0'],
            'GPL-3.0': ['gnu general public license', 'version 3'],
            'BSD-3-Clause': ['bsd 3-clause', 'redistribution and use in source'],
            'ISC': ['isc license', 'permission to use, copy'],
            'MPL-2.0': ['mozilla public license', 'version 2.0'],
        }

        for license_name, patterns in licenses.items():
            if any(pattern in content for pattern in patterns):
                return license_name

        return 'Unknown'

    def _extract_structure(self) -> Dict[str, Any]:
        """Extract directory structure patterns."""
        structure = {
            'directories': {},
            'key_files': [],
            'patterns': [],
        }

        # Map directory structure
        for path in self.repo_path.rglob('*'):
            if path.is_dir() and '.git' not in str(path):
                rel_path = path.relative_to(self.repo_path)
                depth = len(rel_path.parts)

                if depth <= 3:  # Limit depth
                    dir_name = rel_path.name
                    parent = str(rel_path.parent) if rel_path.parent != Path('.') else 'root'

                    if parent not in structure['directories']:
                        structure['directories'][parent] = []
                    structure['directories'][parent].append({
                        'name': dir_name,
                        'purpose': self._infer_directory_purpose(dir_name),
                    })

        # Identify key files
        key_file_patterns = [
            'README*', 'LICENSE*', 'setup.py', 'pyproject.toml',
            'package.json', 'Dockerfile', '.gitignore', 'Makefile',
            'requirements*.txt', '*.yml', '*.yaml', '*.toml'
        ]

        for pattern in key_file_patterns:
            for file_path in self.repo_path.glob(pattern):
                if file_path.is_file():
                    structure['key_files'].append({
                        'path': str(file_path.relative_to(self.repo_path)),
                        'type': self._classify_file_type(file_path),
                    })

        # Identify structural patterns
        structure['patterns'] = self._identify_structural_patterns()

        return structure

    def _infer_directory_purpose(self, dir_name: str) -> str:
        """Infer the purpose of a directory from its name."""
        purposes = {
            'src': 'source_code',
            'lib': 'libraries',
            'test': 'tests',
            'tests': 'tests',
            'docs': 'documentation',
            'doc': 'documentation',
            'examples': 'examples',
            'samples': 'examples',
            'scripts': 'scripts',
            'bin': 'binaries',
            'build': 'build_output',
            'dist': 'distribution',
            'static': 'static_assets',
            'public': 'public_assets',
            'templates': 'templates',
            'config': 'configuration',
            'migrations': 'database_migrations',
            'fixtures': 'test_fixtures',
            'vendor': 'third_party',
            'node_modules': 'dependencies',
        }

        return purposes.get(dir_name.lower(), 'general')

    def _classify_file_type(self, file_path: Path) -> str:
        """Classify the type/purpose of a file."""
        name = file_path.name.lower()

        if 'readme' in name:
            return 'documentation'
        elif 'license' in name:
            return 'license'
        elif name.endswith(('.yml', '.yaml')):
            return 'configuration'
        elif name == 'dockerfile':
            return 'container'
        elif name.endswith('.toml'):
            return 'configuration'
        elif 'requirements' in name:
            return 'dependencies'
        elif name == 'package.json':
            return 'package_manifest'
        elif name == 'setup.py':
            return 'setup'
        elif name == 'makefile':
            return 'build'
        elif name == '.gitignore':
            return 'vcs_ignore'
        else:
            return 'other'

    def _identify_structural_patterns(self) -> List[str]:
        """Identify common structural patterns."""
        patterns = []

        # Check for common patterns
        if (self.repo_path / 'src').exists():
            patterns.append('src_layout')
        if (self.repo_path / 'tests').exists() or (self.repo_path / 'test').exists():
            patterns.append('has_tests')
        if (self.repo_path / 'docs').exists():
            patterns.append('has_docs')
        if (self.repo_path / '.github' / 'workflows').exists():
            patterns.append('github_actions')
        if (self.repo_path / 'Dockerfile').exists():
            patterns.append('containerized')
        if (self.repo_path / 'setup.py').exists() or (self.repo_path / 'pyproject.toml').exists():
            patterns.append('python_package')
        if (self.repo_path / 'package.json').exists():
            patterns.append('node_package')

        return patterns

    def _extract_patterns(self) -> Dict[str, Any]:
        """Extract code patterns and idioms."""
        patterns = {
            'imports': self._extract_import_patterns(),
            'functions': self._extract_function_patterns(),
            'classes': self._extract_class_patterns(),
            'error_handling': self._extract_error_patterns(),
            'logging': self._extract_logging_patterns(),
            'testing': self._extract_testing_patterns(),
        }

        return patterns

    def _extract_import_patterns(self) -> Dict[str, List[str]]:
        """Extract common import patterns."""
        imports = defaultdict(list)

        # Python imports
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports['python'].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports['python'].append(node.module)
            except:
                continue

        # JavaScript/TypeScript imports
        for js_file in self.repo_path.glob('**/*.{js,ts,jsx,tsx}'):
            try:
                with open(js_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Simple regex for imports
                    import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
                    matches = re.findall(import_pattern, content)
                    imports['javascript'].extend(matches)
            except:
                continue

        # Deduplicate and get most common
        for lang in imports:
            counter = Counter(imports[lang])
            imports[lang] = [module for module, _ in counter.most_common(20)]

        return dict(imports)

    def _extract_function_patterns(self) -> Dict[str, Any]:
        """Extract function definition patterns."""
        patterns = {
            'naming_convention': None,
            'common_decorators': [],
            'parameter_patterns': [],
            'return_patterns': [],
        }

        function_names = []
        decorators = []

        # Analyze Python functions
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        function_names.append(node.name)

                        # Check decorators
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Name):
                                decorators.append(decorator.id)
                            elif isinstance(decorator, ast.Attribute):
                                decorators.append(decorator.attr)

                        # Analyze parameters
                        if len(node.args.args) > 0:
                            param_pattern = len(node.args.args)
                            patterns['parameter_patterns'].append(param_pattern)
            except:
                continue

        # Determine naming convention
        if function_names:
            snake_case = sum(1 for name in function_names if '_' in name)
            camel_case = sum(1 for name in function_names if name[0].islower() and any(c.isupper() for c in name))

            if snake_case > camel_case:
                patterns['naming_convention'] = 'snake_case'
            elif camel_case > snake_case:
                patterns['naming_convention'] = 'camelCase'
            else:
                patterns['naming_convention'] = 'mixed'

        # Most common decorators
        if decorators:
            decorator_counts = Counter(decorators)
            patterns['common_decorators'] = [d for d, _ in decorator_counts.most_common(5)]

        return patterns

    def _extract_class_patterns(self) -> Dict[str, Any]:
        """Extract class definition patterns."""
        patterns = {
            'naming_convention': None,
            'inheritance_patterns': [],
            'common_methods': [],
            'design_patterns': [],
        }

        class_names = []
        base_classes = []
        method_names = []

        # Analyze Python classes
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_names.append(node.name)

                        # Check base classes
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                base_classes.append(base.id)

                        # Get method names
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                method_names.append(item.name)
            except:
                continue

        # Determine naming convention
        if class_names:
            pascal_case = sum(1 for name in class_names if name[0].isupper())
            if pascal_case > len(class_names) * 0.8:
                patterns['naming_convention'] = 'PascalCase'

        # Common base classes
        if base_classes:
            base_counts = Counter(base_classes)
            patterns['inheritance_patterns'] = [b for b, _ in base_counts.most_common(5)]

        # Common method names
        if method_names:
            method_counts = Counter(method_names)
            patterns['common_methods'] = [m for m, _ in method_counts.most_common(10)]

        # Detect design patterns
        patterns['design_patterns'] = self._detect_design_patterns(class_names, method_names)

        return patterns

    def _detect_design_patterns(self, class_names: List[str], method_names: List[str]) -> List[str]:
        """Detect common design patterns."""
        patterns = []

        # Singleton pattern
        if any('singleton' in name.lower() for name in class_names) or \
           any('instance' in name.lower() for name in method_names):
            patterns.append('singleton')

        # Factory pattern
        if any('factory' in name.lower() for name in class_names) or \
           any('create' in name.lower() for name in method_names):
            patterns.append('factory')

        # Observer pattern
        if any('observer' in name.lower() for name in class_names) or \
           any('notify' in name.lower() for name in method_names):
            patterns.append('observer')

        # Strategy pattern
        if any('strategy' in name.lower() for name in class_names):
            patterns.append('strategy')

        # Builder pattern
        if any('builder' in name.lower() for name in class_names) or \
           any('build' in name.lower() for name in method_names):
            patterns.append('builder')

        return patterns

    def _extract_error_patterns(self) -> Dict[str, Any]:
        """Extract error handling patterns."""
        patterns = {
            'exception_types': [],
            'error_handling_style': None,
            'common_error_messages': [],
        }

        exception_types = []
        error_keywords = []

        # Analyze Python error handling
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                    # Find exception types
                    exception_pattern = r'except\s+(\w+)'
                    matches = re.findall(exception_pattern, content)
                    exception_types.extend(matches)

                    # Find raise statements
                    raise_pattern = r'raise\s+(\w+)'
                    matches = re.findall(raise_pattern, content)
                    exception_types.extend(matches)

                    # Find error keywords
                    if 'try:' in content:
                        error_keywords.append('try_except')
                    if 'finally:' in content:
                        error_keywords.append('finally')
                    if 'assert' in content:
                        error_keywords.append('assertions')
            except:
                continue

        # Analyze patterns
        if exception_types:
            type_counts = Counter(exception_types)
            patterns['exception_types'] = [e for e, _ in type_counts.most_common(10)]

        if error_keywords:
            if 'try_except' in error_keywords:
                patterns['error_handling_style'] = 'exception_based'
            if 'assertions' in error_keywords:
                if patterns['error_handling_style']:
                    patterns['error_handling_style'] += '_with_assertions'
                else:
                    patterns['error_handling_style'] = 'assertion_based'

        return patterns

    def _extract_logging_patterns(self) -> Dict[str, Any]:
        """Extract logging patterns."""
        patterns = {
            'logging_framework': None,
            'log_levels': [],
            'log_format': None,
        }

        log_statements = []

        # Check Python logging
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                    if 'import logging' in content:
                        patterns['logging_framework'] = 'python_logging'

                    # Find log levels
                    for level in ['debug', 'info', 'warning', 'error', 'critical']:
                        if f'log.{level}' in content or f'logger.{level}' in content:
                            patterns['log_levels'].append(level)

                    # Find print statements (fallback logging)
                    if 'print(' in content and not patterns['logging_framework']:
                        patterns['logging_framework'] = 'print_statements'
            except:
                continue

        return patterns

    def _extract_testing_patterns(self) -> Dict[str, Any]:
        """Extract testing patterns."""
        patterns = {
            'test_framework': None,
            'test_structure': None,
            'assertion_style': None,
            'coverage_configured': False,
        }

        # Check for test frameworks
        test_indicators = {
            'pytest': ['pytest', 'test_*.py', '*_test.py'],
            'unittest': ['unittest', 'TestCase'],
            'jest': ['jest', '*.test.js', '*.spec.js'],
            'mocha': ['mocha', 'describe(', 'it('],
            'junit': ['junit', '@Test'],
        }

        for framework, indicators in test_indicators.items():
            for indicator in indicators:
                if self._file_or_content_exists(indicator):
                    patterns['test_framework'] = framework
                    break
            if patterns['test_framework']:
                break

        # Check for coverage configuration
        coverage_files = ['.coveragerc', 'coverage.xml', '.coverage', 'jest.config.js']
        for cov_file in coverage_files:
            if (self.repo_path / cov_file).exists():
                patterns['coverage_configured'] = True
                break

        # Determine test structure
        if (self.repo_path / 'tests').exists():
            patterns['test_structure'] = 'separate_tests_directory'
        elif any(self.repo_path.glob('**/test_*.py')):
            patterns['test_structure'] = 'alongside_code'

        return patterns

    def _extract_file_templates(self) -> Dict[str, str]:
        """Extract key files as templates."""
        templates = {}

        # Files to extract as templates
        template_files = [
            'README.md',
            'LICENSE',
            '.gitignore',
            'Makefile',
            'setup.py',
            'pyproject.toml',
            'requirements.txt',
            'package.json',
            'Dockerfile',
            '.github/workflows/ci.yml',
        ]

        for file_pattern in template_files:
            file_path = self.repo_path / file_pattern

            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Templatize content
                    templatized = self._templatize_content(content, file_pattern)
                    templates[file_pattern] = templatized
                except:
                    continue

        return templates

    def _templatize_content(self, content: str, filename: str) -> str:
        """Convert content to template with variables."""
        # Replace common patterns with template variables
        replacements = [
            (r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', '{{project_name}}'),  # Project names
            (r'\d{4}', '{{year}}'),  # Years
            (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '{{email}}'),  # Emails
            (r'https?://[^\s]+', '{{url}}'),  # URLs
            (r'[0-9]+\.[0-9]+\.[0-9]+', '{{version}}'),  # Version numbers
        ]

        # Apply replacements selectively based on file type
        if filename in ['LICENSE', 'README.md']:
            for pattern, replacement in replacements[:3]:  # Skip URL and version
                content = re.sub(pattern, replacement, content, count=1)

        return content

    def _extract_workflows(self) -> List[Dict[str, Any]]:
        """Extract CI/CD workflows."""
        workflows = []

        # GitHub Actions
        gh_workflows = self.repo_path / '.github' / 'workflows'
        if gh_workflows.exists():
            for workflow_file in gh_workflows.glob('*.yml'):
                try:
                    with open(workflow_file, 'r') as f:
                        workflow_data = yaml.safe_load(f)

                    workflows.append({
                        'name': workflow_data.get('name', workflow_file.stem),
                        'type': 'github_actions',
                        'triggers': list(workflow_data.get('on', {}).keys()),
                        'jobs': list(workflow_data.get('jobs', {}).keys()),
                    })
                except:
                    continue

        # GitLab CI
        gitlab_ci = self.repo_path / '.gitlab-ci.yml'
        if gitlab_ci.exists():
            try:
                with open(gitlab_ci, 'r') as f:
                    ci_data = yaml.safe_load(f)

                workflows.append({
                    'name': 'GitLab CI',
                    'type': 'gitlab_ci',
                    'stages': ci_data.get('stages', []),
                })
            except:
                pass

        # Jenkins
        jenkinsfile = self.repo_path / 'Jenkinsfile'
        if jenkinsfile.exists():
            workflows.append({
                'name': 'Jenkins',
                'type': 'jenkins',
            })

        return workflows

    def _extract_configurations(self) -> Dict[str, Any]:
        """Extract configuration patterns."""
        configs = {
            'environment_variables': [],
            'config_files': [],
            'config_patterns': [],
        }

        # Look for environment variable usage
        env_vars = set()
        for py_file in self.repo_path.glob('**/*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                    # Find os.environ usage
                    env_pattern = r'os\.environ\.get\([\'"]([A-Z_]+)[\'"]\)'
                    matches = re.findall(env_pattern, content)
                    env_vars.update(matches)

                    # Find os.getenv usage
                    getenv_pattern = r'os\.getenv\([\'"]([A-Z_]+)[\'"]\)'
                    matches = re.findall(getenv_pattern, content)
                    env_vars.update(matches)
            except:
                continue

        configs['environment_variables'] = list(env_vars)

        # Identify config files
        config_patterns = ['*.ini', '*.cfg', '*.conf', '*.json', '*.yml', '*.yaml', '*.toml', '.env*']
        for pattern in config_patterns:
            for config_file in self.repo_path.glob(pattern):
                if config_file.is_file():
                    configs['config_files'].append({
                        'path': str(config_file.relative_to(self.repo_path)),
                        'format': config_file.suffix[1:] if config_file.suffix else 'env',
                    })

        # Identify configuration patterns
        if configs['config_files']:
            if any(f['format'] in ['yml', 'yaml'] for f in configs['config_files']):
                configs['config_patterns'].append('yaml_config')
            if any(f['format'] == 'json' for f in configs['config_files']):
                configs['config_patterns'].append('json_config')
            if any(f['format'] == 'toml' for f in configs['config_files']):
                configs['config_patterns'].append('toml_config')
            if any('env' in f['path'] for f in configs['config_files']):
                configs['config_patterns'].append('dotenv')

        return configs

    def _extract_dependencies(self) -> Dict[str, List[str]]:
        """Extract project dependencies."""
        dependencies = {}

        # Python dependencies
        req_file = self.repo_path / 'requirements.txt'
        if req_file.exists():
            try:
                with open(req_file, 'r') as f:
                    deps = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Extract package name (before any version specifier)
                            pkg = re.split(r'[<>=!]', line)[0].strip()
                            deps.append(pkg)
                    dependencies['python'] = deps
            except:
                pass

        # Python setup.py dependencies
        setup_file = self.repo_path / 'setup.py'
        if setup_file.exists():
            try:
                with open(setup_file, 'r') as f:
                    content = f.read()
                    # Simple extraction (could be improved)
                    if 'install_requires' in content:
                        requires_pattern = r'install_requires\s*=\s*\[(.*?)\]'
                        match = re.search(requires_pattern, content, re.DOTALL)
                        if match:
                            deps_str = match.group(1)
                            deps = re.findall(r'[\'"]([a-zA-Z0-9\-_]+)[\'"]', deps_str)
                            dependencies['python'] = deps
            except:
                pass

        # Node.js dependencies
        package_json = self.repo_path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    deps = []
                    if 'dependencies' in data:
                        deps.extend(data['dependencies'].keys())
                    if 'devDependencies' in data:
                        deps.extend(data['devDependencies'].keys())
                    dependencies['node'] = deps
            except:
                pass

        # Go dependencies
        go_mod = self.repo_path / 'go.mod'
        if go_mod.exists():
            try:
                with open(go_mod, 'r') as f:
                    deps = []
                    for line in f:
                        if line.strip().startswith('require '):
                            parts = line.split()
                            if len(parts) >= 2:
                                deps.append(parts[1])
                    dependencies['go'] = deps
            except:
                pass

        return dependencies

    def _identify_variables(self) -> Dict[str, Dict[str, str]]:
        """Identify template variables that should be configurable."""
        variables = {
            'project': {
                'name': '{{project_name}}',
                'description': '{{project_description}}',
                'version': '{{version}}',
                'author': '{{author}}',
                'email': '{{email}}',
                'license': '{{license}}',
                'url': '{{project_url}}',
            },
            'paths': {
                'source_dir': '{{source_dir}}',
                'test_dir': '{{test_dir}}',
                'docs_dir': '{{docs_dir}}',
                'build_dir': '{{build_dir}}',
            },
            'environment': {},
            'dependencies': {},
        }

        # Add detected environment variables
        configs = self._extract_configurations()
        for env_var in configs.get('environment_variables', []):
            variables['environment'][env_var.lower()] = f'{{{{{env_var}}}}}'

        # Add dependency versions as variables
        deps = self._extract_dependencies()
        for lang, packages in deps.items():
            for pkg in packages[:10]:  # Limit to top 10
                var_name = f'{pkg.replace("-", "_")}_version'
                variables['dependencies'][var_name] = f'{{{{{var_name}}}}}'

        return variables

    def _identify_best_practices(self) -> List[str]:
        """Identify best practices used in the repository."""
        practices = []

        # Version control practices
        if (self.repo_path / '.gitignore').exists():
            practices.append('uses_gitignore')

        # Documentation practices
        if (self.repo_path / 'README.md').exists() or (self.repo_path / 'README.rst').exists():
            practices.append('has_readme')
        if (self.repo_path / 'docs').exists():
            practices.append('has_documentation')

        # Testing practices
        if (self.repo_path / 'tests').exists() or (self.repo_path / 'test').exists():
            practices.append('has_tests')
        if self._file_or_content_exists('coverage'):
            practices.append('tracks_coverage')

        # CI/CD practices
        if (self.repo_path / '.github' / 'workflows').exists():
            practices.append('uses_ci')
        if (self.repo_path / 'Dockerfile').exists():
            practices.append('containerized')

        # Code quality practices
        if any((self.repo_path / f).exists() for f in ['.flake8', '.pylintrc', '.eslintrc']):
            practices.append('uses_linter')
        if any((self.repo_path / f).exists() for f in ['.pre-commit-config.yaml', '.husky']):
            practices.append('uses_pre_commit')

        # Dependency management
        if (self.repo_path / 'requirements.txt').exists() and (self.repo_path / 'requirements.in').exists():
            practices.append('pins_dependencies')
        if (self.repo_path / 'poetry.lock').exists() or (self.repo_path / 'package-lock.json').exists():
            practices.append('uses_lockfile')

        # Security practices
        if self._file_or_content_exists('security'):
            practices.append('security_policy')
        if (self.repo_path / '.github' / 'dependabot.yml').exists():
            practices.append('automated_security_updates')

        # License
        if (self.repo_path / 'LICENSE').exists():
            practices.append('has_license')

        # Configuration management
        if any((self.repo_path / f).exists() for f in ['.env.example', '.env.sample']):
            practices.append('env_example')

        return practices

    def compare_with_template(self, other_template: Dict[str, Any]) -> Dict[str, Any]:
        """Compare extracted template with another template.

        Args:
            other_template: Template to compare with.

        Returns:
            Comparison results.
        """
        current_template = self.extract_template()

        comparison = {
            'similarity_score': 0,
            'missing_practices': [],
            'additional_practices': [],
            'structure_differences': {},
            'pattern_differences': {},
            'suggestions': [],
        }

        # Compare best practices
        current_practices = set(current_template.get('best_practices', []))
        other_practices = set(other_template.get('best_practices', []))

        comparison['missing_practices'] = list(other_practices - current_practices)
        comparison['additional_practices'] = list(current_practices - other_practices)

        # Calculate similarity score
        if current_practices or other_practices:
            common = len(current_practices & other_practices)
            total = len(current_practices | other_practices)
            comparison['similarity_score'] = common / total if total > 0 else 0

        # Generate suggestions
        if comparison['missing_practices']:
            comparison['suggestions'].append(f"Consider adopting: {', '.join(comparison['missing_practices'][:3])}")

        if comparison['similarity_score'] < 0.5:
            comparison['suggestions'].append("Repository structure differs significantly from template")

        return comparison

    def export_template(self, output_path: str):
        """Export template to a file.

        Args:
            output_path: Path to save the template.
        """
        template = self.extract_template()

        with open(output_path, 'w') as f:
            json.dump(template, f, indent=2)

        logger.info(f"Template exported to {output_path}")