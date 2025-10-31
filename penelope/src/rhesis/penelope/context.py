"""
Context and state management for Penelope agent.

Handles test state, conversation history, and result tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    """Status of a test execution."""
    
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"
    MAX_ITERATIONS = "max_iterations"


class Turn(BaseModel):
    """Represents a single turn in the test conversation."""
    
    turn_number: int = Field(description="The turn number (1-indexed)")
    timestamp: datetime = Field(default_factory=datetime.now)
    reasoning: str = Field(description="Penelope's reasoning for this turn")
    action: str = Field(description="The action taken (tool name)")
    action_input: Dict[str, Any] = Field(description="Input provided to the tool")
    action_output: Dict[str, Any] = Field(description="Output received from the tool")
    evaluation: Optional[str] = Field(
        default=None,
        description="Evaluation of progress after this turn"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TestResult(BaseModel):
    """Result of a test execution."""
    
    status: TestStatus = Field(description="Final status of the test")
    goal_achieved: bool = Field(description="Whether the test goal was achieved")
    turns_used: int = Field(description="Number of turns executed")
    findings: List[str] = Field(
        default_factory=list,
        description="Key findings from the test"
    )
    history: List[Turn] = Field(
        default_factory=list,
        description="Complete conversation history"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the test execution"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate test duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GoalProgress(BaseModel):
    """Evaluation of progress toward the test goal."""
    
    goal_achieved: bool = Field(description="Whether the goal is achieved")
    goal_impossible: bool = Field(
        default=False,
        description="Whether the goal is determined to be impossible"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the evaluation (0.0 to 1.0)"
    )
    reasoning: str = Field(description="Explanation of the evaluation")
    findings: List[str] = Field(
        default_factory=list,
        description="Specific findings supporting this evaluation"
    )


@dataclass
class TestContext:
    """
    Context for a test execution.
    
    Contains all information needed to execute a test, including
    target, test instructions, and resources.
    """
    
    target_id: str
    target_type: str
    test_instructions: str
    goal: str
    context: Dict[str, Any] = field(default_factory=dict)
    max_turns: int = 20
    timeout_seconds: Optional[float] = None
    

@dataclass
class TestState:
    """
    Current state of a test execution.
    
    Tracks conversation history, turn count, and session information.
    """
    
    context: TestContext
    turns: List[Turn] = field(default_factory=list)
    current_turn: int = 0
    session_id: Optional[str] = None
    findings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    def add_turn(
        self,
        reasoning: str,
        action: str,
        action_input: Dict[str, Any],
        action_output: Dict[str, Any],
        evaluation: Optional[str] = None,
    ) -> Turn:
        """
        Add a turn to the conversation history.
        
        Args:
            reasoning: Penelope's reasoning for this turn
            action: The action/tool used
            action_input: Input provided to the tool
            action_output: Output from the tool
            evaluation: Optional evaluation of progress
            
        Returns:
            The created Turn object
        """
        self.current_turn += 1
        
        turn = Turn(
            turn_number=self.current_turn,
            reasoning=reasoning,
            action=action,
            action_input=action_input,
            action_output=action_output,
            evaluation=evaluation,
        )
        
        self.turns.append(turn)
        return turn
    
    def add_finding(self, finding: str) -> None:
        """Add a finding to the findings list."""
        if finding not in self.findings:
            self.findings.append(finding)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history in a format suitable for LLM context.
        
        Returns:
            List of message dictionaries with role and content
        """
        messages = []
        
        for turn in self.turns:
            # Add assistant's reasoning and action
            messages.append({
                "role": "assistant",
                "content": (
                    f"Reasoning: {turn.reasoning}\n"
                    f"Action: {turn.action}\n"
                    f"Input: {turn.action_input}"
                )
            })
            
            # Add tool result
            messages.append({
                "role": "user",
                "content": f"Tool Result: {turn.action_output}"
            })
        
        return messages
    
    def to_result(self, status: TestStatus, goal_achieved: bool) -> TestResult:
        """
        Convert the current state to a TestResult.
        
        Args:
            status: Final status of the test
            goal_achieved: Whether the goal was achieved
            
        Returns:
            TestResult object
        """
        return TestResult(
            status=status,
            goal_achieved=goal_achieved,
            turns_used=self.current_turn,
            findings=self.findings,
            history=self.turns,
            start_time=self.start_time,
            end_time=datetime.now(),
        )

