"""
Rhesis backend package.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rhesis-backend")
except PackageNotFoundError:
    __version__ = "0.1.0"
