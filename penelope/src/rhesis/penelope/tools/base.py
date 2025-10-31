"""
Base tool interface for Penelope.

Tools are Penelope's primary way of interacting with the world and gathering information.
Following Anthropic's recommendations, each tool should be extensively documented
with clear examples and edge case handling.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    
    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type (string, number, boolean, object, array)")
    description: str = Field(description="Detailed description of the parameter")
    required: bool = Field(default=False, description="Whether the parameter is required")
    examples: Optional[list] = Field(default=None, description="Example values")


class ToolResult(BaseModel):
    """Result from a tool execution."""
    
    success: bool = Field(description="Whether the tool execution succeeded")
    output: Dict[str, Any] = Field(description="Output data from the tool")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution"
    )


class Tool(ABC):
    """
    Base class for all Penelope tools.
    
    Following Anthropic's Agent-Computer Interface (ACI) principles:
    1. Clear documentation (like writing for a junior developer)
    2. Example usage included
    3. Edge cases documented
    4. No formatting overhead
    5. Parameters that make sense to the model
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Detailed description of what the tool does.
        
        Should include:
        - Purpose and capabilities
        - When to use it
        - When NOT to use it
        - Best practices
        - Common pitfalls to avoid
        """
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """
        Parameter definitions with detailed descriptions and examples.
        
        Each parameter should have:
        - Clear name
        - Specific type
        - Detailed description with examples
        - Edge case handling notes
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with the given parameters.
        
        Args:
            **kwargs: Tool parameters as defined in self.parameters
            
        Returns:
            ToolResult with execution outcome
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the tool schema in a format suitable for LLM tool calling.
        
        Returns:
            Dictionary with name, description, and parameters
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    p.name: {
                        "type": p.type,
                        "description": p.description,
                    }
                    for p in self.parameters
                },
                "required": [p.name for p in self.parameters if p.required],
            },
        }
    
    def validate_input(self, **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate input parameters before execution.
        
        Args:
            **kwargs: Tool parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"
        
        # Check for unknown parameters
        param_names = {p.name for p in self.parameters}
        for key in kwargs:
            if key not in param_names:
                return False, f"Unknown parameter: {key}"
        
        return True, None

