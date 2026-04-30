"""Configuration for the ArchitectAgent.

Centralises every tuneable constant so callers can override them
without touching agent internals.  All values have sensible defaults.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


def _default_discovery_state() -> Dict[str, Any]:
    """Factory for a fresh discovery-state dict."""
    return {
        "endpoint_id": None,
        "endpoint_name": None,
        "explored": False,
        "observations": [],
        "user_confirmed_areas": [],
        "open_questions": [],
    }


@dataclass(frozen=True)
class ArchitectConfig:
    """All tuneable parameters for the ArchitectAgent."""

    # ── ReAct loop ────────────────────────────────────────────────
    max_iterations: int = 15

    # ── argument-validation limits ────────────────────────────────
    max_payload_bytes: int = 100_000
    max_string_value_len: int = 10_000
    max_array_items: int = 100

    # ── attachment truncation ─────────────────────────────────────
    max_attachment_chars: int = 20_000

    # ── conversation-history truncation ───────────────────────────
    recent_msg_limit: int = 4
    recent_msg_max_chars: int = 2_000
    older_msg_max_chars: int = 500

    # ── streaming / tool-result preview ───────────────────────────
    tool_result_preview_chars: int = 4_000
    reasoning_preview_chars: int = 200

    # ── HTTP methods treated as read-only ─────────────────────────
    readonly_http_methods: frozenset = field(
        default_factory=lambda: frozenset({"GET", "HEAD", "OPTIONS"})
    )
