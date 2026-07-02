"""
Deprecated import path for the MAF (Microsoft Agent Framework) target.

``MicrosoftAgentFrameworkTarget`` was renamed to :class:`MAFTarget` and now
lives in :mod:`rhesis.penelope.targets.maf`.  This shim re-exports the old name
for backwards compatibility and will be removed in a future release; import
``MAFTarget`` from ``rhesis.penelope`` instead.
"""

import warnings

from rhesis.penelope.targets.maf import MAFTarget

warnings.warn(
    "MicrosoftAgentFrameworkTarget and the "
    "rhesis.penelope.targets.microsoft_agent_framework module are deprecated; "
    "use MAFTarget from rhesis.penelope instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Backwards-compatible alias for the renamed class.
MicrosoftAgentFrameworkTarget = MAFTarget

__all__ = ["MicrosoftAgentFrameworkTarget", "MAFTarget"]
