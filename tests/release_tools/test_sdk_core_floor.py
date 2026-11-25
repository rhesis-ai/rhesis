"""The SDK's requirement on the core `rhesis` package, raised by each SDK release.

Core is built with the SDK's version and published just before it, so an SDK that imports a new
core module must not install next to an older core.
"""

import re
import shutil
import tomllib

import pytest
from release_tools import version
from release_tools.config import SDK_CORE_REQUIREMENT
from release_tools.version import pin_sdk_core_floor

pytestmark = pytest.mark.unit


def _floor(text: str) -> str:
    _, pattern = SDK_CORE_REQUIREMENT
    matches = re.findall(r'"rhesis\[telemetry\]>=([^"]+)"', text)
    assert re.search(pattern, text) and len(matches) == 1
    return matches[0]


def test_the_floor_is_the_current_sdk_version(repo_root):
    rel_path, _ = SDK_CORE_REQUIREMENT
    text = (repo_root / rel_path).read_text()
    # Read directly: get_current_version shells out to uv, which CI doesn't install here.
    assert _floor(text) == tomllib.loads(text)["project"]["version"]


def test_an_sdk_release_raises_the_floor(repo_root, tmp_path, monkeypatch):
    rel_path, _ = SDK_CORE_REQUIREMENT
    (tmp_path / "sdk").mkdir()
    shutil.copy(repo_root / rel_path, tmp_path / rel_path)
    # `uv version` needs the whole workspace; the floor is what's under test here.
    monkeypatch.setattr(version, "_update_pyproject_version", lambda path, new: True)

    assert version.update_version_file("sdk", "9.8.7", tmp_path)

    assert _floor((tmp_path / rel_path).read_text()) == "9.8.7"


def test_other_components_leave_the_floor_alone(repo_root, tmp_path, monkeypatch):
    rel_path, _ = SDK_CORE_REQUIREMENT
    (tmp_path / "sdk").mkdir()
    shutil.copy(repo_root / rel_path, tmp_path / rel_path)
    before = (tmp_path / rel_path).read_text()
    monkeypatch.setattr(version, "_update_pyproject_version", lambda path, new: True)

    assert version.update_version_file("polyphemus", "9.8.7", tmp_path)

    assert (tmp_path / rel_path).read_text() == before


def test_pinning_fails_without_the_requirement(tmp_path):
    rel_path, _ = SDK_CORE_REQUIREMENT
    (tmp_path / "sdk").mkdir()
    (tmp_path / rel_path).write_text('[project]\nname = "rhesis-sdk"\n')

    assert not pin_sdk_core_floor("9.8.7", tmp_path)
