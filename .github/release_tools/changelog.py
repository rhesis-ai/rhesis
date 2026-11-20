"""
Changelog generation for the Rhesis release tool.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import COMPONENTS, PLATFORM_CHANGELOG, format_component_name
from .git_ops import get_commits_since_tag, get_last_tag
from .utils import call_gemini_api, info, success, warn

UNRELEASED_MARKER = "## [Unreleased]"
UPGRADE_NOTES_HEADING = "### Upgrading a self-hosted deployment"
NO_UPGRADE_NOTES = "None. No configuration or infrastructure changes are needed."


def generate_changelog_with_llm(
    api_key: str,
    component: str,
    version: str,
    commits: List[Dict[str, str]],
    last_tag: Optional[str],
) -> Optional[str]:
    """Generate changelog using Gemini API"""
    if not api_key:
        warn(f"No Gemini API key available. Skipping LLM changelog generation for {component}")
        return None

    commits_text = "\n".join(
        [f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})" for commit in commits]
    )

    prompt = f"""Generate a professional changelog entry for version {version} of the {format_component_name(component)} component in a software project.

Based on these commits since the last release{f" ({last_tag})" if last_tag else ""}:

{commits_text}

Please format the output as a markdown changelog section following the 'Keep a Changelog' format. Include appropriate categories like Added, Changed, Fixed, Removed, etc. Be concise but informative. Focus on user-facing changes and improvements.

