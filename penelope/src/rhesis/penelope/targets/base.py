"""
Base target interface for Penelope.

A Target represents any system that Penelope can test through interaction.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TargetResponse(BaseModel):
    """Response from a target interaction."""
    
    success: bool = Field(description="Whether the interaction succeeded")
    content: str = Field(description="The response content")
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversations"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if interaction failed"
    )


class Target(ABC):
    """
    Base class for all Penelope targets.
    
    A Target represents any system that Penelope can test. Targets must
    support sending messages and receiving responses, enabling multi-turn
    interaction.
    
    Examples of targets:
    - EndpointTarget: HTTP/REST/WebSocket endpoints
    - AgentTarget: Other AI agents
    - SystemTarget: Complete applications
    - Custom: User-defined targets
    """
    
    @property
    @abstractmethod
    def target_type(self) -> str:
        """Type identifier for this target (e.g., 'endpoint', 'agent')."""
        pass
    
    @property
    @abstractmethod
    def target_id(self) -> str:
        """Unique identifier for this specific target instance."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the target."""
        pass
    
    @abstractmethod
    def send_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> TargetResponse:
        """
        Send a message to the target and receive a response.
        
        This is the primary method for interacting with targets.
        
        Args:
            message: The message to send
            session_id: Optional session ID for maintaining conversation context
            **kwargs: Additional target-specific parameters
            
        Returns:
            TargetResponse with the result
        """
        pass
    
    @abstractmethod
    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """
        Validate the target configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    def get_tool_documentation(self) -> str:
        """
        Get documentation for how to interact with this target.
        
        This is used to help Penelope understand how to use the target.
        
        Returns:
            Documentation string for the target
        """
        return f"""
Target Type: {self.target_type}
Target ID: {self.target_id}
Description: {self.description}

Send messages using send_message(message, session_id).
Maintain session_id across turns for conversation continuity.
"""

