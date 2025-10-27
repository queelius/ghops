"""
Auto-publish command with registry detection.

Detects project type and publishes to appropriate registries:
- Python → PyPI (or configured alternatives)
- C++ → Conan, vcpkg
- Node.js → npm
- Rust → crates.io
- Ruby → RubyGems
- Go → pkg.go.dev (via git tags)
"""

import click
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table

from ..config import load_config
from ..utils import run_command
from ..git_ops.utils import get_repos_from_vfs_path
from ..version_manager import bump_version as do_bump_version, set_version as do_set_version, get_version

console = Console()


class ProjectDetector:
    """Detect project type and available registries."""

    DETECTORS = {
        'python': [
            'pyproject.toml',
            'setup.py',
            'setup.cfg',
        ],
        'cpp': [
            'conanfile.py',
            'conanfile.txt',
            'vcpkg.json',
            'CMakeLists.txt',
        ],
        'node': [
            'package.json',
        ],
        'rust': [
            'Cargo.toml',
        ],
        'ruby': [
            'Gemfile',
            '*.gemspec',
        ],
        'go': [
            'go.mod',
        ],
    }

    @classmethod
    def detect(cls, repo_path: str) -> List[str]:
        """Detect all applicable project types for a repository.

        Args:
            repo_path: Path to repository

        Returns:
            List of detected project types (can be multiple)
        """
        repo = Path(repo_path)
        detected = []

        for project_type, indicators in cls.DETECTORS.items():
            for indicator in indicators:
                if '*' in indicator:
                    # Glob pattern
                    if list(repo.glob(indicator)):
                        detected.append(project_type)
                        break
                else:
                    # Exact file
                    if (repo / indicator).exists():
                        detected.append(project_type)
                        break

        return detected


