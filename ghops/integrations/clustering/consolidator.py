"""
Repository consolidation advisor.

Provides detailed recommendations and automation for repository consolidation.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import tempfile
import shutil

logger = logging.getLogger(__name__)


class ConsolidationAdvisor:
    """Provides actionable consolidation recommendations and automation."""

    def __init__(self, analyzer_results: Dict[str, Any]):
        """Initialize with clustering analysis results.

        Args:
            analyzer_results: Results from ClusterAnalyzer.
        """
        self.clusters = analyzer_results.get('clusters', {})
        self.metadata = analyzer_results.get('metadata', {})
        self.repositories = analyzer_results.get('repositories', {})
        self.recommendations = []

    def generate_consolidation_plan(self) -> List[Dict[str, Any]]:
        """Generate detailed consolidation plan with steps.

        Returns:
            List of consolidation tasks with detailed steps.
        """
        plans = []

        for cluster_id, cluster_meta in self.metadata.items():
            consolidation = cluster_meta.get('consolidation_potential', {})

            if consolidation.get('score', 0) > 0.5:
                plan = self._create_consolidation_plan(cluster_id, cluster_meta)
                if plan:
                    plans.append(plan)

        # Sort by priority (score)
        plans.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        return plans

    def _create_consolidation_plan(self,
                                  cluster_id: str,
                                  cluster_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create detailed consolidation plan for a cluster.

        Args:
            cluster_id: Cluster identifier.
            cluster_meta: Cluster metadata.

        Returns:
            Consolidation plan dictionary.
        """
        cluster_type = cluster_meta.get('cluster_type')
        repos = cluster_meta.get('repositories', [])
        consolidation = cluster_meta.get('consolidation_potential', {})

        if not repos or not cluster_type:
            return None

        plan = {
            'cluster_id': cluster_id,
            'type': cluster_type,
            'action': consolidation.get('recommendation'),
            'repositories': repos,
            'priority_score': consolidation.get('score', 0),
            'effort': consolidation.get('effort'),
            'benefits': consolidation.get('benefits', []),
            'risks': consolidation.get('risks', []),
            'steps': [],
            'scripts': [],
            'estimated_time': None,
        }

        # Generate specific steps based on cluster type
        if cluster_type == 'duplicates':
            plan['steps'] = self._generate_merge_duplicate_steps(repos)
            plan['scripts'] = self._generate_merge_scripts(repos)
            plan['estimated_time'] = '2-4 hours'

        elif cluster_type == 'monorepo_candidate':
            plan['steps'] = self._generate_monorepo_steps(repos)
            plan['scripts'] = self._generate_monorepo_scripts(repos)
            plan['estimated_time'] = '4-8 hours'

        elif cluster_type == 'project_family':
            plan['steps'] = self._generate_family_organization_steps(repos)
            plan['scripts'] = self._generate_family_scripts(repos)
            plan['estimated_time'] = '1-2 hours'

        elif cluster_type == 'split_candidate':
            plan['steps'] = self._generate_split_steps(repos[0] if repos else None)
            plan['scripts'] = self._generate_split_scripts(repos[0] if repos else None)
            plan['estimated_time'] = '6-12 hours'

        return plan

    def _generate_merge_duplicate_steps(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate steps for merging duplicate repositories."""
        steps = [
            {
                'order': 1,
                'action': 'analyze',
                'description': 'Compare repository histories and identify the primary repository',
                'command': f'git log --oneline --graph --all',
            },
            {
                'order': 2,
                'action': 'backup',
                'description': 'Create backups of all repositories',
                'command': 'tar -czf backup_$(date +%Y%m%d).tar.gz ' + ' '.join(repos),
            },
            {
                'order': 3,
                'action': 'identify_primary',
                'description': 'Select repository with most complete history as primary',
                'command': 'git rev-list --count --all',
            },
            {
                'order': 4,
                'action': 'merge_histories',
                'description': 'Merge git histories from secondary repos into primary',
                'command': 'git remote add secondary <repo> && git fetch secondary',
            },
            {
                'order': 5,
                'action': 'reconcile_branches',
                'description': 'Merge or rebase branches from secondary repositories',
                'command': 'git checkout -b merge-<repo> secondary/main && git rebase main',
            },
            {
                'order': 6,
                'action': 'migrate_issues',
                'description': 'Export and import issues/PRs to primary repository',
                'command': 'gh issue list --json title,body,labels | gh issue create --repo <primary>',
            },
            {
                'order': 7,
                'action': 'update_references',
                'description': 'Update all references and dependencies pointing to old repos',
                'command': 'grep -r "old-repo-name" . | xargs sed -i "s/old-repo/new-repo/g"',
            },
            {
                'order': 8,
                'action': 'archive_secondary',
                'description': 'Archive secondary repositories with redirect notice',
                'command': 'echo "Moved to <primary-repo>" > README.md && git commit -m "Archive"',
            },
        ]
        return steps

    def _generate_monorepo_steps(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate steps for creating a monorepo."""
        steps = [
            {
                'order': 1,
                'action': 'create_structure',
                'description': 'Create monorepo directory structure',
                'command': 'mkdir -p monorepo/{packages,libs,apps,tools}',
            },
            {
                'order': 2,
                'action': 'init_monorepo',
                'description': 'Initialize monorepo with package manager',
                'command': 'cd monorepo && npm init -y && npm install --save-dev lerna',
            },
            {
                'order': 3,
                'action': 'preserve_history',
                'description': 'Import each repository preserving git history',
                'command': 'git subtree add --prefix=packages/<name> <repo-url> main',
            },
            {
                'order': 4,
                'action': 'setup_workspaces',
                'description': 'Configure workspace management (npm/yarn/pnpm workspaces)',
                'command': 'echo \'{"workspaces": ["packages/*"]}\' > package.json',
            },
            {
                'order': 5,
                'action': 'update_imports',
                'description': 'Update import paths and dependencies between packages',
                'command': 'find . -name "*.js" -o -name "*.ts" | xargs sed -i "s/@old/@monorepo/g"',
            },
            {
                'order': 6,
                'action': 'setup_tooling',
                'description': 'Setup shared tooling (ESLint, Prettier, TypeScript)',
                'command': 'npx lerna init && npx lerna bootstrap',
            },
            {
                'order': 7,
                'action': 'create_scripts',
                'description': 'Create monorepo management scripts',
                'command': 'npm run build:all && npm run test:all',
            },
            {
                'order': 8,
                'action': 'setup_ci',
                'description': 'Update CI/CD for monorepo structure',
                'command': 'cp .github/workflows/monorepo.yml .github/workflows/ci.yml',
            },
        ]
        return steps

    def _generate_family_organization_steps(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate steps for organizing a project family."""
        steps = [
            {
                'order': 1,
                'action': 'create_organization',
                'description': 'Create GitHub/GitLab organization for the family',
                'command': 'gh api -X POST /orgs -f name=<family-name>',
            },
            {
                'order': 2,
                'action': 'standardize_naming',
                'description': 'Rename repositories following consistent convention',
                'command': 'gh repo rename <old-name> <new-name>',
            },
            {
                'order': 3,
                'action': 'create_template',
                'description': 'Create shared template repository',
                'command': 'gh repo create <family>-template --template',
            },
            {
                'order': 4,
                'action': 'share_workflows',
                'description': 'Create reusable GitHub Actions workflows',
                'command': 'mkdir -p .github/workflows && cp shared-workflows/* .',
            },
            {
                'order': 5,
                'action': 'standardize_config',
                'description': 'Apply consistent configuration across repositories',
                'command': 'for repo in <repos>; do cp .editorconfig $repo/; done',
            },
            {
                'order': 6,
                'action': 'create_docs_site',
                'description': 'Create unified documentation site',
                'command': 'mkdocs new family-docs && mkdocs build',
            },
            {
                'order': 7,
                'action': 'setup_badges',
                'description': 'Add family badges and cross-references',
                'command': 'echo "[![Family](badge.svg)](family-url)" >> README.md',
            },
        ]
        return steps

    def _generate_split_steps(self, repo: Optional[str]) -> List[Dict[str, str]]:
        """Generate steps for splitting a repository."""
        if not repo:
            return []

        steps = [
            {
                'order': 1,
                'action': 'analyze_structure',
                'description': 'Analyze repository structure to identify components',
                'command': 'tree -d -L 2 | head -20',
            },
            {
                'order': 2,
                'action': 'identify_boundaries',
                'description': 'Identify module boundaries and dependencies',
                'command': 'madge --json src/ > dependencies.json',
            },
            {
                'order': 3,
                'action': 'create_repos',
                'description': 'Create new repositories for each component',
                'command': 'gh repo create <component-name> --private',
            },
            {
                'order': 4,
                'action': 'filter_history',
                'description': 'Extract component with history using git filter-branch',
                'command': 'git filter-branch --subdirectory-filter <component-path> -- --all',
            },
            {
                'order': 5,
                'action': 'setup_dependencies',
                'description': 'Setup inter-component dependencies',
                'command': 'npm install <other-component>@latest',
            },
            {
                'order': 6,
                'action': 'update_ci',
                'description': 'Setup CI/CD for each new repository',
                'command': 'cp .github/workflows/template.yml .github/workflows/ci.yml',
            },
            {
                'order': 7,
                'action': 'update_imports',
                'description': 'Update import statements in dependent projects',
                'command': 'find . -name "*.js" | xargs sed -i "s/old-import/new-import/g"',
            },
            {
                'order': 8,
                'action': 'deprecate_original',
                'description': 'Add deprecation notice to original repository',
                'command': 'echo "# Deprecated - Split into components" > README.md',
            },
        ]
        return steps

    def _generate_merge_scripts(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate automation scripts for merging repositories."""
        scripts = []

        # Main merge script
        merge_script = f'''#!/bin/bash
# Merge duplicate repositories into one

set -e

PRIMARY_REPO="{repos[0] if repos else ''}"
SECONDARY_REPOS=({' '.join(f'"{r}"' for r in repos[1:])})

echo "Starting repository merge process..."

# Backup all repositories
echo "Creating backups..."
for repo in "${{SECONDARY_REPOS[@]}}"; do
    tar -czf "backup_$(basename $repo)_$(date +%Y%m%d).tar.gz" "$repo"
done

# Clone primary repository
git clone "$PRIMARY_REPO" merged_repo
cd merged_repo

# Add secondary repositories as remotes and merge
for i in "${{!SECONDARY_REPOS[@]}}"; do
    repo="${{SECONDARY_REPOS[$i]}}"
    remote_name="secondary_$i"

    echo "Adding remote: $remote_name"
    git remote add "$remote_name" "$repo"
    git fetch "$remote_name"

    # Create branch for merging
    git checkout -b "merge-$remote_name" "$remote_name/main"

    # Merge into main
    git checkout main
    git merge --allow-unrelated-histories "merge-$remote_name" -m "Merge $repo"
done

echo "Merge complete!"
echo "Review the merged repository in: $(pwd)"
'''

        scripts.append({
            'name': 'merge_repos.sh',
            'content': merge_script,
            'description': 'Automated script to merge duplicate repositories',
        })

        # Issue migration script
        issue_script = '''#!/bin/bash
# Migrate issues from secondary repos to primary

PRIMARY_REPO="$1"
SECONDARY_REPO="$2"

echo "Migrating issues from $SECONDARY_REPO to $PRIMARY_REPO"

# Export issues from secondary
gh issue list --repo "$SECONDARY_REPO" --json number,title,body,labels,state --limit 1000 > issues.json

# Import to primary
jq -c '.[]' issues.json | while read -r issue; do
    title=$(echo "$issue" | jq -r '.title')
    body=$(echo "$issue" | jq -r '.body')
    labels=$(echo "$issue" | jq -r '.labels[].name' | tr '\\n' ',' | sed 's/,$//')

    # Create issue in primary repo
    gh issue create --repo "$PRIMARY_REPO" --title "$title" --body "$body" --label "$labels"
done

echo "Issue migration complete"
'''

        scripts.append({
            'name': 'migrate_issues.sh',
            'content': issue_script,
            'description': 'Script to migrate issues between repositories',
        })

        return scripts

    def _generate_monorepo_scripts(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate automation scripts for monorepo creation."""
        scripts = []

        # Monorepo setup script
        setup_script = f'''#!/bin/bash
# Create monorepo from multiple repositories

set -e

MONOREPO_NAME="monorepo"
REPOS=({' '.join(f'"{r}"' for r in repos)})

echo "Creating monorepo structure..."

# Create monorepo directory
mkdir -p "$MONOREPO_NAME"
cd "$MONOREPO_NAME"

# Initialize git
git init

# Create directory structure
mkdir -p packages libs apps tools docs

# Create root package.json for workspace
cat > package.json << 'EOF'
{{
  "name": "@monorepo/root",
  "private": true,
  "workspaces": [
    "packages/*",
    "libs/*",
    "apps/*"
  ],
  "scripts": {{
    "build": "lerna run build",
    "test": "lerna run test",
    "lint": "lerna run lint",
    "clean": "lerna clean -y && rm -rf node_modules"
  }},
  "devDependencies": {{
    "lerna": "^6.0.0"
  }}
}}
EOF

# Initialize lerna
cat > lerna.json << 'EOF'
{{
  "version": "independent",
  "npmClient": "npm",
  "command": {{
    "publish": {{
      "ignoreChanges": ["*.md"],
      "message": "chore(release): publish"
    }}
  }}
}}
EOF

# Import each repository preserving history
for repo in "${{REPOS[@]}}"; do
    name=$(basename "$repo" .git)
    echo "Importing $name..."

    # Add as git subtree to preserve history
    git subtree add --prefix="packages/$name" "$repo" main --squash
done

# Setup shared configurations
echo "Setting up shared configurations..."

# ESLint config
cat > .eslintrc.json << 'EOF'
{{
  "root": true,
  "extends": ["eslint:recommended"],
  "parserOptions": {{
    "ecmaVersion": 2020
  }}
}}
EOF

# Prettier config
cat > .prettierrc << 'EOF'
{{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2
}}
EOF

# Install dependencies
npm install

echo "Monorepo created successfully!"
echo "Next steps:"
echo "  1. Review the structure in $MONOREPO_NAME"
echo "  2. Update import paths between packages"
echo "  3. Setup CI/CD for monorepo"
'''

        scripts.append({
            'name': 'create_monorepo.sh',
            'content': setup_script,
            'description': 'Automated monorepo creation from multiple repositories',
        })

        # Dependency update script
        dep_script = '''#!/bin/bash
# Update cross-dependencies in monorepo

echo "Updating cross-package dependencies..."

# Find all package.json files
find packages libs apps -name package.json -type f | while read -r pkg; do
    dir=$(dirname "$pkg")
    echo "Processing $dir..."

    # Update internal dependencies to use workspace protocol
    sed -i 's/"@old\\/\\([^"]*\\)": "[^"]*"/"@monorepo\\/\\1": "workspace:*"/g' "$pkg"
done

# Update import statements in source files
find packages libs apps \\( -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" \\) | while read -r file; do
    # Update imports to use new namespace
    sed -i "s/from '@old\\//from '@monorepo\\//g" "$file"
    sed -i "s/require('@old\\//require('@monorepo\\//g" "$file"
done

echo "Dependencies updated!"
'''

        scripts.append({
            'name': 'update_monorepo_deps.sh',
            'content': dep_script,
            'description': 'Update cross-dependencies in monorepo',
        })

        return scripts

    def _generate_family_scripts(self, repos: List[str]) -> List[Dict[str, str]]:
        """Generate scripts for family organization."""
        scripts = []

        # Family setup script
        setup_script = f'''#!/bin/bash
# Organize repositories into a project family

set -e

FAMILY_NAME="${{1:-project-family}}"
REPOS=({' '.join(f'"{r}"' for r in repos)})

echo "Organizing project family: $FAMILY_NAME"

# Create shared resources directory
mkdir -p "$FAMILY_NAME-shared"
cd "$FAMILY_NAME-shared"

# Create shared workflows
mkdir -p .github/workflows
cat > .github/workflows/shared-ci.yml << 'EOF'
name: Shared CI

on:
  workflow_call:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
      - run: npm ci
      - run: npm test
      - run: npm run lint
EOF

# Create shared configuration files
cat > .editorconfig << 'EOF'
root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true
EOF

# Create family README template
cat > README-template.md << 'EOF'
# {{REPO_NAME}}

Part of the $FAMILY_NAME family of projects.

## Related Projects
EOF

for repo in "${{REPOS[@]}}"; do
    name=$(basename "$repo")
    echo "- [$name]($repo)" >> README-template.md
done

# Apply configurations to each repository
for repo in "${{REPOS[@]}}"; do
    echo "Configuring $repo..."

    # Copy shared files
    cp .editorconfig "$repo/"
    cp .github/workflows/shared-ci.yml "$repo/.github/workflows/" 2>/dev/null || true

    # Update README with family badge
    if [[ -f "$repo/README.md" ]]; then
        echo "" >> "$repo/README.md"
        echo "---" >> "$repo/README.md"
        echo "Part of the [$FAMILY_NAME]($FAMILY_NAME-shared) project family." >> "$repo/README.md"
    fi
done

echo "Family organization complete!"
'''

        scripts.append({
            'name': 'organize_family.sh',
            'content': setup_script,
            'description': 'Organize repositories into a project family',
        })

        return scripts

    def _generate_split_scripts(self, repo: Optional[str]) -> List[Dict[str, str]]:
        """Generate scripts for splitting a repository."""
        if not repo:
            return []

        scripts = []

        # Repository split script
        split_script = f'''#!/bin/bash
# Split monolithic repository into components

set -e

SOURCE_REPO="{repo}"
COMPONENTS=()  # Will be populated after analysis

echo "Analyzing repository structure..."

# Analyze directory structure
cd "$SOURCE_REPO"

# Find top-level directories that could be components
for dir in */; do
    if [[ -f "$dir/package.json" ]] || [[ -f "$dir/setup.py" ]] || [[ -f "$dir/go.mod" ]]; then
        COMPONENTS+=("${{dir%/}}")
    fi
done

echo "Found components: ${{COMPONENTS[@]}}"

# Create new repository for each component
for component in "${{COMPONENTS[@]}}"; do
    echo "Extracting $component..."

    # Create new repo directory
    new_repo="../${{component}}-extracted"

    # Use git filter-branch to extract with history
    git filter-branch --prune-empty --subdirectory-filter "$component" \\
        --tag-name-filter cat -- --all

    # Clone to new location
    git clone . "$new_repo"

    # Reset for next component
    git reset --hard
    git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d
done

echo "Repository split complete!"
echo "New repositories created for each component"
'''

        scripts.append({
            'name': 'split_repository.sh',
            'content': split_script,
            'description': 'Split monolithic repository into components',
        })

        return scripts

    def generate_migration_checklist(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate detailed migration checklist for a consolidation plan.

        Args:
            plan: Consolidation plan.

        Returns:
            List of checklist items with validation steps.
        """
        checklist = []
        action = plan.get('action')

        # Pre-migration checks
        checklist.extend([
            {
                'phase': 'pre-migration',
                'task': 'Backup all affected repositories',
                'validation': 'Verify backup files exist and are complete',
                'critical': True,
            },
            {
                'phase': 'pre-migration',
                'task': 'Document current state (URLs, dependencies)',
                'validation': 'Create inventory of all external references',
                'critical': True,
            },
            {
                'phase': 'pre-migration',
                'task': 'Notify stakeholders',
                'validation': 'Confirm all users are aware of changes',
                'critical': False,
            },
        ])

        # Action-specific checks
        if action == 'merge_duplicates':
            checklist.extend([
                {
                    'phase': 'migration',
                    'task': 'Merge git histories',
                    'validation': 'Verify all commits are preserved',
                    'critical': True,
                },
                {
                    'phase': 'migration',
                    'task': 'Migrate issues and PRs',
                    'validation': 'Count issues before and after',
                    'critical': True,
                },
                {
                    'phase': 'migration',
                    'task': 'Update CI/CD configurations',
                    'validation': 'Run test pipeline successfully',
                    'critical': True,
                },
            ])

        elif action == 'create_monorepo':
            checklist.extend([
                {
                    'phase': 'migration',
                    'task': 'Create monorepo structure',
                    'validation': 'Verify directory structure is correct',
                    'critical': True,
                },
                {
                    'phase': 'migration',
                    'task': 'Import repositories with history',
                    'validation': 'Check git log for all components',
                    'critical': True,
                },
                {
                    'phase': 'migration',
                    'task': 'Setup workspace configuration',
                    'validation': 'Run install and verify linking',
                    'critical': True,
                },
                {
                    'phase': 'migration',
                    'task': 'Update import paths',
                    'validation': 'Run build and tests',
                    'critical': True,
                },
            ])

        # Post-migration checks
        checklist.extend([
            {
                'phase': 'post-migration',
                'task': 'Update documentation',
                'validation': 'Review README and docs for accuracy',
                'critical': False,
            },
            {
                'phase': 'post-migration',
                'task': 'Update external references',
                'validation': 'Test all incoming links and dependencies',
                'critical': True,
            },
            {
                'phase': 'post-migration',
                'task': 'Archive old repositories',
                'validation': 'Add redirect notices',
                'critical': False,
            },
            {
                'phase': 'post-migration',
                'task': 'Monitor for issues',
                'validation': 'Check error logs and user reports',
                'critical': False,
            },
        ])

        return checklist

    def export_consolidation_jsonl(self):
        """Generate JSONL output for consolidation recommendations.

        Yields:
            JSON strings, one per line, for each recommendation.
        """
        plans = self.generate_consolidation_plan()

        for plan in plans:
            # Add checklist
            plan['checklist'] = self.generate_migration_checklist(plan)

            # Format for JSONL output
            output = {
                'type': 'consolidation_plan',
                'cluster_id': plan['cluster_id'],
                'action': plan['action'],
                'priority_score': plan['priority_score'],
                'effort': plan['effort'],
                'estimated_time': plan['estimated_time'],
                'affected_repositories': plan['repositories'],
                'benefits': plan['benefits'],
                'risks': plan['risks'],
                'step_count': len(plan['steps']),
                'script_count': len(plan['scripts']),
                'checklist_items': len(plan['checklist']),
            }

            yield json.dumps(output)

    def generate_rollback_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rollback plan for a consolidation.

        Args:
            plan: Original consolidation plan.

        Returns:
            Rollback plan with steps and scripts.
        """
        rollback = {
            'original_action': plan['action'],
            'repositories': plan['repositories'],
            'steps': [],
            'scripts': [],
        }

        if plan['action'] == 'merge_duplicates':
            rollback['steps'] = [
                {
                    'order': 1,
                    'description': 'Restore from backups',
                    'command': 'tar -xzf backup_*.tar.gz',
                },
                {
                    'order': 2,
                    'description': 'Re-create original repositories',
                    'command': 'gh repo create <original-name>',
                },
                {
                    'order': 3,
                    'description': 'Push backed-up content',
                    'command': 'git push origin main --force',
                },
                {
                    'order': 4,
                    'description': 'Restore issues if needed',
                    'command': 'gh issue create --title "Restored" --body "..."',
                },
            ]

        elif plan['action'] == 'create_monorepo':
            rollback['steps'] = [
                {
                    'order': 1,
                    'description': 'Extract components back to separate repos',
                    'command': 'git subtree split --prefix=packages/<name> -b <name>',
                },
                {
                    'order': 2,
                    'description': 'Create individual repositories',
                    'command': 'gh repo create <name> && git push origin <name>:main',
                },
                {
                    'order': 3,
                    'description': 'Restore original dependencies',
                    'command': 'npm install <original-deps>',
                },
            ]

        return rollback