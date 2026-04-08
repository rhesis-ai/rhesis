# Rhesis - Testing and validation platform for LLM applications
#
# Lightweight foundation package with telemetry support.
#   pip install rhesis                → base (pydantic, requests)
#   pip install rhesis[telemetry]     → + OpenTelemetry trace export
#   pip install rhesis[sdk]           → + full SDK (rhesis-sdk)
#   pip install rhesis[all]           → everything
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
