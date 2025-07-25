"""
Publishing functionality for the Rhesis release tool.
Handles tag creation, pushing tags, and creating GitHub releases.
"""

import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import COMPONENTS, PLATFORM_VERSION_FILE, format_component_name
from .version import get_current_version
from .utils import info, warn, error, success, log


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


def parse_release_branch_components(branch_name: str, repo_root: Path) -> Dict[str, str]:
    """Parse component versions from a release branch name"""
    components_versions = {}
    
    if not branch_name.startswith("release/"):
        return components_versions
    
    # Handle different branch naming patterns
    release_part = branch_name.replace("release/", "")
    
    if release_part.startswith("v"):
        # Platform release: release/v1.0.0
        platform_version = release_part[1:]  # Remove 'v'
        components_versions["platform"] = platform_version
        
        # For platform releases, include all components at their current versions
        for component in COMPONENTS.keys():
            try:
                current_version = get_current_version(component, repo_root)
                if current_version and current_version != "0.1.0":  # Skip default versions
                    components_versions[component] = current_version
            except Exception:
                continue
                
    elif "-v" in release_part:
        # Component release: release/backend-v1.0.0 or release/multi-v1.0.0
        if release_part.startswith("multi-"):
            # Multi-component release
            version = release_part.replace("multi-v", "")
            if version:
                # Try to determine which components have this version
                for component in COMPONENTS.keys():
                    try:
                        current_version = get_current_version(component, repo_root)
                        if current_version == version:
                            components_versions[component] = version
                    except Exception:
                        continue
        else:
            # Single component release
            parts = release_part.split("-v")
            if len(parts) == 2:
                component, version = parts
                if component in COMPONENTS or component == "platform":
                    components_versions[component] = version
    
    # If we couldn't parse from branch name, fall back to reading current versions
    if not components_versions:
        warn(f"Could not parse components from branch name: {branch_name}")
        warn("Falling back to reading current versions from files")
        
        # Check all components for versions different from default
        for component in COMPONENTS.keys():
            try:
                current_version = get_current_version(component, repo_root)
                if current_version and current_version != "0.1.0":
                    components_versions[component] = current_version
            except Exception:
                continue
        
        # Check platform version
        try:
            platform_version = get_current_version("platform", repo_root)
            if platform_version and platform_version != "0.0.0":
                components_versions["platform"] = platform_version
        except Exception:
            pass
    
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


def create_github_release(component: str, version: str, tag_name: str, dry_run: bool = False) -> bool:
    """Create a GitHub release for a component"""
    if dry_run:
        info(f"Would create GitHub release for {tag_name}")
        return True
    
    try:
        # Use gh CLI if available
        result = subprocess.run(["which", "gh"], capture_output=True)
        if result.returncode == 0:
            # Use GitHub CLI
            release_title = f"{format_component_name(component)} v{version}"
            subprocess.run([
                "gh", "release", "create", tag_name,
                "--title", release_title,
                "--generate-notes"
            ], check=True)
            
            success(f"Created GitHub release: {tag_name}")
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
    
    tags_to_create = []
    for component, version in components_to_publish.items():
        tag_name = generate_tag_name(component, version)
        if tag_name not in remote_tags:
            tags_to_create.append((component, version, tag_name))
            info(f"  • Create and push tag: {tag_name}")
            info(f"  • Create GitHub release: {tag_name}")
        else:
            info(f"  • Skip {tag_name} (already exists)")
    
    if not tags_to_create:
        warn("No new tags to create. All component versions already have tags.")
        return False
    
    print()
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
    
    info(f"Current branch: {current_branch}")
    
    # Parse components from branch
    components_to_publish = parse_release_branch_components(current_branch, repo_root)
    
    if not components_to_publish:
        error("No components found to publish")
        error("Make sure you're on a release branch (release/...)")
        return False
    
    log("Found components to publish:")
    for component, version in components_to_publish.items():
        info(f"  {component}: v{version}")
    
    # Get remote tags
    info("Fetching remote tags...")
    remote_tags = get_remote_tags()
    
    # Show what will be done
    tags_to_create = []
    tags_to_skip = []
    
    for component, version in components_to_publish.items():
        tag_name = generate_tag_name(component, version)
        if tag_name not in remote_tags:
            tags_to_create.append((component, version, tag_name))
        else:
            tags_to_skip.append(tag_name)
    
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
            info(f"    • Create GitHub release")
        return True
    
    # Ask for confirmation
    if not confirm_publish_action(components_to_publish, remote_tags):
        info("Publish cancelled by user")
        return False
    
    # Create and push tags
    print()
    log("Creating and pushing tags...")
    
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
        if not create_github_release(component, version, tag_name, dry_run):
            warn(f"Failed to create GitHub release for {tag_name}")
            # Continue with other releases even if one fails
    
    print()
    success(f"Successfully published {len(created_tags)} releases! 🎉")
    
    if created_tags:
        info("Published releases:")
        for component, version, tag_name in created_tags:
            info(f"  • {tag_name}")
    
    return True 