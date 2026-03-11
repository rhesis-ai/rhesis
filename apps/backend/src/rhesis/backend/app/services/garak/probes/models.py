"""
Data models for Garak probe enumeration.

This module defines the dataclasses used to represent
Garak probes and modules.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# Placeholder used for generator.name in extracted prompts
GENERATOR_PLACEHOLDER = "{TARGET_MODEL}"


@dataclass
class GarakProbeInfo:
    """Information about a single Garak probe class."""

    module_name: str
    class_name: str
    full_name: str
    description: str
    # Explicit attack objective from probe_class.goal (distinct from the docstring).
    # May be None for probes that do not declare a goal attribute.
    goal: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    prompt_count: int = 0
    detector: Optional[str] = None
    # True when the probe has no static prompts and generates them at runtime.
    # Such probes are excluded from static import and offered for dynamic LLM synthesis.
    is_dynamic: bool = False


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
    # True when at least one probe in this module is dynamic.
    has_dynamic_probes: bool = False
