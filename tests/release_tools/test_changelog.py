"""Tests for the release tool's changelog generation.

No network: the LLM call itself is out of scope here, only the budget it is given and what happens
to the file when it comes back empty.
"""

import re
from pathlib import Path

import pytest
from release_tools.changelog import (
    NO_UPGRADE_NOTES,
    UNRELEASED_MARKER,
    UPGRADE_NOTES_HEADING,
    _insert_under_unreleased,
    placeholder_entry,
)
from release_tools.config import COMPONENTS
from release_tools.utils import LLM_MAX_OUTPUT_TOKENS

pytestmark = pytest.mark.unit

VERSION_SECTION = re.compile(
    r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\n(.*?)(?=\n## \[|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Deliberately pessimistic: Gemini averages ~4.5 chars/token on our changelog prose, so assuming 3
# overestimates the token cost of the longest section rather than flattering the budget.
MIN_CHARS_PER_TOKEN = 3

# The model spends this many output tokens reasoning before it writes anything, measured against
# real release commit ranges. It counts against the same budget as the visible text.
OBSERVED_REASONING_TOKENS = 4_000


def _longest_section(repo_root: Path) -> tuple[str, int]:
    """The biggest changelog section ever shipped, as (label, chars)."""
    biggest = ("", 0)
    for component in COMPONENTS:
        path = repo_root / COMPONENTS[component].changelog_path
        if not path.exists():
            continue
        for version, _date, body in VERSION_SECTION.findall(path.read_text()):
            if len(body) > biggest[1]:
                biggest = (f"{component} v{version}", len(body))
    return biggest


def test_budget_clears_the_largest_changelog_we_have_shipped(repo_root):
    """Trips if a release outgrows the budget, which is how the truncation bug shipped twice."""
    label, chars = _longest_section(repo_root)
    assert chars, "found no changelog sections to measure"

    needed = chars / MIN_CHARS_PER_TOKEN + OBSERVED_REASONING_TOKENS

    assert LLM_MAX_OUTPUT_TOKENS > needed, (
        f"{label} is {chars} chars (~{chars / MIN_CHARS_PER_TOKEN:.0f} tokens); with "
        f"~{OBSERVED_REASONING_TOKENS} reasoning tokens that needs ~{needed:.0f}, over the "
        f"{LLM_MAX_OUTPUT_TOKENS} budget. Raise LLM_MAX_OUTPUT_TOKENS."
    )


def test_placeholder_names_the_component_and_invents_nothing():
    entry = placeholder_entry("backend")

    assert "TODO" in entry
    assert "backend" in entry
    # The old fallback pasted commit subjects here, which read as a real changelog
    assert "(#" not in entry


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(body)
    return path


def test_insert_keeps_hand_written_unreleased_entries_above_the_new_section(tmp_path):
    path = _write(
        tmp_path,
        f"# Changelog\n\n{UNRELEASED_MARKER}\n\n### Added\n\n- A hand-written note\n\n"
        "## [0.13.0] - 2026-08-20\n\n- Older\n",
    )

    _insert_under_unreleased(path, "## [0.14.0] - 2026-08-27\n\n- Fresh\n")

    result = path.read_text()
    assert result.index("hand-written note") < result.index("## [0.14.0]")
    assert result.index("## [0.14.0]") < result.index("## [0.13.0]")


def test_insert_works_when_unreleased_is_empty(tmp_path):
    path = _write(
        tmp_path,
        f"# Changelog\n\n{UNRELEASED_MARKER}\n\n## [0.13.0] - 2026-08-20\n\n- Older\n",
    )

    _insert_under_unreleased(path, "## [0.14.0] - 2026-08-27\n\n- Fresh\n")

    result = path.read_text()
    assert result.index(UNRELEASED_MARKER) < result.index("## [0.14.0]")
    assert result.index("## [0.14.0]") < result.index("## [0.13.0]")


def test_insert_appends_when_there_is_no_released_version_yet(tmp_path):
    path = _write(tmp_path, f"# Changelog\n\n{UNRELEASED_MARKER}\n")

    _insert_under_unreleased(path, "## [0.1.0] - 2026-08-27\n\n- First\n")

    assert "## [0.1.0]" in path.read_text()


def test_insert_refuses_a_changelog_with_no_unreleased_heading(tmp_path):
    """Previously a silent no-op that still reported success, so the entry vanished."""
    path = _write(tmp_path, "# Changelog\n\n## [0.13.0] - 2026-08-20\n\n- Older\n")

    with pytest.raises(ValueError, match="Unreleased"):
        _insert_under_unreleased(path, "## [0.14.0] - 2026-08-27\n\n- Fresh\n")


def test_platform_summary_falls_back_to_a_placeholder_not_commit_subjects(tmp_path, monkeypatch):
    """Reproduces the v0.13.0 / v0.14.0 failure.

    The LLM returns nothing, and the release PR must say so rather than present
    `Key changes include: <subject>, <subject>....` as if it were a real summary.
    """
    from release_tools import changelog as changelog_mod

    path = _write(tmp_path, f"# Changelog\n\n{UNRELEASED_MARKER}\n\n## [0.13.0] - 2026-08-20\n")

    monkeypatch.setattr(changelog_mod, "PLATFORM_CHANGELOG", "CHANGELOG.md")
    monkeypatch.setattr(changelog_mod, "get_last_tag", lambda component: "backend-v0.13.0")
    monkeypatch.setattr(
        changelog_mod,
        "get_commits_since_tag",
        lambda component, tag: [
            {"hash": "abc1234", "author": "A", "message": "feat: a thing (#42)"}
        ],
    )
    # The failure mode under test: the model produced nothing usable
    monkeypatch.setattr(changelog_mod, "call_gemini_api", lambda *a, **k: None)

    changelog_mod.update_platform_changelog(
        {"platform": "0.14.0", "backend": "0.14.0"}, "0.14.0", "fake-key", tmp_path
    )

    result = path.read_text()
    assert "TODO" in result
    assert "Key changes include" not in result
    assert "...." not in result
    assert "(#42)" not in result


def _release_platform(tmp_path, monkeypatch, changelog: str) -> str:
    """Write CHANGELOG.md, cut a platform release with no commits, and return the new file."""
    from release_tools import changelog as changelog_mod

    path = _write(tmp_path, changelog)
    monkeypatch.setattr(changelog_mod, "PLATFORM_CHANGELOG", "CHANGELOG.md")
    monkeypatch.setattr(changelog_mod, "get_last_tag", lambda component: None)
    monkeypatch.setattr(changelog_mod, "get_commits_since_tag", lambda component, tag: [])

    changelog_mod.update_platform_changelog(
        {"platform": "0.14.0", "backend": "0.14.0"}, "0.14.0", "", tmp_path
    )
    return path.read_text()


def test_release_moves_upgrade_notes_out_of_unreleased(tmp_path, monkeypatch):
    from release_tools.publish import get_changelog_content

    result = _release_platform(
        tmp_path,
        monkeypatch,
        f"# Changelog\n\n{UNRELEASED_MARKER}\n\n{UPGRADE_NOTES_HEADING}\n\n"
        "1. Add the new redirect URI.\n\n### Removed\n\n- A hand-written note\n\n"
        "## [0.13.0] - 2026-08-20\n\n- Older\n",
    )

    unreleased, released = result.split("## [0.14.0]")
    assert "redirect URI" not in unreleased
    assert "hand-written note" in unreleased
    assert "redirect URI" in released.split("## [0.13.0]")[0]
    # The GitHub release body is cut from this same section
    notes = get_changelog_content(tmp_path / "CHANGELOG.md")
    assert f"{UPGRADE_NOTES_HEADING}\n\n1. Add the new redirect URI." in notes


def test_release_without_upgrade_notes_says_none(tmp_path, monkeypatch):
    result = _release_platform(
        tmp_path,
        monkeypatch,
        f"# Changelog\n\n{UNRELEASED_MARKER}\n\n## [0.13.0] - 2026-08-20\n\n- Older\n",
    )

    released = result.split("## [0.14.0]")[1].split("## [0.13.0]")[0]
    assert f"{UPGRADE_NOTES_HEADING}\n\n{NO_UPGRADE_NOTES}" in released


def test_platform_release_that_fails_leaves_the_notes_in_place(tmp_path, monkeypatch):
    from release_tools import changelog as changelog_mod

    original = (
        f"# Changelog\n\n{UNRELEASED_MARKER}\n\n{UPGRADE_NOTES_HEADING}\n\n1. A step.\n\n"
        "## [0.13.0] - 2026-08-20\n"
    )
    path = _write(tmp_path, original)
    monkeypatch.setattr(changelog_mod, "PLATFORM_CHANGELOG", "CHANGELOG.md")
    monkeypatch.setattr(changelog_mod, "get_last_tag", lambda component: None)

    def git_fails(component, tag):
        raise RuntimeError("git failed")

    monkeypatch.setattr(changelog_mod, "get_commits_since_tag", git_fails)

    with pytest.raises(RuntimeError):
        changelog_mod.update_platform_changelog(
            {"platform": "0.14.0", "backend": "0.14.0"}, "0.14.0", "", tmp_path
        )

    assert path.read_text() == original
