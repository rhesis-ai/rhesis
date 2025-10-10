"""
Main release processing logic for the Rhesis release tool.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import json

from .config import COMPONENTS, format_component_name
from .utils import log, info, warn, success, check_prerequisites
from .version import get_current_version, bump_version, update_version_file
from .git_ops import create_release_branch, get_last_tag, get_commits_since_tag
from .changelog import (
    generate_changelog_with_llm, 
    generate_fallback_changelog, 
    update_component_changelog,
    update_platform_changelog
)


class ReleaseProcessor:
    """Main release processing class"""
    
    def __init__(self, repo_root: Path, dry_run: bool = False, gemini_api_key: str = "", no_branch: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.gemini_api_key = gemini_api_key
        self.no_branch = no_branch
        
        # Component versions and bumps
        self.component_versions: Dict[str, str] = {}
        self.component_bumps: Dict[str, str] = {}

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        success, api_key = check_prerequisites(self.repo_root, self.gemini_api_key)
        if success:
            self.gemini_api_key = api_key
        return success

    def create_release_branch(self) -> bool:
        """Create appropriate release branch based on components and versions"""
        return create_release_branch(
            self.component_bumps, 
            lambda component: get_current_version(component, self.repo_root),
            self.dry_run, 
            self.no_branch
        )

    def process_releases(self) -> bool:
        """Process all releases"""
        log("Starting release process...")
        version_changes = {}
        # First pass: collect current versions and calculate new versions
        for component, bump_type in self.component_bumps.items():
            current_version = get_current_version(component, self.repo_root)
            new_version = bump_version(current_version, bump_type)
            
            self.component_versions[component] = new_version
            
            info(f"Component: {component}")
            info(f"  Current version: {current_version}")
            info(f"  Bump type: {bump_type}")
            info(f"  New version: {new_version}")
            print()
            version_changes[component] = f"{current_version} -> {new_version} ({bump_type})"

        # Save version changes to a JSON file. This will be used to create the PR title and body in
        # the create-release.yml workflow.
        with open("/tmp/version_changes.json", "w") as f:
            json.dump(version_changes, f)
        
        if self.dry_run:
            warn("DRY RUN MODE - No changes will be made")
            print()
        
        # Second pass: update versions and changelogs
        for component, new_version in self.component_versions.items():
            log(f"Processing release for {component} v{new_version}...")
            
            # Update version files
            if not update_version_file(component, new_version, self.repo_root, self.dry_run, self.component_bumps):
                return False
            
            # Get commit history
            last_tag = get_last_tag(component)
            commits = get_commits_since_tag(component, last_tag)
            
            info(f"Last tag for {component}: {last_tag or '(none)'}")
            
            if commits:
                info(f"Found {len(commits)} commits since last release")
            else:
                info("No commits found since last release")
            
            # Generate changelog (skip for platform-wide releases)
            if component != "platform":
                changelog_content = None
                
                # Try LLM generation first
                if self.gemini_api_key:
                    llm_content = generate_changelog_with_llm(
                        self.gemini_api_key, component, new_version, commits, last_tag
                    )
                    if llm_content:
                        # Add proper header with current date to LLM-generated content
                        date = datetime.now().strftime("%Y-%m-%d")
                        changelog_content = f"## [{new_version}] - {date}\n\n{llm_content.strip()}\n"
                
                # Fall back to basic changelog if LLM failed
                if not changelog_content:
                    changelog_content = generate_fallback_changelog(new_version, commits)
                
                # Update component changelog
                if not update_component_changelog(component, new_version, changelog_content, self.repo_root, self.dry_run):
                    return False
            
            info(f"Version and changelog updated for {component} v{new_version}")
            
            success(f"Completed release for {component} v{new_version}")
            print()
        
        # Handle platform changelog if platform was included
        if "platform" in self.component_bumps:
            platform_version = self.component_versions.get("platform")
            if platform_version:
                update_platform_changelog(
                    self.component_versions, 
                    platform_version, 
                    self.gemini_api_key, 
                    self.repo_root, 
                    self.dry_run
                )
        
        return True

    def run(self, component_bumps: Dict[str, str]) -> bool:
        """Main entry point"""
        self.component_bumps = component_bumps
        
        if not self.check_prerequisites():
            return False
        
        # Create release branch if needed (unless --no-branch specified)
        if not self.no_branch:
            if not self.create_release_branch():
                return False
        
        log("Rhesis Platform Release Tool")
        log(f"Repository: {self.repo_root}")
        
        if self.dry_run:
            warn("Running in DRY RUN mode")
        
        print()
        
        if not self.process_releases():
            return False
        
        print()
        success("Release process completed! 🎉")
        
        if not self.dry_run:
            print()
            info("Next steps:")
            info("1. Review the changes made to version files and changelogs")
            info('2. Commit the changes: git add . && git commit -m "Prepare release: <description>"')
            info("3. Push and create PR: git push origin $(git branch --show-current)")
            info("   • Use ./.github/create-pr.sh or ./.github/pr to create the PR")
            info("4. After PR merge, use --publish to create tags and GitHub releases")
        
        return True 