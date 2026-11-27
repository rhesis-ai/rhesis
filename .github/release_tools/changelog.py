"""
Changelog generation for the Rhesis release tool.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from release_tools.config import COMPONENTS, PLATFORM_CHANGELOG, format_component_name
from release_tools.git_ops import get_commits_since_tag, get_last_tag
from release_tools.utils import call_gemini_api, info, success, warn

UNRELEASED_MARKER = "## [Unreleased]"
UPGRADE_NOTES_HEADING = "### Upgrading a self-hosted deployment"
NO_UPGRADE_NOTES = "None. No configuration or infrastructure changes are needed."


def generate_changelog_with_llm(
    api_key: str,
    component: str,
    version: str,
    commits: List[Dict[str, str]],
    last_tag: Optional[str],
    handwritten: str = "",
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

    if handwritten:
        prompt += f"""

These entries were written by hand for this release and will be included as they are. Leave out
the changes they already describe:

{handwritten}"""

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


def read_unreleased(changelog_path: Path) -> str:
    """The hand-written entries under [Unreleased], or an empty string."""
    if not changelog_path.exists():
        return ""
    lines = changelog_path.read_text().split("\n")
    start, end = _unreleased_bounds(lines, changelog_path)
    return "\n".join(lines[start + 1 : end]).strip()


def take_unreleased(changelog_path: Path) -> str:
    """Cut the hand-written entries out of [Unreleased], leaving its heading, and return them."""
    entries = read_unreleased(changelog_path)
    if entries:
        lines = changelog_path.read_text().split("\n")
        start, end = _unreleased_bounds(lines, changelog_path)
        lines[start + 1 : end] = [""]
        changelog_path.write_text("\n".join(lines))
    return entries


def _sections(text: str) -> List[Tuple[Optional[str], List[str]]]:
    """Split changelog text into (### heading, lines) pairs; text before any heading gets None."""
    sections: List[Tuple[Optional[str], List[str]]] = [(None, [])]
    for line in text.split("\n"):
        if line.startswith("### "):
            sections.append((line.strip(), []))
        else:
            sections[-1][1].append(line)
    trimmed = [(heading, "\n".join(lines).strip().split("\n")) for heading, lines in sections]
    return [(heading, lines) for heading, lines in trimmed if heading or lines != [""]]


def merge_entries(handwritten: str, generated: str) -> str:
    """Put the hand-written entries under the matching ### headings of the generated ones.

    Hand-written entries go first under a shared heading; headings only they use follow.
    """
    remaining = {
        (heading or "").lower(): (heading, lines) for heading, lines in _sections(handwritten)
    }
    merged = []
    for heading, lines in _sections(generated):
        _, own = remaining.pop((heading or "").lower(), (heading, []))
        merged.append((heading, own + lines))
    merged.extend(remaining.values())

    return "\n\n".join(
        f"{heading}\n\n" + "\n".join(lines) if heading else "\n".join(lines)
        for heading, lines in merged
    )


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
    """Insert an entry below the [Unreleased] section, above the newest released version."""
    lines = changelog_path.read_text().split("\n")
    _, insert_at = _unreleased_bounds(lines, changelog_path)

    lines[insert_at:insert_at] = entry.split("\n") + [""]
    changelog_path.write_text("\n".join(lines))


def update_component_changelog(
    component: str, new_version: str, body: str, repo_root: Path, dry_run: bool = False
) -> bool:
    """Write the new version's entry: the [Unreleased] entries plus the generated body."""
    if component not in COMPONENTS:
        warn(f"No changelog path defined for component: {component}")
        return False

    changelog_path = repo_root / COMPONENTS[component].changelog_path

    if dry_run:
        info(f"Would update changelog: {COMPONENTS[component].changelog_path}")
        info("New content:")
        print("\n".join(merge_entries(read_unreleased(changelog_path), body).split("\n")[:10]))
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

    date = datetime.now().strftime("%Y-%m-%d")
    entries = merge_entries(take_unreleased(changelog_path), body)
    _insert_under_unreleased(changelog_path, f"## [{new_version}] - {date}\n\n{entries}\n")
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

    # Cut [Unreleased] only now, after the git calls above, so a failure leaves it intact.
    # Every release says whether self-hosters must act, so "None" is a statement, not a gap.
    upgrade_notes = take_upgrade_notes(changelog_path) or NO_UPGRADE_NOTES
    platform_entry += f"\n{UPGRADE_NOTES_HEADING}\n\n{upgrade_notes}\n"
    handwritten = take_unreleased(changelog_path)
    if handwritten:
        platform_entry += f"\n{handwritten}\n"
    platform_entry += summary

    _insert_under_unreleased(changelog_path, platform_entry)
    success(f"Updated platform changelog: {PLATFORM_CHANGELOG}")
    return True


DOCS_DRAFT_MARKER = "{/* TODO: review and edit this draft */}"
DOCS_COMPONENT_ORDER = ("backend", "frontend", "sdk", "polyphemus")
VERSION_HEADING = re.compile(r"^## \[([^\]]+)\]")


def extract_release_notes(text: str, version: str) -> str:
    """Return the Unreleased notes and the entry for `version`, without older releases.

    The component changelogs put the new version directly below a long hand-written Unreleased
    section. A character cap therefore cuts off the entry the release just generated; selecting by
    heading keeps both parts and leaves every older release out.
    """
    sections: List[Tuple[str, List[str]]] = []
    current_version: Optional[str] = None
    current_lines: List[str] = []

    for line in text.splitlines():
        match = VERSION_HEADING.match(line)
        if match:
            if current_version is not None:
                sections.append((current_version, current_lines))
            current_version = match.group(1).strip()
            current_lines = [line]
        elif current_version is not None:
            current_lines.append(line)

    if current_version is not None:
        sections.append((current_version, current_lines))

    wanted = version.strip().lstrip("v").lower()
    selected = []
    for section_version, lines in sections:
        name = section_version.lstrip("v").lower()
        if name != "unreleased" and name != wanted:
            continue
        body = "\n".join(lines).strip()
        # A bare heading has no release notes for the model to read.
        if body and body != lines[0].strip():
            selected.append(body)
    return "\n\n".join(selected)


def _docs_style_reference(repo_root: Path) -> str:
    """Intro plus one complete released entry from the docs changelog.

    Cutting at the second `## [` heading shows the model a whole entry, including its Highlights
    sections, instead of stopping partway through one.
    """
    docs_changelog = "docs/content/changelog.mdx"
    path = repo_root / docs_changelog
    if not path.exists():
        return ""
    text = path.read_text()
    headings = [match.start() for match in re.finditer(r"(?m)^## \[", text)]
    if len(headings) >= 2:
        return text[: headings[1]].rstrip()
    return text.strip()


def _docs_platform_release_section(component_versions: Dict[str, str]) -> str:
    """The release manifest, written by code instead of being guessed by the model."""
    lines = ["### Platform Release", "", "This release includes the following component versions:"]
    for component in DOCS_COMPONENT_ORDER:
        version = component_versions.get(component)
        if version:
            lines.append(f"- **{format_component_name(component)} {version}**")
    return "\n".join(lines)


def _docs_highlight_headings(component_changelogs: Dict[str, str]) -> List[str]:
    return [
        f"### {format_component_name(component)} Highlights"
        for component in DOCS_COMPONENT_ORDER
        if component_changelogs.get(component, "").strip()
    ]


def _docs_changelog_prompt(
    version: str,
    component_changelogs: Dict[str, str],
    style_reference: str,
    component_versions: Dict[str, str],
) -> str:
    component_sections = []
    for component in DOCS_COMPONENT_ORDER:
        content = component_changelogs.get(component, "").strip()
        if content:
            component_sections.append(
                f"### {format_component_name(component)} changelog\n{content}"
            )

    highlight_headings = "\n".join(_docs_highlight_headings(component_changelogs))
    highlight_instruction = (
        f"Then one section per component, using exactly these headings:\n{highlight_headings}"
        if highlight_headings
        else "Then one `### Component Highlights` section."
    )

    return f"""You are drafting one entry for the Rhesis aggregated docs changelog.

Version: {version}

Use the component changelogs below as the source of truth. Do not invent features, dates, issue
numbers, or breaking changes. If a component changelog says something is a placeholder or TODO,
do not present it as a finished claim.

The caller writes the Platform Release section. Do not repeat it.

Write Markdown/MDX with exactly these sections, in this order:
### Summary
Two to four sentences describing the release as a whole.
### Breaking Changes
Only real breaking changes; omit the section if there are none.
### Featured Capabilities
Group related changes under bold short headings. Prefer user-visible capabilities over internal
refactors.
{highlight_instruction}

Use only the component changelogs that are present. Do not add sections for components that were
not part of this release. Do not add a `## [version]` heading, a date, or a TODO comment.
Return only the body, with no preamble or code fence.

Existing docs changelog style reference:
{style_reference}

Component changelogs:
{chr(10).join(component_sections)}
"""


def generate_docs_changelog_with_llm(
    api_key: str,
    version: str,
    component_changelogs: Dict[str, str],
    repo_root: Path,
    component_versions: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Generate the body of the aggregated docs changelog entry.

    The caller supplies only the components that were released; the Platform Release manifest is
    added here from the versions, not generated by the model.
    """
    if not api_key:
        warn("No Gemini API key; skipping docs changelog draft")
        return None
    if not any(content.strip() for content in component_changelogs.values()):
        warn("No component release notes for the docs changelog draft")
        return None

    versions = component_versions or {}
    prompt = _docs_changelog_prompt(
        version,
        component_changelogs,
        _docs_style_reference(repo_root),
        versions,
    )
    content = call_gemini_api(api_key, prompt)
    if not content:
        warn("No docs changelog draft generated")
        return None

    content = content.strip()
    # Some models include the heading even when told not to; drop it so the caller owns the header.
    if content.startswith("## ["):
        _, separator, rest = content.partition("\n")
        content = rest.lstrip() if separator else ""
    if not content:
        return None

    return f"{_docs_platform_release_section(versions)}\n\n{content}"


def docs_placeholder_entry(component_versions: Dict[str, str]) -> str:
    """A visible draft when the model cannot run, so the docs entry is never silently skipped."""
    return (
        f"{_docs_platform_release_section(component_versions)}\n\n"
        "### Summary\n\n"
        f"{placeholder_entry('docs changelog').strip()}"
    )


def update_docs_changelog(
    new_version: str,
    entry: str,
    repo_root: Path,
    dry_run: bool = False,
) -> bool:
    """Insert a draft entry before the newest released docs section."""
    if not entry.strip():
        warn("Refusing to insert an empty docs changelog entry")
        return False

    docs_changelog = "docs/content/changelog.mdx"
    path = repo_root / docs_changelog
    if not path.exists():
        warn(f"Docs changelog not found: {docs_changelog}")
        return False

    date = datetime.now().strftime("%Y-%m-%d")
    draft_lines = [
        DOCS_DRAFT_MARKER,
        f"## [{new_version}] - {date}",
        "",
        *entry.strip().splitlines(),
        "",
    ]

    if dry_run:
        info(f"Would insert docs changelog entry for v{new_version} in {docs_changelog}")
        return True

    lines = path.read_text().splitlines()
    first_released = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("## [") and not line.startswith("## [Unreleased]")
        ),
        None,
    )

    if first_released is None:
        new_lines = [*lines, "", *draft_lines]
    else:
        new_lines = [*lines[:first_released], *draft_lines, *lines[first_released:]]

    path.write_text("\n".join(new_lines).rstrip() + "\n")
    success(f"Updated docs changelog: {docs_changelog}")
    return True

