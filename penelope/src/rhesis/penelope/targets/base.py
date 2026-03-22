"""
Backward-compatibility shim.

The canonical ``Target`` and ``TargetResponse`` classes now live in
``rhesis.sdk.targets``.  This module re-exports them so existing
imports from ``rhesis.penelope.targets.base`` continue to work.
"""

from rhesis.sdk.targets import Target, TargetResponse

__all__ = ["Target", "TargetResponse"]
