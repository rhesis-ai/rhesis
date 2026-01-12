"""
Changelog generation for the Rhesis release tool.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import COMPONENTS, PLATFORM_CHANGELOG, format_component_name
from .git_ops import get_commits_since_tag, get_last_tag
from .utils import call_gemini_api, info, success, warn


def generate_changelog_with_llm(api_key: str, component: str, version: str, 
                               commits: List[Dict[str, str]], last_tag: Optional[str]) -> Optional[str]:
    """Generate changelog using Gemini API"""
    if not api_key:
        warn(f"No Gemini API key available. Skipping LLM changelog generation for {component}")
        return None
    
    commits_text = "\n".join([
        f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})"
        for commit in commits
    ])
    
    prompt = f"""Generate a professional changelog entry for version {version} of the {format_component_name(component)} component in a software project.

Based on these commits since the last release{f' ({last_tag})' if last_tag else ''}:

{commits_text}

Please format the output as a markdown changelog section following the 'Keep a Changelog' format. Include appropriate categories like Added, Changed, Fixed, Removed, etc. Be concise but informative. Focus on user-facing changes and improvements.

Do NOT include the version header line (## [version] - date) - only return the content sections (### Added, ### Changed, etc.). 

Return ONLY the changelog content without any additional text or explanations."""

    return call_gemini_api(api_key, prompt, max_tokens=2048)


def generate_component_summary_with_llm(api_key: str, component: str, version: str, 
                                       commits: List[Dict[str, str]], last_tag: Optional[str]) -> Optional[str]:
    """Generate a brief component summary for platform changelog using Gemini API"""
    if not api_key:
        return None
    
    commits_text = "\n".join([
        f"- {commit['message']} ({commit['hash'][:8]}, {commit['author']})"
        for commit in commits
    ])
    
    prompt = f"""Generate a brief bullet point summary of changes for version {version} of the {format_component_name(component)} component.

Based on these commits since the last release{f' ({last_tag})' if last_tag else ''}:

{commits_text}

Focus on the most important user-facing changes and improvements. Format as 2-4 bullet points using simple dashes (-). Keep each point concise and informative.

Return ONLY the bullet points without any additional text or explanations."""

    return call_gemini_api(api_key, prompt, max_tokens=512)


def generate_fallback_changelog(version: str, commits: List[Dict[str, str]]) -> str:
    """Generate fallback changelog from commits"""
    date = datetime.now().strftime("%Y-%m-%d")
    
    changelog = f"## [{version}] - {date}\n\n### Changed\n\n"
    
    if commits:
        for commit in commits:
            changelog += f"- {commit['message']}\n"
    else:
        changelog += "- Initial release\n"
    
    changelog += "\n"
    return changelog


def update_component_changelog(component: str, new_version: str, changelog_content: str, 
                             repo_root: Path, dry_run: bool = False) -> bool:
    """Update component changelog"""
    if component not in COMPONENTS:
        warn(f"No changelog path defined for component: {component}")
        return False
    
    changelog_path = repo_root / COMPONENTS[component].changelog_path
    
    if dry_run:
        info(f"Would update changelog: {COMPONENTS[component].changelog_path}")
        info("New content:")
        print("\n".join(changelog_content.split('\n')[:10]))
        return True
    
    # Create changelog if it doesn't exist
    if not changelog_path.exists():
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        
        header = f"""# {format_component_name(component)} Changelog

All notable changes to the {component} component will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

"""
        changelog_path.write_text(header)
    
    # Insert new changelog entry after [Unreleased] section
    content = changelog_path.read_text()
    lines = content.split('\n')
    
    new_lines = []
    inserted = False
    
    for line in lines:
        new_lines.append(line)
        if line.strip() == "## [Unreleased]" and not inserted:
            new_lines.append("")
            new_lines.extend(changelog_content.split('\n'))
            inserted = True
    
    changelog_path.write_text('\n'.join(new_lines))
    success(f"Updated changelog: {COMPONENTS[component].changelog_path}")
    return True


def update_platform_changelog(component_versions: Dict[str, str], new_version: str, 
                            api_key: str, repo_root: Path, dry_run: bool = False) -> bool:
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
            
            # Try to generate LLM summary
            summary = None
            if api_key and commits:
                summary = generate_component_summary_with_llm(
                    api_key, component, version, commits, last_tag
                )
            
            if summary:
                platform_entry += f"{summary}\n\n"
            elif commits:
                # Fallback to first few commit messages
                commit_msgs = [commit['message'] for commit in commits[:3]]
                platform_entry += f"Key changes include: {', '.join(commit_msgs[:2])}{'...' if len(commits) > 2 else ''}.\n\n"
            else:
                platform_entry += "Initial release or no significant changes.\n\n"
    
    platform_entry += "See individual component changelogs for detailed changes:\n"
    
    for component in component_versions:
        if component != "platform" and component in COMPONENTS:
            changelog_path_rel = COMPONENTS[component].changelog_path
            platform_entry += f"- [{format_component_name(component)} Changelog]({changelog_path_rel})\n"
    
    platform_entry += "\n"
    
    # Insert into changelog
    content = changelog_path.read_text()
    lines = content.split('\n')
    
    new_lines = []
    inserted = False
    
    for line in lines:
        new_lines.append(line)
        if line.strip() == "## [Unreleased]" and not inserted:
            new_lines.append("")
            new_lines.extend(platform_entry.split('\n'))
            inserted = True
    
    changelog_path.write_text('\n'.join(new_lines))
    success(f"Updated platform changelog: {PLATFORM_CHANGELOG}")
    return True 