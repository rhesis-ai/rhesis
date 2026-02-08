"""
Git operations for the Rhesis release tool.
"""

import hashlib
import re
import subprocess
from typing import Dict, List, Optional

from .config import COMPONENT_PATHS
from .utils import error, info, success, warn


def get_last_tag(component: str) -> Optional[str]:
    """Get the last git tag for a component"""
    if component == "platform":
        tag_pattern = "v*"
    else:
        tag_pattern = f"{component}-v*"

    try:
        result = subprocess.run(
            ["git", "tag", "-l", tag_pattern], capture_output=True, text=True, check=True
        )
        tags = result.stdout.strip().split("\n") if result.stdout.strip() else []
        if tags:
            # Sort tags by version
            return sorted(tags, key=lambda x: [int(i) for i in re.findall(r"\d+", x)])[-1]
        return None
    except subprocess.CalledProcessError:
        return None


def get_commits_since_tag(component: str, last_tag: Optional[str]) -> List[Dict[str, str]]:
    """Get commits since last tag for a component.

    Returns commits with full message (subject + body) for better changelog context.
    """
    component_path = COMPONENT_PATHS.get(component, ".")

    git_range = f"{last_tag}..HEAD" if last_tag else "HEAD"

    # Use a unique delimiter to separate commits since body can contain newlines
    delimiter = "---COMMIT_END---"

    try:
        # %H=hash, %an=author, %ai=date, %s=subject, %b=body
        cmd = ["git", "log", f"--pretty=format:%H|%an|%ai|%s|%b{delimiter}", git_range]
        if component != "platform":
            cmd.extend(["--", component_path])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        commits = []
        for entry in result.stdout.split(delimiter):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split("|", 4)
            if len(parts) >= 4:
                subject = parts[3]
                body = parts[4].strip() if len(parts) > 4 else ""
                # Combine subject and body for full message
                if body:
                    message = f"{subject}\n\n{body}"
                else:
                    message = subject
                commits.append(
                    {"hash": parts[0], "author": parts[1], "date": parts[2], "message": message}
                )

        return commits

    except subprocess.CalledProcessError:
        return []


def generate_branch_name(component_bumps: Dict[str, str], get_version_func) -> str:
    """Generate appropriate branch name based on release components"""
    # Get target versions for all components
    component_versions = []
    unique_versions = set()

    for component, bump_type in component_bumps.items():
        current_version = get_version_func(component)
        if not current_version:
            continue
        # Import bump_version function from version module
        from .version import bump_version

        new_version = bump_version(current_version, bump_type)
        component_versions.append((component, new_version))
        unique_versions.add(new_version)

    # Determine branch naming strategy
    if len(component_versions) == 1:
        # Single component
        component, version = component_versions[0]
        if component == "platform":
            return f"release/v{version}"
        else:
            return f"release/{component}-v{version}"

    elif "platform" in [comp for comp, _ in component_versions]:
        # Platform release
        platform_version = next(ver for comp, ver in component_versions if comp == "platform")
        return f"release/v{platform_version}"

    elif len(unique_versions) == 1:
        # Multiple components, same version
        version = unique_versions.pop()
        return f"release/multi-v{version}"

    else:
        # Multiple components, different versions
        # Use a short hash of component names for uniqueness
        component_names = sorted([comp for comp, _ in component_versions])
        hash_input = "-".join(component_names)
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:6]
        return f"release/multi-{short_hash}"


def create_release_branch(
    component_bumps: Dict[str, str],
    get_version_func,
    dry_run: bool = False,
    no_branch: bool = False,
) -> bool:
    """Create appropriate release branch based on components and versions"""
    if no_branch:
        info("Skipping branch creation (--no-branch specified)")
        return True

    # Check if we're on main branch
    try:
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        error("Failed to get current branch")
        return False

    # If already on a release branch, skip creation
    if current_branch.startswith("release/"):
        info(f"Already on release branch: {current_branch}")
        return True

    # If not on main, warn but continue
    if current_branch != "main":
        warn(f"Not on main branch (currently on: {current_branch})")
        if not dry_run:
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != "y":
                info("Release cancelled")
                return False

    # Generate branch name based on release components
    branch_name = generate_branch_name(component_bumps, get_version_func)

    if dry_run:
        info(f"Would create release branch: {branch_name}")
        return True

    # Check if branch already exists
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
            check=True,
        )
        error(f"Branch {branch_name} already exists")
        return False
    except subprocess.CalledProcessError:
        # Branch doesn't exist, which is what we want
        pass

    # Create and checkout the branch
    try:
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)
        success(f"Created and switched to branch: {branch_name}")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to create branch {branch_name}: {e}")
        return False
