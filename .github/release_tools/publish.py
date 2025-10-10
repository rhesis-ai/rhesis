"""
Publishing functionality for the Rhesis release tool.
Handles tag creation, pushing tags, and creating GitHub releases.
"""

import subprocess
import json
import urllib.request
import urllib.error
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re 
from .config import COMPONENTS, PLATFORM_VERSION_FILE, format_component_name
from .version import get_current_version
from .utils import info, warn, error, success, log



def find_repository_root() -> Path:
    """Find the repository root directory"""
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    else:
        error("Not in a git repository")
        sys.exit(1)
    
    return repo_root


def get_current_branch() -> Optional[str]:
    """Get the current git branch name"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_components_version(branch_name: str, repo_root: Path) -> Dict[str, str]:
    """Parse component versions from a release branch name"""
    components_versions = {}
    
    # Check all components for versions different from default
    for component in COMPONENTS.keys():
        try:
            current_version = get_current_version(component, repo_root)
            if current_version and current_version != "0.1.0":
                components_versions[component] = current_version
            elif current_version == "0.1.0":
                info(f"Component {component} has default version 0.1.0 - skipping")
        except Exception as e:
            warn(f"Failed to get version for component {component}: {e}")
            warn(f"Skipping component {component} due to version detection failure")
            continue
    
    # Check platform version
    try:
        platform_version = get_current_version("platform", repo_root)
        if platform_version and platform_version != "0.0.0":
            components_versions["platform"] = platform_version
    except Exception as e:
        warn(f"Failed to get platform version: {e}")
        warn("Skipping platform due to version detection failure")
    
    return components_versions


def get_remote_tags() -> List[str]:
    """Get list of tags from remote repository"""
    try:
        # Fetch latest tags from remote
        subprocess.run(["git", "fetch", "--tags"], capture_output=True, check=True)
        
        # Get all remote tags
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "origin"],
            capture_output=True, text=True, check=True
        )
        
        tags = []
        for line in result.stdout.strip().split('\n'):
            if line and 'refs/tags/' in line:
                tag = line.split('refs/tags/')[-1]
                # Remove ^{} suffix if present (annotated tags)
                if tag.endswith('^{}'):
                    tag = tag[:-3]
                tags.append(tag)
        
        return sorted(set(tags))  # Remove duplicates and sort
        
    except subprocess.CalledProcessError as e:
        error(f"Failed to fetch remote tags: {e}")
        return []


def generate_tag_name(component: str, version: str) -> str:
    """Generate appropriate tag name for a component"""
    if component == "platform":
        return f"v{version}"
    else:
        return f"{component}-v{version}"


def create_and_push_tag(component: str, version: str, dry_run: bool = False) -> bool:
    """Create and push a git tag for a component"""
    tag_name = generate_tag_name(component, version)
    
    if dry_run:
        info(f"Would create and push tag: {tag_name}")
        return True
    
    try:
        # Create annotated tag
        tag_message = f"Release {format_component_name(component)} version {version}"
        subprocess.run([
            "git", "tag", "-a", tag_name, "-m", tag_message
        ], check=True)
        
        success(f"Created tag: {tag_name}")
        
        # Push tag to remote
        subprocess.run([
            "git", "push", "origin", tag_name
        ], check=True)
        
        success(f"Pushed tag to remote: {tag_name}")
        return True
        
    except subprocess.CalledProcessError as e:
        error(f"Failed to create/push tag {tag_name}: {e}")
        return False


def get_changelog_content(changelog_path: Path) -> str:
# Read the changelog file
    with open(changelog_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Extract the first version section (latest) using regex
    # Pattern breakdown:
    # ^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\n  - matches version header like "## [0.4.0] - 2025-10-10"
    # (.*?)  - captures all content after the header (non-greedy)
    # (?=\n## \[|\Z)  - stops at next version header or end of file (positive lookahead)
    pattern = r'^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\n(.*?)(?=\n## \[|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    changelog_content = match.group(3)
    return changelog_content



def create_github_release(component: str, version: str, tag_name: str, dry_run: bool = False, set_as_latest: bool = False) -> bool:
    """Create a GitHub release for a component"""
    if dry_run:
        latest_info = " (marked as latest)" if set_as_latest else ""
        info(f"Would create GitHub release for {tag_name}{latest_info}")
        return True
    
    try:
        # Use gh CLI if available
        result = subprocess.run(["which", "gh"], capture_output=True)
        if result.returncode == 0:
            # Use GitHub CLI
            repo_root = find_repository_root()
            release_title = f"{format_component_name(component)} v{version}"
            if component == "platform":
                changelog_content = get_changelog_content(repo_root / "CHANGELOG.md")
            else:
                changelog_content = get_changelog_content(repo_root / COMPONENTS[component].changelog_path)
            cmd = [
                "gh", "release", "create", tag_name,
                "--title", release_title,
                "--notes", changelog_content
            ]
            
            # Add latest flag for platform releases
            if set_as_latest:
                cmd.append("--latest")
            
            subprocess.run(cmd, check=True)
            
            latest_info = " (marked as latest)" if set_as_latest else ""
            success(f"Created GitHub release: {tag_name}{latest_info}")
            return True
        else:
            warn("GitHub CLI (gh) not found. Skipping GitHub release creation.")
            warn("Install gh CLI and authenticate to enable GitHub release creation.")
            return True
            
    except subprocess.CalledProcessError as e:
        error(f"Failed to create GitHub release for {tag_name}: {e}")
        return False


def confirm_publish_action(components_to_publish: Dict[str, str], remote_tags: List[str]) -> bool:
    """Ask user for confirmation before publishing"""
    print()
    warn("⚠️  PUBLISH MODE - This will create tags and GitHub releases!")
    print()
    
    info("The following actions will be performed:")
    
    # Separate platform from other components for proper display ordering
    platform_actions = []
    other_actions = []
    
    for component, version in components_to_publish.items():
        tag_name = generate_tag_name(component, version)
        if tag_name not in remote_tags:
            action_info = [f"Create and push tag: {tag_name}"]
            if component == "platform":
                action_info.append(f"Create GitHub release: {tag_name} (marked as latest)")
                platform_actions.extend([f"  • {action}" for action in action_info])
            else:
                action_info.append(f"Create GitHub release: {tag_name}")
                other_actions.extend([f"  • {action}" for action in action_info])
        else:
            info(f"  • Skip {tag_name} (already exists)")
    
    # Display other components first, then platform
    for action in other_actions:
        info(action)
    
    if platform_actions:
        if other_actions:
            info("  • --- Platform release (created last) ---")
        for action in platform_actions:
            info(action)
    
    tags_to_create = len(other_actions) // 2 + len(platform_actions) // 2  # Each component has 2 actions
    if tags_to_create == 0:
        warn("No new tags to create. All component versions already have tags.")
        return False
    
    print()
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        info("Publishing in GitHub Actions - skipping confirmation")
        return True
    else:
        response = input("Do you want to proceed with publishing? (y/N): ").strip().lower()
        return response == 'y'


def publish_releases(repo_root: Path, dry_run: bool = False) -> bool:
    """Main publish function - create tags and GitHub releases"""
    # Check if we're in a git repository
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        error("Not in a git repository")
        return False
    
    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        error("Failed to get current branch")
        return False
    
    if not current_branch.startswith("release/"):
        error("Not on a release branch")
        return False
    
    info(f"Current branch: {current_branch}")
    
    # Parse components from branch
    try:
        components_version = get_components_version(current_branch, repo_root)
    except Exception as e:
        error(f"Failed to parse release components: {e}")
        return False
    
    log("Current components version:")
    for component, version in components_version.items():
        info(f"  {component}: v{version}")
    
    # Get remote tags
    info("Fetching remote tags...")
    remote_tags = get_remote_tags()
    
    # Show what will be done
    tags_to_create = []
    tags_to_skip = []
    
    # Separate platform from other components for ordering
    platform_version = None
    other_components = []
    
    for component, version in components_version.items():
        tag_name = generate_tag_name(component, version)
        if tag_name not in remote_tags:
            if component == "platform":
                platform_version = (component, version, tag_name)
            else:
                other_components.append((component, version, tag_name))
        else:
            tags_to_skip.append(tag_name)
    
    # Order components: other components first, then platform last
    tags_to_create = other_components
    if platform_version:
        tags_to_create.append(platform_version)
    
    if tags_to_skip:
        info("Tags that already exist (will be skipped):")
        for tag in tags_to_skip:
            info(f"  {tag}")
    
    if not tags_to_create:
        warn("No new tags to create. All component versions already have tags.")
        return True
    
    if dry_run:
        info("DRY RUN - Would create the following tags:")
        for component, version, tag_name in tags_to_create:
            info(f"  {tag_name}")
            info(f"    • Create and push tag")
            latest_info = " (marked as latest)" if component == "platform" else ""
            info(f"    • Create GitHub release{latest_info}")
        return True
    
    # Ask for confirmation
    if not confirm_publish_action(components_version, remote_tags):
        info("Publish cancelled by user")
        return False
    
    # Create and push tags
    print()
    log("Creating and pushing tags...")
    
    # Inform user about ordering if platform is included
    if platform_version:
        info("Note: Platform release will be created last and marked as latest")
    
    created_tags = []
    for component, version, tag_name in tags_to_create:
        if create_and_push_tag(component, version, dry_run):
            created_tags.append((component, version, tag_name))
        else:
            error(f"Failed to create tag for {component} v{version}")
            return False
    
    # Create GitHub releases
    print()
    log("Creating GitHub releases...")
    
    for component, version, tag_name in created_tags:
        # Determine if the component is the platform and if it should be marked as latest
        is_platform = component == "platform"
        if not create_github_release(component, version, tag_name, dry_run, set_as_latest=is_platform):
            warn(f"Failed to create GitHub release for {tag_name}")
            # Continue with other releases even if one fails
    
    print()
    success(f"Successfully published {len(created_tags)} releases! 🎉")
    
    if created_tags:
        info("Published releases:")
        for component, version, tag_name in created_tags:
            info(f"  • {tag_name}")
    
    return True 