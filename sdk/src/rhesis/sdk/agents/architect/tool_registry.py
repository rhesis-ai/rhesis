"""Unified tool-category registry for the ArchitectAgent.

Single source of truth that replaces the separate
``_CREATING_TOOLS``, ``_EXECUTING_TOOLS`` and
``_TOOL_TO_PLAN_CATEGORY`` mappings that were maintained in
parallel inside ``agent.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, FrozenSet, Optional

from rhesis.sdk.agents.constants import AgentMode


class PlanCategory(StrEnum):
    """Plan item categories tracked for progress."""

    PROJECT = "project"
    BEHAVIOR = "behavior"
    TEST_SET = "test_set"
    METRIC = "metric"
    MAPPING = "mapping"


@dataclass(frozen=True)
class ToolEntry:
    """Metadata for a single external tool."""

    mode: AgentMode
    plan_category: Optional[PlanCategory] = None


TOOL_REGISTRY: Dict[str, ToolEntry] = {
    "create_project": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.PROJECT,
    ),
    "create_behavior": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.BEHAVIOR,
    ),
    "create_test_set_bulk": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.TEST_SET,
    ),
    "generate_test_set": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.TEST_SET,
    ),
    "create_metric": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.METRIC,
    ),
    "generate_metric": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.METRIC,
    ),
    "improve_metric": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.METRIC,
    ),
    "add_behavior_to_metric": ToolEntry(
        mode=AgentMode.CREATING,
        plan_category=PlanCategory.MAPPING,
    ),
    "execute_test_set": ToolEntry(
        mode=AgentMode.EXECUTING,
    ),
    "get_test_result_stats": ToolEntry(
        mode=AgentMode.EXECUTING,
    ),
    "get_test_run_stats": ToolEntry(
        mode=AgentMode.EXECUTING,
    ),
}


def tools_for_mode(mode: AgentMode) -> FrozenSet[str]:
    """Return the set of tool names that trigger a given mode."""
    return frozenset(
        name for name, entry in TOOL_REGISTRY.items() if entry.mode == mode
    )


def plan_category_for(tool_name: str) -> Optional[PlanCategory]:
    """Return the plan category a tool maps to, or None."""
    entry = TOOL_REGISTRY.get(tool_name)
    return entry.plan_category if entry else None


def mode_for(tool_name: str) -> Optional[AgentMode]:
    """Return the mode a tool should trigger, or None."""
    entry = TOOL_REGISTRY.get(tool_name)
    return entry.mode if entry else None
