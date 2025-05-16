"""
Rhesis backend package.
"""

import os
import tomli

# Find the pyproject.toml file
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_pyproject_path = os.path.join(_root_dir, "pyproject.toml")

# Read version from pyproject.toml
try:
    with open(_pyproject_path, "rb") as f:
        _pyproject_data = tomli.load(f)
    __version__ = _pyproject_data["project"]["version"]
except (FileNotFoundError, KeyError, ImportError):
    # Fallback version if we can't read from pyproject.toml
    __version__ = "0.1.0"
