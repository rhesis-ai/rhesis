"""Tests for the docs changelog draft added to the release tool."""

from pathlib import Path

import pytest
from release_tools.changelog import (
    DOCS_DRAFT_MARKER,
    UNRELEASED_MARKER,
    _docs_style_reference,
    docs_placeholder_entry,
    extract_release_notes,
    generate_docs_changelog_with_llm,
    update_docs_changelog,
)
from release_tools.config import COMPONENTS

pytestmark = pytest.mark.unit


def _docs_repo(tmp_path: Path, body: str = "# Rhesis Changelog\n\nIntro.\n\n") -> Path:
    path = tmp_path / "docs" / "content"
    path.mkdir(parents=True, exist_ok=True)
    changelog = path / "changelog.mdx"
    changelog.write_text(body)
    return changelog


def test_extract_release_notes_keeps_long_unreleased_and_new_version():
    text = (
        f"# Backend Changelog\n\n{UNRELEASED_MARKER}\n\n"
        + "Long hand-written note. " * 300
        + "\n\n## [0.22.0] - 2026-11-19\n\n### Added\n\n- New thing\n\n"
        "## [0.21.2] - 2026-11-17\n\n### Added\n\n- Old thing\n"
    )

    notes = extract_release_notes(text, "0.22.0")

    assert "Long hand-written note." in notes
    assert "New thing" in notes
    assert "Old thing" not in notes
    # The old 4000-character cap cut before the new version entry.
    assert len(notes) > 4000


def test_extract_release_notes_does_not_fall_back_to_an_old_release():
    text = (
        f"# Backend Changelog\n\n{UNRELEASED_MARKER}\n\n"
        "## [0.21.2] - 2026-11-17\n\n### Added\n\n- Old thing\n"
    )

    assert extract_release_notes(text, "0.22.0") == ""


def test_docs_style_reference_ends_at_the_second_version_heading(tmp_path):
    text = (
        "# Rhesis Changelog\n\nIntro.\n\n"
        "## [0.22.0] - 2026-11-19\n\n### Summary\n\nFull first entry.\n\n"
        "### Backend Highlights\n- Complete highlight\n\n"
        "## [0.21.2] - 2026-11-17\n\n### Summary\n\nOlder entry.\n"
    )
    (tmp_path / "docs" / "content").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "content" / "changelog.mdx").write_text(text)

    style = _docs_style_reference(tmp_path)

    assert "Full first entry." in style
    assert "Complete highlight" in style
    assert "Older entry." not in style


def test_docs_prompt_only_contains_released_components(monkeypatch, tmp_path):
    from release_tools import changelog as changelog_mod

    captured = {}

    def fake_call(api_key, prompt, max_tokens=None):
        captured["prompt"] = prompt
        return "### Summary\n\nA focused release.\n"

    monkeypatch.setattr(changelog_mod, "call_gemini_api", fake_call)
    _docs_repo(tmp_path)

    body = generate_docs_changelog_with_llm(
        "key",
        "0.23.0",
        {
            "backend": "Backend added rate limits",
            "sdk": "SDK added retries",
        },
        tmp_path,
        {"backend": "0.23.0", "sdk": "0.23.0"},
    )

    assert body.startswith("### Platform Release")
    assert "- **Backend 0.23.0**" in body
    assert "- **SDK 0.23.0**" in body
    prompt = captured["prompt"]
    assert "Backend added rate limits" in prompt
    assert "SDK added retries" in prompt
    assert "### Backend Highlights" in prompt
    assert "### SDK Highlights" in prompt
    assert "Frontend Highlights" not in prompt
    assert "Polyphemus Highlights" not in prompt
    assert "Commits since" not in prompt


def test_docs_placeholder_is_visible_and_has_the_manifest():
    entry = docs_placeholder_entry({"backend": "0.23.0", "frontend": "0.23.0"})

    assert "### Platform Release" in entry
    assert "- **Backend 0.23.0**" in entry
    assert "- **Frontend 0.23.0**" in entry
    assert "TODO: changelog generation failed for docs changelog" in entry


def test_docs_uses_a_jsx_comment_for_mdx(tmp_path):
    changelog = _docs_repo(
        tmp_path,
        "# Rhesis Changelog\n\n## [0.22.0] - 2026-11-19\n\n- Old release\n",
    )

    assert update_docs_changelog("0.23.0", "### Summary\n\nNew\n", tmp_path)

    result = changelog.read_text()
    assert DOCS_DRAFT_MARKER in result
    assert "{/* TODO: review and edit this draft */}" in result
    assert "<!-- TODO" not in result
    assert result.index("## [0.23.0]") < result.index("## [0.22.0]")


def test_processor_only_reads_components_in_this_release(tmp_path, monkeypatch):
    from release_tools import processor as processor_mod

    _docs_repo(
        tmp_path,
        "# Rhesis Changelog\n\n## [0.22.0] - 2026-11-19\n\n- Old release\n",
    )
    for component in ("backend", "frontend", "sdk", "polyphemus"):
        config = COMPONENTS[component]
        path = tmp_path / config.changelog_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Changelog\n\n{UNRELEASED_MARKER}\n\n### Added\n\n- {component} note\n\n"
            f"## [0.23.0] - 2026-11-27\n\n### Added\n\n- {component} release\n"
        )

    captured = {}

    def fake_generate(api_key, version, changelogs, repo_root, component_versions=None):
        captured["changelogs"] = changelogs
        captured["versions"] = component_versions
        return "### Summary\n\nA focused release.\n"

    monkeypatch.setattr(processor_mod, "generate_docs_changelog_with_llm", fake_generate)
    processor = processor_mod.ReleaseProcessor(tmp_path)
    processor.component_versions = {
        "platform": "0.23.0",
        "backend": "0.23.0",
        "frontend": "0.23.0",
        "sdk": "0.23.0",
    }

    assert processor._update_docs_changelog("0.23.0")
    assert set(captured["changelogs"]) == {"backend", "frontend", "sdk"}
    assert set(captured["versions"]) == {"backend", "frontend", "sdk"}
    # Polyphemus was not released and must not have its August notes fed to the model.
    assert "polyphemus" not in captured["changelogs"]
    assert "polyphemus" not in captured["versions"]


def test_processor_dry_run_does_not_call_the_model(tmp_path, monkeypatch):
    from release_tools import processor as processor_mod

    def fail(*args, **kwargs):
        raise AssertionError("dry run must not call Gemini")

    monkeypatch.setattr(processor_mod, "generate_docs_changelog_with_llm", fail)
    processor = processor_mod.ReleaseProcessor(tmp_path, dry_run=True, gemini_api_key="key")
    processor.component_versions = {"platform": "0.23.0", "backend": "0.23.0"}

    assert processor._update_docs_changelog("0.23.0")
