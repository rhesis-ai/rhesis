"""Future tool extension point for Dr-Rhesis.

No tools are implemented in the first draft. The one safe future addition is a
"find care near me" lookup wired only into the escalation path via Haystack
``Tool`` / ``ComponentTool``.
"""

from __future__ import annotations

# Placeholder for future escalation-only tools.
ESCALATION_TOOLS: list[object] = []

__all__ = ["ESCALATION_TOOLS"]
