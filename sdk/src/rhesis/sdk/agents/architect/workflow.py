"""Workflow path routing for lazy phase prompt loading."""

from __future__ import annotations

import re
from enum import StrEnum


class WorkflowPath(StrEnum):
    """High-level user intent — drives which reference files load per turn."""

    UNSET = "unset"
    EXPLORE = "explore"
    PRD = "prd"
    RUN_ANALYZE = "run_analyze"
    DIRECT = "direct"


_PRD_SIGNALS = (
    "acceptance criteria",
    "functional requirement",
    "user story",
    "product spec",
    "requirements doc",
    "guardrails doc",
    "numbered fr",
    " fr-",
    "prd",
)

_RUN_ANALYZE_SIGNALS = (
    "compare run",
    "compare my",
    "last run",
    "test results",
    "analyze run",
    "run analyze",
    "past runs",
    "summarize insights",
    "insights summary",
    "insights page",
)

_DIRECT_SIGNALS = (
    "list my",
    "list test",
    "list metric",
    "list behavior",
    "update metric",
    "improve metric",
    "link metric",
    "unlink metric",
)


def infer_workflow_path(message: str, *, has_attachments: bool = False) -> WorkflowPath | None:
    """Detect workflow path from the user message. Returns None if ambiguous."""
    text = message.lower().strip()

    if text in {"1", "one"}:
        return WorkflowPath.EXPLORE
    if text in {"2", "two"}:
        return WorkflowPath.EXPLORE
    if text in {"3", "three"}:
        return WorkflowPath.PRD
    if text in {"4", "four"}:
        return WorkflowPath.RUN_ANALYZE

    if re.search(r"(?:^|\b)(?:1|one)\b.*quick|quick exploration", text):
        return WorkflowPath.EXPLORE
    if re.search(r"(?:^|\b)(?:2|two)\b.*comprehensive|comprehensive exploration", text):
        return WorkflowPath.EXPLORE
    if re.search(
        r"(?:^|\b)(?:3|three)\b.*(?:prd|foundation|requirements)|"
        r"test foundation from your prd|build.*from.*prd",
        text,
    ):
        return WorkflowPath.PRD
    if re.search(
        r"(?:^|\b)(?:4|four)\b.*(?:run|analyze)|run or analyze existing",
        text,
    ):
        return WorkflowPath.RUN_ANALYZE

    if has_attachments and len(message) > 200:
        return WorkflowPath.PRD
    if any(signal in text for signal in _PRD_SIGNALS) and len(message) > 400:
        return WorkflowPath.PRD

    if any(signal in text for signal in _RUN_ANALYZE_SIGNALS):
        return WorkflowPath.RUN_ANALYZE

    if any(signal in text for signal in _DIRECT_SIGNALS):
        return WorkflowPath.DIRECT

    if any(
        phrase in text
        for phrase in (
            "explore my",
            "explore the",
            "test my endpoint",
            "test my chatbot",
            "test the endpoint",
        )
    ):
        return WorkflowPath.EXPLORE

    return None


_OVERRIDE_FROM_EXPLORE = frozenset(
    {
        WorkflowPath.PRD,
        WorkflowPath.RUN_ANALYZE,
        WorkflowPath.DIRECT,
    }
)


def resolve_workflow_path_update(
    current: WorkflowPath,
    message: str,
    *,
    has_attachments: bool = False,
) -> WorkflowPath | None:
    """Return an updated path when user signals warrant re-classification."""
    inferred = infer_workflow_path(message, has_attachments=has_attachments)
    if inferred is None:
        return None
    if current == WorkflowPath.UNSET:
        return inferred
    if current == WorkflowPath.EXPLORE and inferred in _OVERRIDE_FROM_EXPLORE:
        return inferred
    return None
