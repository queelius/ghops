#!/usr/bin/env python3

import os
import json
import requests
import toml
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import re

from .config import logger, config
from .utils import run_command

def find_packaging_files(repo_path: str) -> List[str]:
    """Find Python packaging files in a repository."""
    packaging_files = []
    repo_path = Path(repo_path)
    
    # Look for common packaging files
    candidates = ['pyproject.toml', 'setup.py', 'setup.cfg']
    
    for candidate in candidates:
        file_path = repo_path / candidate
        if file_path.exists():
            packaging_files.append(str(file_path))
    
    return packaging_files

def extract_package_name_from_pyproject(file_path: str) -> Optional[str]:
    """Extract package name from pyproject.toml."""
    try:
        with open(file_path, 'r') as f:
            data = toml.load(f)
        
        # Check [project] section first (PEP 621)
        if 'project' in data and 'name' in data['project']:
            return data['project']['name']
        
        # Check [tool.setuptools] for older format
        if 'tool' in data and 'setuptools' in data['tool'] and 'name' in data['tool']['setuptools']:
            return data['tool']['setuptools']['name']
        
        # Check [build-system] for some edge cases
        if 'build-system' in data and 'name' in data['build-system']:
            return data['build-system']['name']
        
    except Exception as e:
        logger.debug(f"Error parsing {file_path}: {e}")
    
    return None

def extract_package_name_from_setup_py(file_path: str) -> Optional[str]:
    """Extract package name from setup.py (basic regex parsing)."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for name= parameter in setup() call
        patterns = [
            r'name\s*=\s*["\']([^"\']+)["\']',
            r'name\s*=\s*([a-zA-Z_][a-zA-Z0-9_-]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
    except Exception as e:
        logger.debug(f"Error parsing {file_path}: {e}")
    
    return None

def extract_package_name_from_setup_cfg(file_path: str) -> Optional[str]:
    """Extract package name from setup.cfg."""
    try:
        import configparser
        config_parser = configparser.ConfigParser()
        config_parser.read(file_path)
        
        if 'metadata' in config_parser and 'name' in config_parser['metadata']:
            return config_parser['metadata']['name']
        
    except Exception as e:
        logger.debug(f"Error parsing {file_path}: {e}")
    
    return None

def extract_package_name(file_path: str) -> Optional[str]:
    """Extract package name from a packaging file."""
    file_path = Path(file_path)
    
    if file_path.name == 'pyproject.toml':
        return extract_package_name_from_pyproject(str(file_path))
    elif file_path.name == 'setup.py':
        return extract_package_name_from_setup_py(str(file_path))
    elif file_path.name == 'setup.cfg':
        return extract_package_name_from_setup_cfg(str(file_path))
    
    return None

def check_pypi_package(package_name: str) -> Optional[Dict]:
    """Check if a package exists on PyPI and get its info."""
    try:
        timeout = config.get('pypi', {}).get('timeout_seconds', 10)
        
        # Check main PyPI
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(url, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'exists': True,
                'version': data['info']['version'],
                'url': f"https://pypi.org/project/{package_name}/",
                'description': data['info']['summary'] or '',
                'author': data['info']['author'] or '',
                'home_page': data['info']['home_page'] or '',
                'download_url': data['info']['download_url'] or '',
                'last_updated': data['urls'][0]['upload_time'] if data['urls'] else ''
            }
        elif response.status_code == 404:
            return {'exists': False}
        else:
            logger.warning(f"PyPI API returned status {response.status_code} for {package_name}")
            return None
            
    except requests.RequestException as e:
        logger.debug(f"Error checking PyPI for {package_name}: {e}")
        return None
    except Exception as e:
        logger.debug(f"Unexpected error checking PyPI for {package_name}: {e}")
        return None

def detect_pypi_package(repo_path: str) -> Dict:
    """Detect PyPI package information for a repository."""
    result = {
        'has_packaging_files': False,
        'packaging_files': [],
        'package_name': None,
        'pypi_info': None,
        'is_published': False
    }
    
    # Find packaging files
    packaging_files = find_packaging_files(repo_path)
    result['packaging_files'] = packaging_files
    result['has_packaging_files'] = bool(packaging_files)
    
    if not packaging_files:
        return result
    
    # Try to extract package name from the first packaging file found
    for file_path in packaging_files:
        package_name = extract_package_name(file_path)
        if package_name:
            result['package_name'] = package_name
            break
    
    # If no package name found, try using the repository directory name
    if not result['package_name']:
        repo_name = Path(repo_path).name
        # Clean up common patterns
        clean_name = repo_name.replace('-', '_').replace(' ', '_')
        result['package_name'] = clean_name
    
    # Check PyPI if we have a package name
    if result['package_name']:
        pypi_info = check_pypi_package(result['package_name'])
        if pypi_info:
            result['pypi_info'] = pypi_info
            result['is_published'] = pypi_info.get('exists', False)
    
    return result

def get_local_package_version(repo_path: str, package_name: str) -> Optional[str]:
    """Get the local version of a package from packaging files."""
    packaging_files = find_packaging_files(repo_path)
    
    for file_path in packaging_files:
        if Path(file_path).name == 'pyproject.toml':
            try:
                with open(file_path, 'r') as f:
                    data = toml.load(f)
                
                # Check [project] section
                if 'project' in data and 'version' in data['project']:
                    return data['project']['version']
                
                # Check [tool.setuptools] for older format
                if 'tool' in data and 'setuptools' in data['tool'] and 'version' in data['tool']['setuptools']:
                    return data['tool']['setuptools']['version']
                    
            except Exception as e:
                logger.debug(f"Error reading version from {file_path}: {e}")
        
        elif Path(file_path).name == 'setup.py':
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Look for version= parameter
                patterns = [
                    r'version\s*=\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1)
                        
            except Exception as e:
                logger.debug(f"Error reading version from {file_path}: {e}")
    
    return None

def is_package_outdated(repo_path: str, package_name: str, pypi_version: str) -> bool:
    """Check if local package version is behind PyPI version."""
    local_version = get_local_package_version(repo_path, package_name)
    
    if not local_version:
        return False
    
    try:
        # Simple version comparison (you might want to use packaging.version for more robust comparison)
        from packaging import version
        return version.parse(local_version) < version.parse(pypi_version)
    except ImportError:
        # Fallback to string comparison if packaging module not available
        return local_version != pypi_version
    except Exception:
        return False