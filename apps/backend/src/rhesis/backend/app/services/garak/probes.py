"""
Garak probe enumeration and extraction service.

This module handles the discovery and extraction of Garak probes
for import into Rhesis as test sets.
"""

import ast
import importlib
import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rhesis.backend.logging.rhesis_logger import logger

# Placeholder used for generator.name in extracted prompts
GENERATOR_PLACEHOLDER = "{TARGET_MODEL}"


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
            import garak.probes  # noqa: F401 - verify garak is installed

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
                            detector_value = attr.recommended_detector
                            # Handle both string and list types
                            if isinstance(detector_value, (list, tuple)):
                                default_detector = detector_value[0] if detector_value else None
                            elif isinstance(detector_value, str):
                                default_detector = detector_value

                        # Count prompts by extracting from probe method source
                        probe_prompts = self._extract_prompts_from_probe_method(attr)
                        total_prompts += len(probe_prompts)
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

    def _extract_prompts_from_probe_method(self, probe_class: type) -> List[str]:
        """
        Extract prompts from a probe class.

        Garak probes may set self.prompts in different ways:
        1. As a class attribute
        2. In __init__() (e.g., encoding probes)
        3. In the probe() method (e.g., DAN probes with f-strings)

        This method tries multiple strategies to extract prompts.

        Args:
            probe_class: The probe class to extract prompts from

        Returns:
            List of prompt strings with generator.name replaced by placeholder
        """
        prompts = []

        try:
            # First try: check if class already has prompts attribute
            if hasattr(probe_class, "prompts"):
                class_prompts = probe_class.prompts
                if isinstance(class_prompts, (list, tuple)) and class_prompts:
                    return list(class_prompts)

            # Second try: instantiate the probe to get prompts set in __init__
            try:
                instance = probe_class()
                if hasattr(instance, "prompts") and instance.prompts:
                    return list(instance.prompts)
            except Exception as inst_error:
                logger.debug(f"Could not instantiate {probe_class.__name__}: {inst_error}")

            # Third try: get source code of probe method
            if not hasattr(probe_class, "probe"):
                return prompts

            try:
                source = inspect.getsource(probe_class.probe)
            except (OSError, TypeError):
                return prompts

            # Parse the source to find self.prompts = [...] assignment
            # Use regex to extract the list contents
            # Pattern matches: self.prompts = [ ... ]
            pattern = r"self\.prompts\s*=\s*\["
            match = re.search(pattern, source)
            if not match:
                return prompts

            # Find the matching closing bracket
            start_idx = match.end() - 1  # Position of opening [
            bracket_count = 0
            prompts_str = ""

            for i, char in enumerate(source[start_idx:]):
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        prompts_str = source[start_idx : start_idx + i + 1]
                        break

            if not prompts_str:
                return prompts

            # Create a mock generator class for evaluating f-strings
            class MockGenerator:
                name = GENERATOR_PLACEHOLDER

            generator = MockGenerator()

            # Try to evaluate the prompts list
            # Replace f-string references to generator.name with our placeholder
            try:
                # Use exec to evaluate in proper context
                local_vars: Dict[str, Any] = {"generator": generator}
                exec(f"result = {prompts_str}", {"generator": generator}, local_vars)
                result = local_vars.get("result", [])
                if isinstance(result, (list, tuple)):
                    prompts = [str(p) for p in result]
            except Exception as eval_error:
                # If eval fails, try to count list items using AST
                logger.debug(f"Could not eval prompts, using AST count: {eval_error}")
                try:
                    # Parse just the list literal to count elements
                    tree = ast.parse(prompts_str, mode="eval")
                    if isinstance(tree.body, ast.List):
                        # Return placeholder prompts based on count
                        count = len(tree.body.elts)
                        class_name = probe_class.__name__
                        prompts = [f"[Prompt {i + 1} from {class_name}]" for i in range(count)]
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Error extracting prompts from {probe_class.__name__}: {e}")

        return prompts

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

            # Get prompts - Garak probes set prompts inside probe() method
            # We need to extract them from the source code
            prompts = self._extract_prompts_from_probe_method(probe_class)

            # Get detector
            detector = None
            if hasattr(probe_class, "recommended_detector"):
                detector_value = probe_class.recommended_detector
                # Handle both string and list types
                if isinstance(detector_value, (list, tuple)):
                    detector = detector_value[0] if detector_value else None
                elif isinstance(detector_value, str):
                    detector = detector_value

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
