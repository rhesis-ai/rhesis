"""Shared constants and enums for the agent framework."""

from enum import StrEnum


class Action(StrEnum):
    """Actions the LLM can take in the ReAct loop."""

    CALL_TOOL = "call_tool"
    FINISH = "finish"


class Role(StrEnum):
    """Conversation message roles."""

    USER = "user"
    ASSISTANT = "assistant"


class ToolMeta(StrEnum):
    """Keys used in tool definition dicts for write-guard classification.

    ``readOnlyHint`` and ``destructiveHint`` follow MCP ToolAnnotations
    naming (camelCase). ``requires_confirmation`` and ``http_method``
    are Rhesis-specific extensions (snake_case).
    """

    REQUIRES_CONFIRMATION = "requires_confirmation"
    READONLY_HINT = "readOnlyHint"
    DESTRUCTIVE_HINT = "destructiveHint"
    HTTP_METHOD = "http_method"


class InternalTool(StrEnum):
    """Pseudo-tool names for internal execution steps."""

    FINISH = "finish"
    ERROR = "error"
    SAVE_PLAN = "save_plan"


class AgentMode(StrEnum):
    """Lifecycle phases for the ArchitectAgent."""

    DISCOVERY = "discovery"
    PLANNING = "planning"
    CREATING = "creating"
    EXECUTING = "executing"
