"""
Version management functionality for the Rhesis release tool.
"""

import json
import re
from pathlib import Path
from typing import Optional

from .config import COMPONENTS, PLATFORM_VERSION_FILE
from .utils import success, error


def get_current_version(component: str, repo_root: Path) -> str:
    """Get current version of a component"""
    if component == "platform":
        version_file = repo_root / PLATFORM_VERSION_FILE
        if version_file.exists():
            return version_file.read_text().strip() or "0.0.0"
        return "0.0.0"
    
    if component not in COMPONENTS:
        raise ValueError(f"Unknown component: {component}")
    
    config = COMPONENTS[component]
    config_path = repo_root / config.config_file
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    if config.config_type == "pyproject":
        return _get_pyproject_version(config_path)
    elif config.config_type == "package":
        return _get_package_version(config_path)
    elif config.config_type == "requirements":
        return "0.1.0"  # Default for requirements.txt based components
    
    return "0.1.0"


def _get_pyproject_version(config_path: Path) -> str:
    """Get version from pyproject.toml"""
    try:
        import tomli
        with open(config_path, 'rb') as f:
            data = tomli.load(f)
        return data['project']['version']
    except ImportError:
        try:
            import toml
            with open(config_path, 'r') as f:
                data = toml.load(f)
            return data['project']['version']
        except ImportError:
            pass
    except Exception:
        pass
    return "0.1.0"


def _get_package_version(config_path: Path) -> str:
    """Get version from package.json"""
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        return data.get('version', '0.1.0')
    except Exception:
        return "0.1.0"


def bump_version(current_version: str, bump_type: str) -> str:
    """Bump version according to semantic versioning"""
    version_parts = current_version.split('.')
    major = int(version_parts[0]) if len(version_parts) > 0 else 0
    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    patch = int(version_parts[2]) if len(version_parts) > 2 else 0
    
    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    
    return f"{major}.{minor}.{patch}"


def update_version_file(component: str, new_version: str, repo_root: Path, dry_run: bool = False) -> bool:
    """Update version in configuration file"""
    if component == "platform":
        return _update_platform_version(new_version, repo_root, dry_run)
    
    if component not in COMPONENTS:
        error(f"Unknown component: {component}")
        return False
    
    config = COMPONENTS[component]
    config_path = repo_root / config.config_file
    
    if dry_run:
        from .utils import info
        info(f"Would update {config.config_file} version to: {new_version}")
        return True
    
    if config.config_type == "pyproject":
        return _update_pyproject_version(config_path, new_version, repo_root)
    elif config.config_type == "package":
        return _update_package_version(config_path, new_version, repo_root)
    elif config.config_type == "requirements":
        from .utils import info
        info(f"Component {component} uses requirements.txt - version tracked via git tags only")
        return True
    
    return False


def _update_platform_version(new_version: str, repo_root: Path, dry_run: bool) -> bool:
    """Update platform version file"""
    if dry_run:
        from .utils import info
        info(f"Would update {PLATFORM_VERSION_FILE} to: {new_version}")
        return True
    
    version_file = repo_root / PLATFORM_VERSION_FILE
    version_file.write_text(new_version)
    success(f"Updated {PLATFORM_VERSION_FILE} to: {new_version}")
    return True


def _update_pyproject_version(config_path: Path, new_version: str, repo_root: Path) -> bool:
    """Update version in pyproject.toml"""
    try:
        # Try using tomli/tomli_w
        try:
            import tomli
            import tomli_w
            
            with open(config_path, 'rb') as f:
                data = tomli.load(f)
            
            data['project']['version'] = new_version
            
            with open(config_path, 'wb') as f:
                tomli_w.dump(data, f)
            
            success(f"Updated {config_path.relative_to(repo_root)} version to: {new_version}")
            return True
            
        except ImportError:
            # Fallback to regex replacement
            content = config_path.read_text()
            pattern = r'(version\s*=\s*)["\']([^"\']*)["\']'
            new_content = re.sub(pattern, rf'\1"{new_version}"', content)
            config_path.write_text(new_content)
            success(f"Updated {config_path.relative_to(repo_root)} version to: {new_version}")
            return True
            
    except Exception as e:
        error(f"Failed to update {config_path}: {e}")
        return False


def _update_package_version(config_path: Path, new_version: str, repo_root: Path) -> bool:
    """Update version in package.json"""
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        data['version'] = new_version
        
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        success(f"Updated {config_path.relative_to(repo_root)} version to: {new_version}")
        return True
        
    except Exception as e:
        error(f"Failed to update {config_path}: {e}")
        return False 