class RegistryPublisher:
    """Handle publishing to various registries."""

    def __init__(self, repo_path: str, dry_run: bool = False):
        self.repo_path = repo_path
        self.dry_run = dry_run
        self.repo_name = Path(repo_path).name

    def publish_python_pypi(self) -> Tuple[bool, str]:
        """Publish Python package to PyPI using twine.

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing Python package to PyPI...[/cyan]")

        # Check if package is built
        dist_dir = Path(self.repo_path) / "dist"
        if not dist_dir.exists() or not list(dist_dir.glob("*.whl")) and not list(dist_dir.glob("*.tar.gz")):
            console.print("[yellow]No built distribution found. Building package...[/yellow]")

            # Build package
            build_cmd = "python -m build"
            if self.dry_run:
                console.print(f"[dim]Would run: {build_cmd}[/dim]")
            else:
                output, returncode = run_command(build_cmd, cwd=self.repo_path, capture_output=True, check=False)
                if returncode != 0:
                    return False, f"Build failed: {output}"
                console.print("[green]✓[/green] Package built")

        # Upload to PyPI
        upload_cmd = "python -m twine upload dist/*"
        if self.dry_run:
            console.print(f"[dim]Would run: {upload_cmd}[/dim]")
            return True, "Dry run: would upload to PyPI"
        else:
            output, returncode = run_command(upload_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"Upload failed: {output}"
            return True, "Published to PyPI"

    def publish_cpp_conan(self) -> Tuple[bool, str]:
        """Publish C++ package to Conan.

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing C++ package to Conan...[/cyan]")

        # Check for conanfile
        conanfile = Path(self.repo_path) / "conanfile.py"
        if not conanfile.exists():
            conanfile = Path(self.repo_path) / "conanfile.txt"
            if not conanfile.exists():
                return False, "No conanfile.py or conanfile.txt found"

        # Create and upload package
        export_cmd = "conan export . "
        upload_cmd = "conan upload * -r conancenter --all"

        if self.dry_run:
            console.print(f"[dim]Would run: {export_cmd}[/dim]")
            console.print(f"[dim]Would run: {upload_cmd}[/dim]")
            return True, "Dry run: would publish to Conan"
        else:
            # Export package
            output, returncode = run_command(export_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"Conan export failed: {output}"

            # Upload package
            output, returncode = run_command(upload_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"Conan upload failed: {output}"

            return True, "Published to Conan"

    def publish_node_npm(self) -> Tuple[bool, str]:
        """Publish Node.js package to npm.

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing Node.js package to npm...[/cyan]")

        # Check for package.json
        package_json = Path(self.repo_path) / "package.json"
        if not package_json.exists():
            return False, "No package.json found"

        # Publish to npm
        publish_cmd = "npm publish"
        if self.dry_run:
            console.print(f"[dim]Would run: {publish_cmd}[/dim]")
            return True, "Dry run: would publish to npm"
        else:
            output, returncode = run_command(publish_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"npm publish failed: {output}"
            return True, "Published to npm"

    def publish_rust_crates(self) -> Tuple[bool, str]:
        """Publish Rust crate to crates.io.

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing Rust crate to crates.io...[/cyan]")

        # Check for Cargo.toml
        cargo_toml = Path(self.repo_path) / "Cargo.toml"
        if not cargo_toml.exists():
            return False, "No Cargo.toml found"

        # Publish to crates.io
        publish_cmd = "cargo publish"
        if self.dry_run:
            console.print(f"[dim]Would run: {publish_cmd}[/dim]")
            return True, "Dry run: would publish to crates.io"
        else:
            output, returncode = run_command(publish_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"cargo publish failed: {output}"
            return True, "Published to crates.io"

    def publish_ruby_gems(self) -> Tuple[bool, str]:
        """Publish Ruby gem to RubyGems.

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing Ruby gem to RubyGems...[/cyan]")

        # Find gemspec file
        gemspecs = list(Path(self.repo_path).glob("*.gemspec"))
        if not gemspecs:
            return False, "No .gemspec file found"

        # Build and publish gem
        build_cmd = f"gem build {gemspecs[0].name}"
        publish_cmd = f"gem push *.gem"

        if self.dry_run:
            console.print(f"[dim]Would run: {build_cmd}[/dim]")
            console.print(f"[dim]Would run: {publish_cmd}[/dim]")
            return True, "Dry run: would publish to RubyGems"
        else:
            # Build gem
            output, returncode = run_command(build_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"gem build failed: {output}"

            # Publish gem
            output, returncode = run_command(publish_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"gem push failed: {output}"

            return True, "Published to RubyGems"

    def publish_go_pkg(self) -> Tuple[bool, str]:
        """Publish Go module via git tags (Go uses git directly).

        Returns:
            (success, message)
        """
        console.print(f"[cyan]Publishing Go module...[/cyan]")

        # Check for go.mod
        go_mod = Path(self.repo_path) / "go.mod"
        if not go_mod.exists():
            return False, "No go.mod found"

        # Go packages are published via git tags
        # Check if there's a version tag
        output, returncode = run_command(
            "git describe --tags --abbrev=0",
            cwd=self.repo_path,
            capture_output=True,
            check=False
        )

        if returncode != 0 or not output:
            return False, "No git tag found. Create a version tag (e.g., v1.0.0) to publish."

        # Push tags to make module available
        push_cmd = "git push --tags"
        if self.dry_run:
            console.print(f"[dim]Would run: {push_cmd}[/dim]")
            return True, f"Dry run: would push tags (current: {output})"
        else:
            output, returncode = run_command(push_cmd, cwd=self.repo_path, capture_output=True, check=False)
            if returncode != 0:
                return False, f"git push --tags failed: {output}"
            return True, f"Published Go module (available via git tags)"


REGISTRY_HANDLERS = {
    'python': {
        'pypi': RegistryPublisher.publish_python_pypi,
    },
    'cpp': {
        'conan': RegistryPublisher.publish_cpp_conan,
        # 'vcpkg': would need separate implementation
    },
    'node': {
        'npm': RegistryPublisher.publish_node_npm,
    },
    'rust': {
        'crates.io': RegistryPublisher.publish_rust_crates,
    },
    'ruby': {
        'rubygems': RegistryPublisher.publish_ruby_gems,
    },
    'go': {
        'pkg.go.dev': RegistryPublisher.publish_go_pkg,
    },
}


@click.command('publish')
@click.argument('vfs_path', default='.', required=False)
@click.option('--registry', '-r', help='Specific registry to publish to (pypi, npm, conan, etc.)')
@click.option('--all-registries', is_flag=True, help='Publish to all configured registries for this project type')
@click.option('--dry-run', is_flag=True, help='Show what would be published without actually publishing')
@click.option('--bump-version', type=click.Choice(['major', 'minor', 'patch']), help='Bump version before publishing')
@click.option('--set-version', help='Set specific version before publishing')
@click.option('--version-only', is_flag=True, help='Only bump/set version, don\'t publish')
@click.option('--json', 'json_output', is_flag=True, help='Output results as JSONL')
def publish_handler(vfs_path, registry, all_registries, dry_run, bump_version, set_version, version_only, json_output):
    """Auto-detect and publish packages to appropriate registries.

    Detects project type (Python, C++, Node.js, Rust, etc.) and publishes
    to the appropriate registry (PyPI, Conan, npm, crates.io, etc.).

    Examples:
        ghops publish                        # Auto-detect and publish current repo
        ghops publish /repos/myproject       # Publish specific repo
        ghops publish --registry pypi        # Force specific registry
        ghops publish --all-registries       # Publish to all configured registries
        ghops publish --dry-run              # Preview without publishing
        ghops publish /by-language/Python    # Publish all Python repos

    Configuration (in ~/.ghops/config.json):
        {
            "publish": {
                "python": ["pypi"],              # Default registries for Python
                "cpp": ["conan"],                # Default registries for C++
                "node": ["npm"],                 # Default registries for Node.js
                "rust": ["crates.io"],           # etc.
                "ruby": ["rubygems"],
                "go": ["pkg.go.dev"]
            }
        }
    """
    config = load_config()

    # Get repository paths
    if vfs_path.startswith('/'):
        # VFS path - resolve to repo paths
        repo_paths = get_repos_from_vfs_path(vfs_path)
        if not repo_paths:
            console.print(f"[red]No repositories found at VFS path: {vfs_path}[/red]")
            return
    else:
        # Relative path or '.' - use current directory
        from pathlib import Path as RealPath
        import os
        cwd = RealPath(os.getcwd())
        if (cwd / '.git').exists():
            repo_paths = [str(cwd)]
        else:
            console.print(f"[red]Not in a git repository[/red]")
            return

    results = []

    for repo_path in repo_paths:
        repo_name = Path(repo_path).name
        console.print(f"\n[bold cyan]Processing: {repo_name}[/bold cyan]")

        # Detect project types
        project_types = ProjectDetector.detect(repo_path)

        if not project_types:
            result = {
                'repo': repo_name,
                'path': repo_path,
                'detected_types': [],
                'published': False,
                'message': 'No recognized project type detected'
            }
            results.append(result)
            console.print(f"[yellow]⚠[/yellow] No recognized project type detected")
            continue

        console.print(f"[green]✓[/green] Detected types: {', '.join(project_types)}")

        # Handle version bumping/setting
        version_changed = False
        old_version = None
        new_version_value = None

        if bump_version or set_version:
            ptype = project_types[0]  # Use first detected type for versioning
            old_version = get_version(repo_path, ptype)

            if old_version:
                console.print(f"Current version: {old_version}")

            if set_version:
                # Set specific version
                new_version_value = set_version
                if dry_run:
                    console.print(f"[dim]Would set version to: {new_version_value}[/dim]")
                    version_changed = True
                else:
                    from ..version_manager import set_version as vs
                    if vs(repo_path, ptype, new_version_value):
                        console.print(f"[green]✓[/green] Version set to: {new_version_value}")
                        version_changed = True
                    else:
                        console.print(f"[yellow]⚠[/yellow] Failed to set version")
            elif bump_version:
                # Bump version
                if dry_run:
                    from ..version_manager import VersionBumper
                    bumper = VersionBumper()
                    if bump_version == 'major':
                        new_version_value = bumper.bump_major(old_version or '0.0.0')
                    elif bump_version == 'minor':
                        new_version_value = bumper.bump_minor(old_version or '0.0.0')
                    else:  # patch
                        new_version_value = bumper.bump_patch(old_version or '0.0.0')
                    console.print(f"[dim]Would bump {bump_version}: {old_version} → {new_version_value}[/dim]")
                    version_changed = True
                else:
                    old_v, new_v = do_bump_version(repo_path, ptype, bump_version)
                    if new_v:
                        console.print(f"[green]✓[/green] Bumped {bump_version}: {old_v} → {new_v}")
                        version_changed = True
                        new_version_value = new_v
                    else:
                        console.print(f"[yellow]⚠[/yellow] Failed to bump version")

        # If version-only mode, skip publishing
        if version_only:
            result = {
                'repo': repo_name,
                'path': repo_path,
                'detected_types': project_types,
                'version_changed': version_changed,
                'old_version': old_version,
                'new_version': new_version_value,
                'published': False,
                'message': 'Version-only mode (no publishing)'
            }
            results.append(result)
            continue

        # Get configured registries for each type
        publish_config = config.get('publish', {})
        registries_to_publish = []

        if registry:
            # User specified specific registry
            registries_to_publish = [(project_types[0], registry)]
        elif all_registries:
            # Publish to all registries for all detected types
            for ptype in project_types:
                configured = publish_config.get(ptype, list(REGISTRY_HANDLERS.get(ptype, {}).keys()))
                for reg in configured:
                    registries_to_publish.append((ptype, reg))
        else:
            # Publish to default registry for first detected type
            ptype = project_types[0]
            configured = publish_config.get(ptype, list(REGISTRY_HANDLERS.get(ptype, {}).keys()))
            if configured:
                registries_to_publish = [(ptype, configured[0])]

        if not registries_to_publish:
            result = {
                'repo': repo_name,
                'path': repo_path,
                'detected_types': project_types,
                'published': False,
                'message': 'No registries configured'
            }
            results.append(result)
            console.print(f"[yellow]⚠[/yellow] No registries configured for {project_types}")
            continue

        # Publish to each registry
        publisher = RegistryPublisher(repo_path, dry_run=dry_run)
        publish_results = []

        for ptype, reg_name in registries_to_publish:
            if ptype not in REGISTRY_HANDLERS or reg_name not in REGISTRY_HANDLERS[ptype]:
                console.print(f"[yellow]⚠[/yellow] Registry '{reg_name}' not supported for {ptype}")
                publish_results.append({
                    'registry': reg_name,
                    'success': False,
                    'message': f'Registry not supported'
                })
                continue

            handler = REGISTRY_HANDLERS[ptype][reg_name]
            success, message = handler(publisher)

            publish_results.append({
                'registry': reg_name,
                'success': success,
                'message': message
            })

            if success:
                console.print(f"[green]✓[/green] {message}")
            else:
                console.print(f"[red]✗[/red] {message}")

        result = {
            'repo': repo_name,
            'path': repo_path,
            'detected_types': project_types,
            'published': any(r['success'] for r in publish_results),
            'results': publish_results
        }
        results.append(result)

    # Output results
    if json_output:
        for result in results:
            print(json.dumps(result))
    else:
        # Summary table
        console.print("\n[bold cyan]Publish Summary[/bold cyan]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Repository", style="green")
        table.add_column("Types", style="blue")
        table.add_column("Status", style="white")

        for result in results:
            types_str = ', '.join(result['detected_types']) if result['detected_types'] else 'None'
            if result.get('version_changed') and not result['published']:
                # Version-only mode
                status = "[blue]✓ Version updated[/blue]"
            elif result['published']:
                status = "[green]✓ Published[/green]"
            elif not result['detected_types']:
                status = "[yellow]⚠ Not detected[/yellow]"
            else:
                status = "[red]✗ Failed[/red]"

            table.add_row(result['repo'], types_str, status)

        console.print(table)

        # Show what would happen in dry-run
        if dry_run:
            console.print("\n[yellow]Dry run mode - no actual publishing occurred[/yellow]")
