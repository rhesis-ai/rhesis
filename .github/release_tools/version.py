"""
Version management functionality for the Rhesis release tool.
"""

import json
import re
import os
import subprocess
from pathlib import Path
from typing import Optional

from .config import COMPONENTS, PLATFORM_VERSION_FILE
from .utils import success, error, warn, info


def _check_virtual_environments() -> Optional[str]:
    """Check for common virtual environment setups and return activation hint"""
    hints = []
    
    # Check for UV virtual environment in common locations
    venv_locations = [
        (Path(".venv"), "source .venv/bin/activate"),
        (Path("../.venv"), "source ../.venv/bin/activate"),
        (Path("venv"), "source venv/bin/activate"),
        (Path("../venv"), "source ../venv/bin/activate"),
    ]
    
    for venv_path, activation_cmd in venv_locations:
        if venv_path.exists() and (venv_path / "bin" / "activate").exists():
            hints.append(f"Virtual environment detected at {venv_path.resolve()}. Run: {activation_cmd}")
            break  # Use the first one found
    
    # Check for conda environment file
    if Path("environment.yml").exists() or Path("environment.yaml").exists():
        hints.append("Conda environment file detected. Run: conda env create -f environment.yml && conda activate <env-name>")
    
    # Check for Poetry
    if Path("pyproject.toml").exists():
        try:
            with open("pyproject.toml", 'r') as f:
                content = f.read()
                if "[tool.poetry]" in content:
                    hints.append("Poetry project detected. Run: poetry install && poetry shell")
        except Exception:
            pass
    
    # Check for requirements files
    if Path("requirements.txt").exists():
        hints.append("Requirements file detected. Run: pip install -r requirements.txt")
    
    # Return the most specific hint first
    return hints[0] if hints else None


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
    
    try:
        if config.config_type == "pyproject":
            return _get_pyproject_version(config_path)
        elif config.config_type == "package":
            return _get_package_version(config_path)
        elif config.config_type == "requirements":
            from .utils import warn
            warn(f"Component {component} uses requirements.txt - no version file, using default 0.1.0")
            return "0.1.0"  # Default for requirements.txt based components
    except Exception as e:
        from .utils import error
        error(f"Failed to get version for component {component}: {e}")
        raise
    
    return "0.1.0"


def _try_install_toml_libraries() -> bool:
    """Try to automatically install TOML parsing libraries"""
    from .utils import warn, info, error
    
    info("Attempting to automatically install TOML libraries...")
    
    # Try different installation methods
    install_commands = [
        ["pip", "install", "tomli", "tomli-w"],
        ["pip3", "install", "tomli", "tomli-w"],
        ["python", "-m", "pip", "install", "tomli", "tomli-w"],
        ["python3", "-m", "pip", "install", "tomli", "tomli-w"],
    ]
    
    for cmd in install_commands:
        try:
            info(f"Trying: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                info("Successfully installed TOML libraries!")
                
                # Verify installation worked
                try:
                    import tomli
                    info("TOML libraries verified and ready to use.")
                    return True
                except ImportError:
                    warn("Installation completed but libraries not accessible. May need to restart.")
                    return False
            else:
                warn(f"Command failed: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            warn(f"Installation timed out: {' '.join(cmd)}")
        except FileNotFoundError:
            continue  # Try next command
        except Exception as e:
            warn(f"Installation failed: {e}")
    
    # Try conda as fallback
    try:
        info("Trying conda installation...")
        result = subprocess.run(["conda", "install", "-y", "tomli", "tomli-w"], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            info("Successfully installed TOML libraries via conda!")
            try:
                import tomli
                return True
            except ImportError:
                warn("Conda installation completed but libraries not accessible.")
                return False
    except Exception:
        pass
    
    error("Failed to automatically install TOML libraries.")
    error("Please install manually with one of:")
    error("  pip install tomli tomli-w")
    error("  conda install tomli tomli-w")
    error("  uv pip install tomli tomli-w")
    return False


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
            from .utils import warn, error, info
            
            warn("TOML parser libraries not found.")
            
            # Try automatic installation
            if _try_install_toml_libraries():
                # Retry parsing after installation
                try:
                    import tomli
                    with open(config_path, 'rb') as f:
                        data = tomli.load(f)
                    return data['project']['version']
                except Exception as e:
                    error(f"Still failed to parse after installation: {e}")
                    raise RuntimeError(f"TOML parser installation succeeded but parsing failed: {config_path}")
            
            # Check for virtual environment setup if auto-install failed
            venv_hint = _check_virtual_environments()
            if venv_hint:
                warn(f"Environment issue detected: {venv_hint}")
                warn("Then run: pip install tomli tomli-w")
            else:
                warn("If using a virtual environment, make sure it's activated first")
            
            error(f"Cannot read version from {config_path}")
            raise RuntimeError(f"TOML parser not available for {config_path}")
    except KeyError as e:
        from .utils import error
        error(f"Missing version field in {config_path}: {e}")
        raise
    except Exception as e:
        from .utils import error
        error(f"Failed to parse {config_path}: {e}")
        raise


def _get_package_version(config_path: Path) -> str:
    """Get version from package.json"""
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        version = data.get('version')
        if not version:
            from .utils import error
            error(f"No version field found in {config_path}")
            raise KeyError("version field missing")
        return version
    except FileNotFoundError:
        from .utils import error
        error(f"Package.json file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        from .utils import error
        error(f"Invalid JSON in {config_path}: {e}")
        raise
    except Exception as e:
        from .utils import error
        error(f"Failed to parse {config_path}: {e}")
        raise


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