"""
Garak probe enumeration service.

This module provides the main service class for discovering and
extracting Garak probes for import into Rhesis as test sets.
"""

import importlib
import pkgutil
from typing import Any, Dict, List, Optional

from rhesis.backend.logging.rhesis_logger import logger

from .extraction import PromptExtractor
from .models import GarakModuleInfo, GarakProbeInfo


class GarakProbeService:
    """Service for enumerating and extracting Garak probes."""

    # Modules to exclude from enumeration (internal/testing modules)
    EXCLUDED_MODULES = {"base", "test"}

    def __init__(self):
        self._probe_cache: Dict[str, GarakModuleInfo] = {}
        self._garak_version: Optional[str] = None
        self._discovered_modules: Optional[List[str]] = None
        self._extractor = PromptExtractor()

    def _discover_probe_modules(self) -> List[str]:
        """
        Dynamically discover all probe modules in garak.probes.

        Uses pkgutil to iterate over the garak.probes package and find
        all available probe modules, excluding internal ones.

        Returns:
            List of probe module names

        Raises:
            ImportError: If garak package is not installed
        """
        if self._discovered_modules is not None:
            return self._discovered_modules

        # Let ImportError propagate - callers handle garak not being installed
        import garak.probes

        modules = []
        for importer, modname, ispkg in pkgutil.iter_modules(garak.probes.__path__):
            if modname not in self.EXCLUDED_MODULES:
                modules.append(modname)

        self._discovered_modules = sorted(modules)
        return self._discovered_modules

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
            # Dynamically discover probe modules
            probe_modules = self._discover_probe_modules()

            for module_name in probe_modules:
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
                        probe_prompts = self._extractor.extract_prompts(attr)
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

        except ImportError:
            # Module not found in this garak version - skip silently
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

            # Get prompts using the extractor
            prompts = self._extractor.extract_prompts(probe_class)

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

        Raises:
            RuntimeError: If garak package is not installed
        """
        all_probes = {}

        try:
            probe_modules = self._discover_probe_modules()
        except ImportError as e:
            logger.error(f"Garak package not installed: {e}")
            raise RuntimeError("Garak package is not installed") from e

        for module_name in probe_modules:
            probes = self.extract_probes_from_module(module_name)
            if probes:
                all_probes[module_name] = probes

        return all_probes

    async def enumerate_probe_modules_cached(
        self,
    ) -> tuple[List[GarakModuleInfo], Dict[str, List[GarakProbeInfo]]]:
        """
        Enumerate probe modules with caching support.

        This is the preferred method for API endpoints - it checks the cache
        first and only generates probe data if not cached.

        Returns:
            Tuple of (modules, probes_by_module) where:
            - modules: List of GarakModuleInfo
            - probes_by_module: Dict mapping module names to lists of GarakProbeInfo
        """
        from rhesis.backend.app.services.garak.cache import (
            GarakProbeCache,
            deserialize_probe_data,
            serialize_probe_data,
        )

        # Check cache first
        cached_data = await GarakProbeCache.get(self.garak_version)
        if cached_data:
            module_count = len(cached_data.get("modules", []))
            probe_count = sum(
                len(probes) for probes in cached_data.get("probes_by_module", {}).values()
            )
            logger.info(
                f"Garak probe cache HIT: {module_count} modules, "
                f"{probe_count} probes (v{self.garak_version})"
            )
            return deserialize_probe_data(cached_data)

        # Cache miss - generate probe data
        # Suppress verbose output during enumeration (print statements and logging)
        import contextlib
        import io
        import logging

        logger.info(f"Garak probe cache MISS: generating probe data (v{self.garak_version})...")

        # Suppress all output: garak uses print() statements, and we have debug logs
        null_output = io.StringIO()

        # Get all loggers that might produce output during enumeration
        root_logger = logging.getLogger()
        garak_logger = logging.getLogger("garak")
        rhesis_logger = logging.getLogger("__rhesis__")

        # Save original levels
        original_levels = {
            "root": root_logger.level,
            "garak": garak_logger.level,
            "rhesis": rhesis_logger.level,
        }

        try:
            # Suppress all logging during enumeration
            root_logger.setLevel(logging.CRITICAL)
            garak_logger.setLevel(logging.CRITICAL)
            rhesis_logger.setLevel(logging.CRITICAL)

            # Suppress stdout/stderr (garak uses print() for "loading probe:" messages)
            with contextlib.redirect_stdout(null_output), contextlib.redirect_stderr(null_output):
                modules = self.enumerate_probe_modules()

                # Extract probes for each module
                probes_by_module: Dict[str, List[GarakProbeInfo]] = {}
                for module in modules:
                    probes = self.extract_probes_from_module(module.name)
                    if probes:
                        probes_by_module[module.name] = probes
        finally:
            # Restore original log levels
            root_logger.setLevel(original_levels["root"])
            garak_logger.setLevel(original_levels["garak"])
            rhesis_logger.setLevel(original_levels["rhesis"])

        # Store in cache
        cache_data = serialize_probe_data(modules, probes_by_module)
        await GarakProbeCache.set(self.garak_version, cache_data)

        total_probes = sum(len(p) for p in probes_by_module.values())
        logger.info(
            f"Garak probe cache SET: {len(modules)} modules, "
            f"{total_probes} probes (v{self.garak_version}, TTL: 7 days)"
        )

        return modules, probes_by_module

    async def warm_cache(self) -> bool:
        """
        Pre-warm the probe cache.

        Called during application startup to ensure the cache is populated
        before the first user request.

        Returns:
            True if cache was warmed successfully, False otherwise
        """
        from rhesis.backend.app.services.garak.cache import GarakProbeCache

        try:
            # Check if cache already exists
            cached_data = await GarakProbeCache.get(self.garak_version)
            if cached_data:
                # Cache already warm - enumerate_probe_modules_cached will log details
                return True

            # Generate and cache (this will log summary)
            await self.enumerate_probe_modules_cached()
            return True

        except Exception as e:
            logger.error(f"Failed to warm Garak probe cache: {e}")
            return False
