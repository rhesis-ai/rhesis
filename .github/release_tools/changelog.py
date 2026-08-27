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


def _insert_under_unreleased(changelog_path: Path, entry: str) -> None:
    """Insert an entry below the [Unreleased] section, above the newest released version.

    Anything hand-written under [Unreleased] stays there. Inserting directly beneath the heading
    instead would leave those entries under the new version header, reading as part of a release
    that never contained them.
    """
    lines = changelog_path.read_text().split("\n")

    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == UNRELEASED_MARKER)
    except StopIteration:
        raise ValueError(f"{changelog_path} has no '{UNRELEASED_MARKER}' heading to insert under")

    # Skip past any existing Unreleased content to the next section heading, or the end of the file
    insert_at = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )

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

    platform_entry += "\n### Summary of Changes\n\n"

    # Generate summaries for each component
    for component, version in component_versions.items():
        if component != "platform":
            # Get commit history for this component
            last_tag = get_last_tag(component)
            commits = get_commits_since_tag(component, last_tag)

            component_name = format_component_name(component)
            platform_entry += f"**{component_name} v{version}:**\n"

            summary = None
            if api_key and commits:
                summary = generate_component_summary_with_llm(
                    api_key, component, version, commits, last_tag
                )

            if summary:
                platform_entry += f"{summary}\n\n"
            elif commits:
                platform_entry += f"{placeholder_entry(component)}\n"
            else:
                platform_entry += "Initial release or no significant changes.\n\n"

    platform_entry += "See individual component changelogs for detailed changes:\n"

    for component in component_versions:
        if component != "platform" and component in COMPONENTS:
            changelog_path_rel = COMPONENTS[component].changelog_path
            platform_entry += (
                f"- [{format_component_name(component)} Changelog]({changelog_path_rel})\n"
            )

    platform_entry += "\n"

    _insert_under_unreleased(changelog_path, platform_entry)
    success(f"Updated platform changelog: {PLATFORM_CHANGELOG}")
    return True