Do NOT include the version header line (## [version] - date) - only return the content sections (### Added, ### Changed, etc.).

Return ONLY the changelog content without any additional text or explanations."""

    return call_gemini_api(api_key, prompt)


def generate_component_summary_with_llm(
    api_key: str,
    component: str,
    version: str,
    commits: List[Dict[str, str]],
    last_tag: Optional[str],
) -> Optional[str]:
    """Generate a brief component summary for platform changelog using Gemini API"""
    if not api_key:
        warn(f"No Gemini API key available. Skipping LLM summary generation for {component}")
        return None

    commits_text = "\n".join(
        [f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})" for commit in commits]
    )

    prompt = f"""Generate a brief bullet point summary of changes for version {version} of the {format_component_name(component)} component.

Based on these commits since the last release{f" ({last_tag})" if last_tag else ""}:

{commits_text}

Focus on the most important user-facing changes and improvements. Format as 2-4 bullet points using simple dashes (-). Keep each point concise and informative.

Return ONLY the bullet points without any additional text or explanations."""

    return call_gemini_api(api_key, prompt)


def placeholder_entry(component: str) -> str:
    """Unmissable stand-in for a changelog section the LLM failed to produce.

    Never fabricate the section from commit subjects -- it reads as real prose, and two releases
    shipped it before anyone noticed.
    """
    return f"- TODO: changelog generation failed for {component}; write this section by hand.\n"


def _unreleased_bounds(lines: List[str], changelog_path: Path) -> tuple[int, int]:
    """Line range of the [Unreleased] section: its heading, and the next version heading or EOF."""
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == UNRELEASED_MARKER)
    except StopIteration:
        raise ValueError(f"{changelog_path} has no '{UNRELEASED_MARKER}' heading")

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return start, end


def take_upgrade_notes(changelog_path: Path) -> str:
    """Cut the hand-written upgrade notes out of [Unreleased] and return them.

    The LLM can't tell from commit subjects what a self-hoster has to change, so these come from
    the PRs that need them. Returns an empty string when no PR wrote any.
    """
    lines = changelog_path.read_text().split("\n")
    start, end = _unreleased_bounds(lines, changelog_path)

    heading = next(
        (i for i in range(start + 1, end) if lines[i].strip() == UPGRADE_NOTES_HEADING), None
    )
    if heading is None:
        return ""

    stop = next((i for i in range(heading + 1, end) if lines[i].startswith("### ")), end)
    notes = "\n".join(lines[heading + 1 : stop]).strip()

    del lines[heading:stop]
    changelog_path.write_text("\n".join(lines))
    return notes


def _insert_under_unreleased(changelog_path: Path, entry: str) -> None:
    """Insert an entry below the [Unreleased] section, above the newest released version.

    Anything hand-written under [Unreleased] stays there. Inserting directly beneath the heading
    instead would leave those entries under the new version header, reading as part of a release
    that never contained them.
    """
    lines = changelog_path.read_text().split("\n")
    _, insert_at = _unreleased_bounds(lines, changelog_path)

    lines[insert_at:insert_at] = entry.split("\n") + [""]
    changelog_path.write_text("\n".join(lines))


def update_component_changelog(
    component: str, new_version: str, changelog_content: str, repo_root: Path, dry_run: bool = False
) -> bool:
    """Update component changelog"""
    if component not in COMPONENTS:
        warn(f"No changelog path defined for component: {component}")
        return False

    changelog_path = repo_root / COMPONENTS[component].changelog_path

    if dry_run:
        info(f"Would update changelog: {COMPONENTS[component].changelog_path}")
        info("New content:")
        print("\n".join(changelog_content.split("\n")[:10]))
        return True

    # Create changelog if it doesn't exist
    if not changelog_path.exists():
        changelog_path.parent.mkdir(parents=True, exist_ok=True)

        header = f"""# {format_component_name(component)} Changelog

All notable changes to the {component} component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{UNRELEASED_MARKER}

"""
        changelog_path.write_text(header)

    _insert_under_unreleased(changelog_path, changelog_content)
    success(f"Updated changelog: {COMPONENTS[component].changelog_path}")
    return True


def update_platform_changelog(
    component_versions: Dict[str, str],
    new_version: str,
    api_key: str,
    repo_root: Path,
    dry_run: bool = False,
) -> bool:
    """Update platform changelog"""
    if dry_run:
        info(f"Would update platform changelog: {PLATFORM_CHANGELOG}")
        info("Platform changelog would include LLM-generated summaries for each component")
        return True

    changelog_path = repo_root / PLATFORM_CHANGELOG
    date = datetime.now().strftime("%Y-%m-%d")

    # Generate platform changelog entry
    platform_entry = f"""## [{new_version}] - {date}

### Platform Release

This release includes the following component versions:
"""

    # Add component versions
    for component, version in component_versions.items():
        if component != "platform":
            platform_entry += f"- **{format_component_name(component)} {version}**\n"

    summary = "\n### Summary of Changes\n\n"

    # Generate summaries for each component
    for component, version in component_versions.items():
        if component != "platform":
            # Get commit history for this component
            last_tag = get_last_tag(component)
            commits = get_commits_since_tag(component, last_tag)

            component_name = format_component_name(component)
            summary += f"**{component_name} v{version}:**\n"

            component_summary = None
            if api_key and commits:
                component_summary = generate_component_summary_with_llm(
                    api_key, component, version, commits, last_tag
                )

            if component_summary:
                summary += f"{component_summary}\n\n"
            elif commits:
                summary += f"{placeholder_entry(component)}\n"
            else:
                summary += "Initial release or no significant changes.\n\n"

    summary += "See individual component changelogs for detailed changes:\n"

    for component in component_versions:
        if component != "platform" and component in COMPONENTS:
            changelog_path_rel = COMPONENTS[component].changelog_path
            summary += f"- [{format_component_name(component)} Changelog]({changelog_path_rel})\n"

    summary += "\n"

    # Cut the notes only now, after the git calls above, so a failure leaves them in place.
    # Every release says whether self-hosters must act, so "None" is a statement, not a gap.
    upgrade_notes = take_upgrade_notes(changelog_path) or NO_UPGRADE_NOTES
    platform_entry += f"\n{UPGRADE_NOTES_HEADING}\n\n{upgrade_notes}\n" + summary

    _insert_under_unreleased(changelog_path, platform_entry)
    success(f"Updated platform changelog: {PLATFORM_CHANGELOG}")
    return True
