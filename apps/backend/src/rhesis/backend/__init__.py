"""Rhesis backend package.

This module is shared between the MIT-licensed core (this directory) and
the optional Enterprise Edition package (``ee/backend/src/rhesis/backend/``).
The ``pkgutil.extend_path`` call is what allows ``rhesis.backend.ee`` to
exist as a sibling subpackage when the ``rhesis-backend-ee`` extra is
installed; without it, the EE source tree is invisible to the import
machinery because Python treats this file as a regular ``__init__``.
"""

from importlib.metadata import PackageNotFoundError, version

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

try:
    __version__ = version("rhesis-backend")
except PackageNotFoundError:
    __version__ = "0.1.0"
