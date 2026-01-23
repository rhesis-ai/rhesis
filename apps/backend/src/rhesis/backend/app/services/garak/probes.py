"""
Garak probe enumeration and extraction service.

This module handles the discovery and extraction of Garak probes
for import into Rhesis as test sets.
"""

import importlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rhesis.backend.logging.rhesis_logger import logger


@dataclass
class GarakProbeInfo:
    """Information about a single Garak probe class."""

    module_name: str
    class_name: str
    full_name: str
    description: str
    tags: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    prompt_count: int = 0
    detector: Optional[str] = None


@dataclass
class GarakModuleInfo:
    """Information about a Garak probe module."""

    name: str
    description: str
    probe_classes: List[str] = field(default_factory=list)
    probe_count: int = 0
    total_prompt_count: int = 0
    tags: List[str] = field(default_factory=list)
    default_detector: Optional[str] = None


class GarakProbeService:
    """Service for enumerating and extracting Garak probes."""

    # Known probe modules to enumerate
    KNOWN_PROBE_MODULES = [
        "dan",
        "encoding",
        "promptinject",
        "continuation",
        "misleading",
        "lmrc",
        "realtoxicityprompts",
        "malwaregen",
        "packagehallucination",
        "gcg",
        "knownbadsignatures",
        "suffix",
        "tap",
        "xss",
        "snowball",
        "donotanswer",
        "glitch",
        "goodside",
        "leakreplay",
        "base64",
    ]

    def __init__(self):
        self._probe_cache: Dict[str, GarakModuleInfo] = {}
        self._garak_version: Optional[str] = None

    @property
    def garak_version(self) -> str:
        """Get the installed Garak version."""
        if self._garak_version is None:
            try:
                import garak

                self._garak_version = getattr(garak, "__version__", "unknown")
            except ImportError:
                self._garak_version = "not_installed"
        return self._garak_version

    def enumerate_probe_modules(self) -> List[GarakModuleInfo]:
        """
        Enumerate all available Garak probe modules.

        Returns:
            List of GarakModuleInfo with module metadata
        """
        modules = []

        try:
            import garak.probes as probes_pkg

            # Iterate through known probe modules
            for module_name in self.KNOWN_PROBE_MODULES:
                try:
                    module_info = self._get_module_info(module_name)
                    if module_info:
                        modules.append(module_info)
                except Exception as e:
                    logger.warning(f"Failed to enumerate probe module {module_name}: {e}")
                    continue

        except ImportError as e:
            logger.error(f"Garak package not installed: {e}")
            raise RuntimeError("Garak package is not installed") from e

        return modules

    def _get_module_info(self, module_name: str) -> Optional[GarakModuleInfo]:
        """
        Get detailed information about a specific probe module.

        Args:
            module_name: Name of the probe module (e.g., 'dan', 'encoding')

        Returns:
            GarakModuleInfo or None if module not found
        """
        # Check cache first
        if module_name in self._probe_cache:
            return self._probe_cache[module_name]

        try:
            # Import the probe module
            module = importlib.import_module(f"garak.probes.{module_name}")

            # Get module docstring as description
            description = module.__doc__ or f"Garak {module_name} probes"
            description = description.strip().split("\n")[0]  # First line only

            # Find all probe classes in the module
            probe_classes = []
            tags = set()
            total_prompts = 0
            default_detector = None

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if self._is_probe_class(attr, attr_name):
                    probe_classes.append(attr_name)

                    # Try to get probe-level info
                    try:
                        # Get tags from class
                        if hasattr(attr, "tags"):
                            class_tags = attr.tags
                            if isinstance(class_tags, (list, tuple, set)):
                                tags.update(class_tags)

                        # Get default detector
                        if hasattr(attr, "recommended_detector") and not default_detector:
                            default_detector = attr.recommended_detector

                        # Try to count prompts
                        if hasattr(attr, "prompts"):
                            prompts = attr.prompts
                            if isinstance(prompts, (list, tuple)):
                                total_prompts += len(prompts)
                    except Exception:
                        pass

            if not probe_classes:
                return None

            module_info = GarakModuleInfo(
                name=module_name,
                description=description,
                probe_classes=probe_classes,
                probe_count=len(probe_classes),
                total_prompt_count=total_prompts,
                tags=list(tags),
                default_detector=default_detector,
            )

            # Cache the result
            self._probe_cache[module_name] = module_info
            return module_info

        except ImportError as e:
            logger.debug(f"Module garak.probes.{module_name} not found: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error loading probe module {module_name}: {e}")
            return None

    def _is_probe_class(self, obj: Any, name: str) -> bool:
        """Check if an object is a Garak probe class."""
        if not isinstance(obj, type):
            return False

        # Skip private classes
        if name.startswith("_"):
            return False

        # Check if it inherits from a Garak probe base class
        try:
            from garak.probes.base import Probe

            return issubclass(obj, Probe) and obj is not Probe
        except ImportError:
            # Fallback: check for common probe attributes
            return hasattr(obj, "prompts") or hasattr(obj, "probe")

    def get_probe_details(self, module_name: str) -> Optional[GarakModuleInfo]:
        """
        Get detailed information about a probe module.

        Args:
            module_name: Name of the probe module

        Returns:
            GarakModuleInfo with full details
        """
        return self._get_module_info(module_name)

    def extract_probes_from_module(
        self, module_name: str, probe_class_names: Optional[List[str]] = None
    ) -> List[GarakProbeInfo]:
        """
        Extract individual probes from a module.

        Args:
            module_name: Name of the probe module
            probe_class_names: Optional list of specific probe classes to extract.
                              If None, extracts all probes from the module.

        Returns:
            List of GarakProbeInfo with probe details and prompts
        """
        probes = []

        try:
            module = importlib.import_module(f"garak.probes.{module_name}")

            for attr_name in dir(module):
                # Skip if we have a specific list and this isn't in it
                if probe_class_names and attr_name not in probe_class_names:
                    continue

                attr = getattr(module, attr_name)
                if not self._is_probe_class(attr, attr_name):
                    continue

                probe_info = self._extract_probe_info(module_name, attr_name, attr)
                if probe_info:
                    probes.append(probe_info)

        except ImportError as e:
            logger.error(f"Module garak.probes.{module_name} not found: {e}")
        except Exception as e:
            logger.error(f"Error extracting probes from {module_name}: {e}")

        return probes

    def _extract_probe_info(
        self, module_name: str, class_name: str, probe_class: type
    ) -> Optional[GarakProbeInfo]:
        """
        Extract information from a single probe class.

        Args:
            module_name: Name of the probe module
            class_name: Name of the probe class
            probe_class: The probe class itself

        Returns:
            GarakProbeInfo with probe details
        """
        try:
            # Get description from docstring
            description = probe_class.__doc__ or f"{class_name} probe"
            description = description.strip().split("\n")[0]

            # Get tags
            tags = []
            if hasattr(probe_class, "tags"):
                probe_tags = probe_class.tags
                if isinstance(probe_tags, (list, tuple, set)):
                    tags = list(probe_tags)

            # Get prompts - try to instantiate the class to get actual prompts
            prompts = []
            try:
                # Some probe classes can be instantiated without arguments
                instance = probe_class()
                if hasattr(instance, "prompts"):
                    prompts = list(instance.prompts) if instance.prompts else []
            except Exception:
                # Fall back to class-level prompts attribute
                if hasattr(probe_class, "prompts"):
                    class_prompts = probe_class.prompts
                    if isinstance(class_prompts, (list, tuple)):
                        prompts = list(class_prompts)

            # Get detector
            detector = None
            if hasattr(probe_class, "recommended_detector"):
                detector = probe_class.recommended_detector

            return GarakProbeInfo(
                module_name=module_name,
                class_name=class_name,
                full_name=f"{module_name}.{class_name}",
                description=description,
                tags=tags,
                prompts=prompts,
                prompt_count=len(prompts),
                detector=detector,
            )

        except Exception as e:
            logger.warning(f"Error extracting probe info for {module_name}.{class_name}: {e}")
            return None

    def get_all_probes(self) -> Dict[str, List[GarakProbeInfo]]:
        """
        Get all probes from all modules.

        Returns:
            Dictionary mapping module names to lists of GarakProbeInfo
        """
        all_probes = {}

        for module_name in self.KNOWN_PROBE_MODULES:
            probes = self.extract_probes_from_module(module_name)
            if probes:
                all_probes[module_name] = probes

        return all_probes
