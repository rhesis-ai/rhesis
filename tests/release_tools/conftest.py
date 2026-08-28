"""Put `.github` on sys.path so `release_tools` imports the way `python3 .github/release` does."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / ".github"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
