# Rhesis - Testing and validation platform for LLM applications
#
# This is the umbrella package for Rhesis. It automatically includes rhesis-sdk.
#
# Usage:
#   pip install rhesis           # Core SDK
#   pip install rhesis[penelope] # Multi-turn testing agent
#   pip install rhesis[all]      # Everything
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
