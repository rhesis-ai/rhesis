"""
Main release processing logic for the Rhesis release tool.
"""

import json
from pathlib import Path
from typing import Dict

from release_tools.changelog import (
    generate_changelog_with_llm,
    placeholder_entry,
    read_unreleased,
    update_component_changelog,
    update_platform_changelog,
)
from release_tools.config import COMPONENTS, platform_followers
from release_tools.git_ops import create_release_branch, get_commits_since_tag, get_last_tag
from release_tools.utils import check_prerequisites, info, log, success, warn
from release_tools.version import bump_version, get_current_version, update_version_file


class ReleaseProcessor:
    """Main release processing class"""

    def __init__(
        self,
        repo_root: Path,
        dry_run: bool = False,
        gemini_api_key: str = "",
        no_branch: bool = False,
    ):
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
        )

    @staticmethod
    def _in_canonical_order(versions: Dict[str, str]) -> Dict[str, str]:
        """Reorder versions to COMPONENTS order, platform first"""
        order = ["platform"] + list(COMPONENTS)
        return {name: versions[name] for name in order if name in versions}

    def _update_docs_changelog(self, platform_version: str) -> bool:
        """Draft the aggregated docs changelog from the components in this release."""
        from release_tools.changelog import (
            DOCS_COMPONENT_ORDER,
            docs_placeholder_entry,
            extract_release_notes,
            update_docs_changelog,
        )

        if self.dry_run:
            info(f"Would generate docs changelog draft for platform v{platform_version}")
            return True

        component_versions = {
            component: self.component_versions[component]
            for component in DOCS_COMPONENT_ORDER
            if component in self.component_versions
        }
        component_changelogs = {}
        for component, version in component_versions.items():
            config = COMPONENTS.get(component)
            if config is None:
                continue
            path = self.repo_root / config.changelog_path
            if not path.exists():
                warn(f"No changelog for {component}; leaving it out of the docs draft")
                continue
            notes = extract_release_notes(path.read_text(), version)
            if notes:
                component_changelogs[component] = notes
            else:
                warn(f"No Unreleased or {version} notes for {component} in the docs draft")

        entry = generate_docs_changelog_with_llm(
            self.gemini_api_key,
            platform_version,
            component_changelogs,
            self.repo_root,
            component_versions,
        )
        if not entry:
            warn("Writing a visible TODO placeholder for the docs changelog")
            entry = docs_placeholder_entry(component_versions)

        return update_docs_changelog(
            platform_version,
            entry,
            self.repo_root,
            self.dry_run,
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
            version_changes[component] = f"v{current_version} -> v{new_version}"

        # Save version changes to a JSON file. This will be used to create the PR title and body in
        # the create-release.yml workflow. Platform followers are deliberately absent: they carry
        # the platform's number, so listing them would repeat it once per component.
        with open("/tmp/version_changes.json", "w") as f:
            json.dump(version_changes, f)

        # Platform followers take the platform's version rather than a bump of their own. Added
        # after version_changes above, and before the second pass below, so they still get their
        # version file and changelog written like any other component.
        platform_version = self.component_versions.get("platform")
        if platform_version:
            for component in platform_followers():
                self.component_versions[component] = platform_version
                info(f"Component: {component} (follows platform)")
                info(f"  Version: {platform_version}")
                print()
            # Canonical order, so the platform changelog's sections don't reshuffle from release to
            # release depending on which components were bumped
            self.component_versions = self._in_canonical_order(self.component_versions)

        if self.dry_run:
            warn("DRY RUN MODE - No changes will be made")
            print()

        # Second pass: update versions and changelogs
        for component, new_version in self.component_versions.items():
            log(f"Processing release for {component} v{new_version}...")

            # Update version files
            if not update_version_file(
                component,
                new_version,
                self.repo_root,
                self.dry_run,
            ):
                return False

            # Get commit history
            last_tag = get_last_tag(component)
            commits = get_commits_since_tag(component, last_tag)

            info(f"Last tag for {component}: {last_tag or '(none)'}")

            if commits:
                info(f"Found {len(commits)} commits since last release")
            else:
                info("No commits found since last release")

            # The platform changelog is written once, after every component
            if component != "platform":
                if not self._write_component_changelog(component, new_version, commits, last_tag):
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
                    self.dry_run,
                )
                if not self._update_docs_changelog(platform_version):
                    warn("Docs changelog draft was not written; continuing with the release")

        return True

    def _write_component_changelog(
        self, component: str, new_version: str, commits: list, last_tag: str | None
    ) -> bool:
        handwritten = ""
        if component in COMPONENTS:
            handwritten = read_unreleased(self.repo_root / COMPONENTS[component].changelog_path)

        body = None
        if self.gemini_api_key:
            llm_content = generate_changelog_with_llm(
                self.gemini_api_key, component, new_version, commits, last_tag, handwritten
            )
            if llm_content:
                body = llm_content.strip()

        if body is None:
            body = placeholder_entry(component).rstrip()

        return update_component_changelog(
            component, new_version, body, self.repo_root, self.dry_run
        )

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

        return True

# Exposed for tests that monkeypatch the docs generator.
from release_tools.changelog import generate_docs_changelog_with_llm  # noqa: E402,F401
