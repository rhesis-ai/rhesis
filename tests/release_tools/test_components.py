"""Tests for which components the release tool releases, and how they get their version.

The backend and the frontend ship with the platform: they take its version and are covered by its
tag. Everything here pins that down, plus the guard that would have caught the `chatbot` entry
pointing at a version file that had not existed for a long time.
"""

import json

import pytest
from release_tools.cli import bumpable_components, reject_platform_followers
from release_tools.config import COMPONENTS, follows_platform, platform_followers
from release_tools.git_ops import get_last_tag
from release_tools.processor import ReleaseProcessor
from release_tools.version import _update_package_version

pytestmark = pytest.mark.unit


def test_every_component_version_file_exists(repo_root):
    """`chatbot` pointed at a deleted requirements.txt and was silently skipped every release."""
    missing = [
        f"{component} -> {config.config_file}"
        for component, config in COMPONENTS.items()
        if not (repo_root / config.config_file).exists()
    ]

    assert not missing, f"COMPONENTS entries whose version file does not exist: {missing}"


def test_every_component_changelog_exists(repo_root):
    """A component with no changelog cannot be released -- publish reads its notes from one."""
    missing = [
        f"{component} -> {config.changelog_path}"
        for component, config in COMPONENTS.items()
        if not (repo_root / config.changelog_path).exists()
    ]

    assert not missing, f"COMPONENTS entries whose changelog does not exist: {missing}"


def test_backend_and_frontend_follow_the_platform():
    assert platform_followers() == ["backend", "frontend"]
    assert follows_platform("backend")
    assert follows_platform("frontend")
    assert not follows_platform("sdk")
    assert not follows_platform("platform")


def test_followers_are_not_bumpable():
    assert "platform" in bumpable_components()
    assert "sdk" in bumpable_components()
    assert "backend" not in bumpable_components()
    assert "frontend" not in bumpable_components()


def test_a_bump_config_naming_a_follower_is_rejected(capsys):
    """release_config.json lives on main, so a stale one can still name backend."""
    assert not reject_platform_followers({"platform": "minor", "backend": "minor"})

    out = capsys.readouterr().out
    assert "backend" in out
    assert "platform" in out


def test_a_bump_config_without_followers_is_accepted():
    assert reject_platform_followers({"platform": "minor", "sdk": "patch"})


def test_a_follower_reads_its_last_tag_from_the_platform(monkeypatch):
    """Its own `backend-v*` tags stopped moving, so matching them would span several releases."""
    patterns = []

    def fake_run(cmd, **kwargs):
        patterns.append(cmd[-1])
        raise AssertionError("stop after capturing the pattern")

    monkeypatch.setattr("release_tools.git_ops.subprocess.run", fake_run)

    for component in ("backend", "frontend", "platform", "sdk"):
        with pytest.raises(AssertionError):
            get_last_tag(component)

    assert patterns == ["v*", "v*", "v*", "sdk-v*"]


def test_a_platform_bump_gives_its_followers_the_platform_version(repo_root):
    processor = ReleaseProcessor(repo_root, dry_run=True, gemini_api_key="", no_branch=True)

    processor.component_bumps = {"platform": "minor"}
    processor.process_releases()

    platform_version = processor.component_versions["platform"]
    assert processor.component_versions["backend"] == platform_version
    assert processor.component_versions["frontend"] == platform_version

    # Canonical order, so the platform changelog's sections don't reshuffle between releases
    assert list(processor.component_versions) == ["platform", "backend", "frontend"]


def test_followers_stay_out_of_the_release_pr_title(repo_root):
    """They carry the platform's number, so listing them repeats it once per component."""
    processor = ReleaseProcessor(repo_root, dry_run=True, gemini_api_key="", no_branch=True)

    processor.component_bumps = {"platform": "minor"}
    processor.process_releases()

    with open("/tmp/version_changes.json") as f:
        version_changes = json.load(f)

    assert list(version_changes) == ["platform"]


def test_a_platform_bump_does_not_touch_independent_components(repo_root):
    processor = ReleaseProcessor(repo_root, dry_run=True, gemini_api_key="", no_branch=True)

    processor.component_bumps = {"platform": "minor"}
    processor.process_releases()

    assert "sdk" not in processor.component_versions
    assert "polyphemus" not in processor.component_versions


def test_package_version_is_written_with_a_trailing_newline(tmp_path):
    """Without it the frontend linter rewrites package.json right after the release tool does."""
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"name": "frontend", "version": "0.14.0"}, indent=2) + "\n")

    assert _update_package_version(path, "0.15.0", tmp_path)

    assert json.loads(path.read_text())["version"] == "0.15.0"
    assert path.read_text().endswith("}\n")


def _write_lock(path, version, extra=None):
    """A minimal lockfileVersion 3 file, formatted the way npm writes one."""
    data = {
        "name": "frontend",
        "version": version,
        "lockfileVersion": 3,
        "packages": {"": {"name": "frontend", "version": version}},
    }
    if extra:
        data["packages"].update(extra)
    path.write_text(json.dumps(data, indent=2) + "\n")


def test_package_lock_version_is_bumped_alongside_package_json(tmp_path):
    """A bump that skips the lockfile leaves it a release behind, per the 0.15.0 release."""
    package_json = tmp_path / "package.json"
    package_json.write_text(json.dumps({"name": "frontend", "version": "0.14.0"}, indent=2) + "\n")
    lock = tmp_path / "package-lock.json"
    _write_lock(lock, "0.14.0")

    assert _update_package_version(package_json, "0.15.0", tmp_path)

    data = json.loads(lock.read_text())
    # lockfileVersion 2 and 3 carry the root version twice, and npm rewrites both.
    assert data["version"] == "0.15.0"
    assert data["packages"][""]["version"] == "0.15.0"


def test_package_lock_rewrite_touches_only_the_version_fields(tmp_path):
    """Any formatting drift here lands as churn in whichever PR next runs npm install."""
    package_json = tmp_path / "package.json"
    package_json.write_text(json.dumps({"name": "frontend", "version": "0.14.0"}, indent=2) + "\n")
    lock = tmp_path / "package-lock.json"
    _write_lock(lock, "0.14.0", extra={"node_modules/react": {"version": "19.2.1"}})
    original = lock.read_text()

    assert _update_package_version(package_json, "0.15.0", tmp_path)

    assert lock.read_text() == original.replace('"0.14.0"', '"0.15.0"')


def test_package_version_succeeds_when_there_is_no_lockfile(tmp_path):
    """Only the frontend ships a package-lock.json, so its absence is not a failure."""
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"name": "docs", "version": "0.14.0"}, indent=2) + "\n")

    assert _update_package_version(path, "0.15.0", tmp_path)
    assert not (tmp_path / "package-lock.json").exists()


def test_frontend_lockfile_version_matches_package_json(repo_root):
    """The real files: this drifted once and only showed up as noise in an unrelated PR."""
    package_json = repo_root / COMPONENTS["frontend"].config_file
    lock = package_json.parent / "package-lock.json"

    expected = json.loads(package_json.read_text())["version"]
    data = json.loads(lock.read_text())

    assert data["version"] == expected
    assert data["packages"][""]["version"] == expected
