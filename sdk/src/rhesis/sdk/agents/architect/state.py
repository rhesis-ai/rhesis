"""Serialisable snapshot of ArchitectAgent runtime state.

Used by ``ArchitectAgent.dump_state`` / ``restore_state`` to persist
and reload agent state across Celery task boundaries without coupling
the backend to private agent attributes.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArchitectAgentStateSnapshot(BaseModel):
    """Full serialisable snapshot of ArchitectAgent state.

    Fields map directly to what the backend stores in the DB:
    - ``mode`` / ``plan_data`` / ``conversation_history`` are separate
      DB columns on the architect session.
    - The remaining fields are stored together in the ``agent_state``
      JSON column.
    """

    mode: str = "discovery"
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    discovery_state: Dict[str, Any] = Field(default_factory=dict)
    guard_state: Dict[str, Any] = Field(default_factory=dict)
    id_to_name: Dict[str, str] = Field(default_factory=dict)
    plan_data: Optional[Dict[str, Any]] = None
    max_iterations: int = 15
    pending_tasks: List[Dict[str, Any]] = Field(default_factory=list)
