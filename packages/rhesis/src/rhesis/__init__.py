# Rhesis - Testing and validation platform for LLM applications
#
# This is the base namespace package for Rhesis.
# For the full SDK functionality, install rhesis-sdk:
#
#   pip install rhesis-sdk
#
# Documentation: https://docs.rhesis.ai

from importlib.metadata import PackageNotFoundError, version

# Namespace package declaration - allows multiple packages to contribute to rhesis.*
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

try:
    __version__ = version("rhesis")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for development

__all__ = ["__version__"]
