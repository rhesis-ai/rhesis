"""
Version management functionality for the Rhesis release tool.
"""

import json
import re
import subprocess
from pathlib import Path

from release_tools.config import (
    COMPONENTS,
    PLATFORM_PINNED_FILES,
    PLATFORM_VERSION_FILE,
    SDK_CORE_REQUIREMENT,
)
from release_tools.utils import error, info, success


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
        if config.config_type == "package":
            return _get_package_version(config_path)
    except Exception as e:
        error(f"Failed to get version for component {component}: {e}")
        raise

    raise ValueError(f"Unknown config type for component {component}: {config.config_type}")


def _get_pyproject_version(config_path: Path) -> str:
    """Get version from pyproject.toml"""
    # --color never: uv honours FORCE_COLOR even when its output is captured, and the ANSI
    # escapes then end up inside the version string, where int() chokes on them.
    cmd = ["uv", "version", "--short", "--color", "never", "--project", config_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        print(e.stdout)
        exit(1)
    version = result.stdout.strip()
    return version


def _get_package_version(config_path: Path) -> str:
    """Get version from package.json"""
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        version = data.get("version")
        if not version:
            error(f"No version field found in {config_path}")
            raise KeyError("version field missing")
        return version
    except FileNotFoundError:
        error(f"Package.json file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        error(f"Invalid JSON in {config_path}: {e}")
        raise
    except Exception as e:
        error(f"Failed to parse {config_path}: {e}")
        raise


def bump_version(current_version: str, bump_type: str) -> str:
    """Bump version according to semantic versioning"""
    version_parts = current_version.split(".")
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


def update_version_file(
    component: str,
    new_version: str,
    repo_root: Path,
    dry_run: bool = False,
) -> bool:
    """Update version in configuration file"""
    if component == "platform":
        return _update_platform_version(new_version, repo_root, dry_run)

    if component not in COMPONENTS:
        error(f"Unknown component: {component}")
        return False

    config = COMPONENTS[component]
    config_path = repo_root / config.config_file

    if dry_run:
        info(f"Would update {config.config_file} version to: {new_version}")
        if component == "sdk":
            info(f"Would raise the SDK's rhesis requirement to: >={new_version}")
        return True

    if config.config_type == "pyproject":
        # Checked first so a missing requirement fails before any file changes.
        if component == "sdk" and not _sdk_core_floor_found(repo_root):
            return False
        if not _update_pyproject_version(config_path, new_version):
            return False
        return component != "sdk" or pin_sdk_core_floor(new_version, repo_root)
    if config.config_type == "package":
        return _update_package_version(config_path, new_version, repo_root)

    error(f"Unknown config type for component {component}: {config.config_type}")
    return False


def _update_platform_version(new_version: str, repo_root: Path, dry_run: bool) -> bool:
    """Update the platform version file and the deploy files pinned to it"""
    if dry_run:
        info(f"Would update {PLATFORM_VERSION_FILE} to: {new_version}")
        for rel_path in PLATFORM_PINNED_FILES:
            info(f"Would pin {rel_path} to: {new_version}")
        return True

    version_file = repo_root / PLATFORM_VERSION_FILE
    version_file.write_text(new_version)
    success(f"Updated {PLATFORM_VERSION_FILE} to: {new_version}")
    return pin_platform_files(new_version, repo_root)


def pin_platform_files(new_version: str, repo_root: Path) -> bool:
    """Write the platform version into the deploy files that name it"""
    for rel_path, pattern in PLATFORM_PINNED_FILES.items():
        path = repo_root / rel_path
        text, count = re.subn(
            pattern, lambda m: f"{m.group(1)}{new_version}{m.group(2)}", path.read_text()
        )
        if count == 0:
            error(f"Found no version to update in {rel_path}")
            return False
        path.write_text(text)
        success(f"Pinned {rel_path} to: {new_version}")
    return True


def _sdk_core_floor_found(repo_root: Path) -> bool:
    rel_path, pattern = SDK_CORE_REQUIREMENT
    count = len(re.findall(pattern, (repo_root / rel_path).read_text()))
    if count != 1:
        error(f"Expected one rhesis[telemetry] requirement in {rel_path}, found {count}")
    return count == 1


def pin_sdk_core_floor(new_version: str, repo_root: Path) -> bool:
    """Raise the SDK's requirement on the core package to the version being released"""
    if not _sdk_core_floor_found(repo_root):
        return False
    rel_path, pattern = SDK_CORE_REQUIREMENT
    path = repo_root / rel_path
    path.write_text(
        re.sub(pattern, lambda m: f"{m.group(1)}{new_version}{m.group(3)}", path.read_text())
    )
    success(f"Raised the rhesis requirement in {rel_path} to: >={new_version}")
    return True


def _update_pyproject_version(config_path: Path, new_version: str) -> bool:
    """Update version in pyproject.toml.

    Sets the version outright rather than using `uv version --bump`: bump_version has already
    computed it, and a platform-following component has no bump type of its own.
    """
    # --color never keeps escape codes out of the stderr we print on failure
    cmd = [
        "uv",
        "version",
        new_version,
        "--color",
        "never",
        "--project",
        config_path,
        "--no-sync",
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        print(e.stdout)
        return False


def _update_package_version(config_path: Path, new_version: str, repo_root: Path) -> bool:
    """Update version in package.json and its lockfile"""
    try:
        with open(config_path, "r") as f:
            data = json.load(f)

        data["version"] = new_version

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
            # Add a newline to the end of the file, to make the frontend linter happy
            f.write("\n")
        success(f"Updated {config_path.relative_to(repo_root)} version to: {new_version}")
        return _update_package_lock_version(config_path, new_version, repo_root)

    except Exception as e:
        error(f"Failed to update {config_path}: {e}")
        return False


def _update_package_lock_version(config_path: Path, new_version: str, repo_root: Path) -> bool:
    """Mirror the new version into the sibling package-lock.json, when there is one.

    Bumping only package.json leaves the lockfile a release behind, so the next
    `npm install` rewrites it and the version churn surfaces as unrelated noise in
    whichever PR ran it. uv keeps uv.lock in step for the Python components; npm
    only does the same when it runs, which release does not do.
    """
    lock_path = config_path.parent / "package-lock.json"
    if not lock_path.exists():
        return True

    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["version"] = new_version
        # lockfileVersion 2 and 3 repeat the root package's version under packages[""].
        root_package = data.get("packages", {}).get("")
        if root_package is not None:
            root_package["version"] = new_version

        with open(lock_path, "w", encoding="utf-8") as f:
            # indent=2 plus a trailing newline reproduces npm's own formatting byte for
            # byte, so rewriting the file touches nothing but the version fields.
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        success(f"Updated {lock_path.relative_to(repo_root)} version to: {new_version}")
        return True

    except Exception as e:
        error(f"Failed to update {lock_path}: {e}")
        return False
