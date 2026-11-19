"""The deploy files a release pins to the platform version.

A release tag's docker-compose.ghcr.yml and Helm chart must name that release's images.
When they didn't (`:latest`, an unchanging chart appVersion), a checkout of `main` ran
newer config against the last release's images, and the frontend wouldn't start.
"""

import re
import shutil

import pytest
from release_tools.config import PLATFORM_PINNED_FILES, PLATFORM_VERSION_FILE
from release_tools.version import pin_platform_files

pytestmark = pytest.mark.unit


def test_pinned_files_are_on_the_current_platform_version(repo_root):
    """Every pin in the repo names the version in VERSION; a release keeps them together."""
    version = (repo_root / PLATFORM_VERSION_FILE).read_text().strip()
    for rel_path, pattern in PLATFORM_PINNED_FILES.items():
        text = (repo_root / rel_path).read_text()
        found = {m.group(0) for m in re.finditer(pattern, text)}
        assert found, f"{rel_path}: pattern matches nothing"
        for match in found:
            assert version in match, f"{rel_path}: {match!r} is not on {version}"


def test_pinning_rewrites_every_occurrence(repo_root, tmp_path):
    for rel_path in PLATFORM_PINNED_FILES:
        (tmp_path / rel_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(repo_root / rel_path, tmp_path / rel_path)

    assert pin_platform_files("9.8.7", tmp_path)

    compose = (tmp_path / "docker-compose.ghcr.yml").read_text()
    assert compose.count("${RHESIS_VERSION:-9.8.7}") == 4

    chart = (tmp_path / "charts/rhesis/Chart.yaml").read_text()
    assert re.search(r"(?m)^version: 9\.8\.7$", chart)
    assert re.search(r'(?m)^appVersion: "9\.8\.7"$', chart)
    # Subchart dependency versions are indented and must be left alone.
    assert '    version: "~2.x"' in chart


def test_pinning_fails_when_a_file_has_no_version(tmp_path):
    for rel_path in PLATFORM_PINNED_FILES:
        (tmp_path / rel_path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel_path).write_text("nothing to pin here\n")

    assert not pin_platform_files("9.8.7", tmp_path)
