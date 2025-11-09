# Multi-Turn Metrics Design Document

**Status**: Design Proposal  
**Date**: 2025-11-02  
**Author**: Penelope Design Team  
**Last Updated**: 2025-11-02 (Native Message Format)

## Executive Summary

This document proposes extending the Rhesis SDK metrics system to support **multi-turn conversation evaluation**. This will enable:
1. Automated goal achievement assessment in Penelope tests
2. Standalone conversation quality evaluation
3. Integration with any conversation-based system (LangChain, CrewAI, etc.)
4. Platform-wide conversation analytics in Rhesis

**Key Architecture Decision**: Penelope uses **native Pydantic message schemas** (`AssistantMessage`, `ToolMessage`) that are provider-agnostic and compatible with major LLM providers (OpenAI, Anthropic, Vertex AI, etc.). No format conversions are required.

## Problem Statement

### Current Limitations

**Penelope's Goal Tracking (Current)**:
- Uses placeholder heuristics in `_evaluate_goal_progress()`
- Cannot properly determine if multi-turn test goals are achieved
- Results in false negatives (e.g., "goal not achieved" when it actually was)
- Lacks sophisticated conversation analysis

**SDK Metrics (Current)**:
- Only support single-turn evaluation (`input` → `output`)
- Cannot evaluate conversation-level properties:
  - Goal achievement across multiple turns
  - Context retention
  - Conversation coherence
  - Task completion

### Example Issue

```
Test Goal: "Successfully complete a multi-turn conversation where:
- The chatbot provides information about insurance types
- The chatbot answers follow-up questions with context
- The chatbot remembers previous parts of the conversation
- At least 4 turns are completed"

Actual Result: All criteria met ✓
Reported Result: "Goal not fully achieved" ✗
```

## Proposed Solution

### Penelope's Native Message Format

**Core Design**: Penelope stores conversations using **native Pydantic schemas** defined in `rhesis.penelope.schemas`:

```python
# rhesis/penelope/schemas.py

class FunctionCall(BaseModel):
    """Function call specification."""
    name: str
    arguments: str  # JSON string

class MessageToolCall(BaseModel):
    """Tool call specification."""
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall

class AssistantMessage(BaseModel):
    """
    Assistant message with optional tool calls.
    Compatible with OpenAI, Anthropic, Vertex AI, and other providers.
    """
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[MessageToolCall]] = None

class ToolMessage(BaseModel):
    """
    Tool response message.
    Compatible with OpenAI, Anthropic, Vertex AI, and other providers.
    """
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    content: str
```

**Turn Structure**:
```python
class Turn(BaseModel):
    """Represents a single turn in the test conversation."""
    turn_number: int
    timestamp: datetime
    
    # Native Pydantic message objects
    assistant_message: AssistantMessage
    tool_message: ToolMessage
    
    # Penelope metadata
    reasoning: str
    evaluation: Optional[str] = None
    retrieval_context: Optional[List[Dict[str, Any]]] = None
```

**Benefits**:
- ✅ **No Conversions**: Messages are stored in standard format natively
- ✅ **Type Safety**: Full Pydantic validation and IDE support
- ✅ **Provider Agnostic**: Works with any LLM provider supporting this format
- ✅ **Direct Access**: No serialization overhead to access message fields
- ✅ **Flexible Export**: Convert to dict only when needed via `.model_dump()`

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Rhesis SDK                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            Multi-Turn Metrics                         │  │
│  │  - BaseMultiTurnMetric (abstract)                     │  │
│  │  - GoalAchievementJudge                              │  │
│  │  - ContextRetentionMetric                            │  │
│  │  - ConversationCoherenceMetric                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ▲                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
    ┌─────────▼────────┐      ┌────────▼─────────┐
    │    Penelope      │      │  External Users  │
    │   (Consumer)     │      │  - Platform API  │
    │                  │      │  - LangChain     │
    │ Native Pydantic  │      │  - CrewAI        │
    │ message schemas  │      │  - Custom Apps   │
    └──────────────────┘      └──────────────────┘
```

## SDK Design: Multi-Turn Metrics

### 1. Conversation Data Models

```python
# rhesis/sdk/metrics/types.py

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""
    
    role: Literal["user", "assistant", "system"] = Field(
        description="The role of the speaker in this turn"
    )
    content: str = Field(
        description="The content/message of this turn"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (timestamp, tokens, etc.)"
    )


class ConversationHistory(BaseModel):
    """Complete conversation history."""
    
    turns: List[ConversationTurn] = Field(
        description="Ordered list of conversation turns"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional unique identifier for the conversation"
    )
    
    def to_dict_list(self) -> List[Dict[str, str]]:
        """Convert to simple dict format for compatibility."""
        return [
            {"role": turn.role, "content": turn.content}
            for turn in self.turns
        ]
    
    @classmethod
    def from_dict_list(cls, turns: List[Dict[str, str]]) -> "ConversationHistory":
        """Create from simple dict format."""
        return cls(
            turns=[
                ConversationTurn(role=t["role"], content=t["content"])
                for t in turns
            ]
        )


class MultiTurnEvaluationInput(BaseModel):
    """Input for multi-turn metric evaluation."""
    
    conversation_history: ConversationHistory = Field(
        description="The conversation to evaluate"
    )
    goal: str = Field(
        description="The goal or success criteria to evaluate against"
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Optional instructions that guided the conversation"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context (target type, expected behavior, etc.)"
    )
```

### 2. Base Multi-Turn Metric

```python
# rhesis/sdk/metrics/base.py (additions)

from abc import abstractmethod
from rhesis.sdk.metrics.types import MultiTurnEvaluationInput


class ConversationType(str, Enum):
    """Type of conversation evaluation."""
    
    SINGLE_TURN = "single_turn"
    MULTI_TURN = "multi_turn"


class BaseMultiTurnMetric(BaseMetric):
    """
    Base class for multi-turn conversation evaluation metrics.
    
    Multi-turn metrics evaluate entire conversations against specific criteria
    such as goal achievement, context retention, or conversation quality.
    
    They are framework-agnostic and can be used with any conversation system
    (Penelope, LangChain, CrewAI, custom chatbots, etc.).
    """
    
    def __init__(
        self,
        config: MetricConfig,
        model: Optional[Union[BaseLLM, str]] = None
    ):
        super().__init__(config, model)
        self.conversation_type = ConversationType.MULTI_TURN
    
    @abstractmethod
    def evaluate_conversation(
        self,
        evaluation_input: MultiTurnEvaluationInput,
    ) -> MetricResult:
        """
        Evaluate a multi-turn conversation.
        
        Args:
            evaluation_input: The conversation and evaluation criteria
            
        Returns:
            MetricResult with score and detailed evaluation
        """
        pass
    
    # Convenience method for simpler API
    def evaluate(
        self,
        conversation_history: Union[ConversationHistory, List[Dict[str, str]]],
        goal: str,
        instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MetricResult:
        """
        Evaluate a conversation (simplified API).
        
        Args:
            conversation_history: Conversation as ConversationHistory or list of dicts
            goal: The goal/success criteria
            instructions: Optional test instructions
            context: Optional additional context
            
        Returns:
            MetricResult with evaluation details
        """
        # Convert to ConversationHistory if needed
        if isinstance(conversation_history, list):
            conversation_history = ConversationHistory.from_dict_list(conversation_history)
        
        # Create evaluation input
        eval_input = MultiTurnEvaluationInput(
            conversation_history=conversation_history,
            goal=goal,
            instructions=instructions,
            context=context,
        )
        
        return self.evaluate_conversation(eval_input)
```

### 3. Goal Achievement Judge (First Implementation)

```python
# rhesis/sdk/metrics/providers/native/multi_turn/goal_achievement.py

from typing import List, Optional, Union
from pydantic import BaseModel, Field, create_model

from rhesis.sdk.metrics.base import BaseMultiTurnMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.types import MultiTurnEvaluationInput
from rhesis.sdk.models.base import BaseLLM


class GoalAchievementResponse(BaseModel):
    """Structured response from LLM for goal achievement evaluation."""
    
    achievement_level: str = Field(
        description="Level of goal achievement: not_achieved, partially_achieved, or fully_achieved"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the assessment (0.0 to 1.0)"
    )
    reasoning: str = Field(
        description="Detailed explanation of why this achievement level was assigned"
    )
    evidence: List[str] = Field(
        description="Specific evidence from the conversation supporting the assessment"
    )
    missing_criteria: List[str] = Field(
        default_factory=list,
        description="List of criteria that were not met (empty if fully achieved)"
    )


class GoalAchievementJudge(BaseMultiTurnMetric):
    """
    Evaluates whether a multi-turn conversation achieved its stated goal.
    
    This metric uses an LLM to comprehensively assess:
    - Whether all goal criteria were met
    - Quality of goal achievement
    - Evidence from conversation
    - Missing elements (if any)
    
    Example:
        >>> from rhesis.sdk.metrics import GoalAchievementJudge
        >>> from rhesis.sdk.models import AnthropicLLM
        >>> 
        >>> metric = GoalAchievementJudge(
        ...     categories=["not_achieved", "partially_achieved", "fully_achieved"],
        ...     passing_categories=["fully_achieved"],
        ...     model=AnthropicLLM()
        ... )
        >>> 
        >>> conversation = [
        ...     {"role": "user", "content": "What insurance do you offer?"},
        ...     {"role": "assistant", "content": "We offer auto, home, life."},
        ...     {"role": "user", "content": "Tell me about auto coverage."},
        ...     {"role": "assistant", "content": "Auto includes liability and collision."},
        ... ]
        >>> 
        >>> result = metric.evaluate(
        ...     conversation_history=conversation,
        ...     goal="Customer learns about insurance types and specific coverage"
        ... )
        >>> 
        >>> print(f"Achieved: {result.details['is_successful']}")
        >>> print(f"Reasoning: {result.details['reasoning']}")
    """
    
    EVALUATION_TEMPLATE = """You are evaluating whether a multi-turn conversation achieved its stated goal.

**Goal/Success Criteria:**
{goal}

{% if instructions %}
**Test Instructions:**
{instructions}
{% endif %}

{% if context %}
**Context:**
{context}
{% endif %}

**Conversation History:**
{% for turn in conversation_turns %}
{{ turn.role|upper }}: {{ turn.content }}
{% endfor %}

**Your Task:**
Evaluate whether the conversation achieved the stated goal. Consider:
1. Were all criteria in the goal satisfied?
2. Is there clear evidence in the conversation?
3. Did the conversation maintain context and coherence?
4. Were any critical elements missing?

Classify the achievement level as:
- **fully_achieved**: All goal criteria clearly met with strong evidence
- **partially_achieved**: Some criteria met, but gaps or issues exist
- **not_achieved**: Goal criteria not met or conversation failed

Provide:
1. Your achievement level classification
2. Confidence in your assessment (0.0 to 1.0)
3. Detailed reasoning explaining your decision
4. Specific evidence from the conversation
5. List of missing criteria (if any)"""
    
    def __init__(
        self,
        categories: Optional[List[str]] = None,
        passing_categories: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = "goal_achievement",
        description: Optional[str] = "Evaluates multi-turn conversation goal achievement",
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Goal Achievement Judge.
        
        Args:
            categories: Achievement levels (default: ["not_achieved", "partially_achieved", "fully_achieved"])
            passing_categories: Levels considered successful (default: ["fully_achieved"])
            name: Metric name
            description: Metric description
            model: LLM model to use for evaluation
        """
        if categories is None:
            categories = ["not_achieved", "partially_achieved", "fully_achieved"]
        
        if passing_categories is None:
            passing_categories = ["fully_achieved"]
        elif isinstance(passing_categories, str):
            passing_categories = [passing_categories]
        
        config = MetricConfig(
            class_name=self.__class__.__name__,
            name=name,
            description=description,
            score_type="categorical",
            metric_type="conversation",
            requires_ground_truth=False,
            requires_context=False,
        )
        
        super().__init__(config=config, model=model)
        
        self.categories = categories
        self.passing_categories = passing_categories
    
    def evaluate_conversation(
        self,
        evaluation_input: MultiTurnEvaluationInput,
    ) -> MetricResult:
        """
        Evaluate goal achievement for a conversation.
        
        Args:
            evaluation_input: The conversation and evaluation criteria
            
        Returns:
            MetricResult with achievement assessment
        """
        from jinja2 import Template
        
        # Build evaluation prompt
        template = Template(self.EVALUATION_TEMPLATE)
        prompt = template.render(
            goal=evaluation_input.goal,
            instructions=evaluation_input.instructions,
            context=evaluation_input.context,
            conversation_turns=evaluation_input.conversation_history.turns,
        )
        
        # Create dynamic response model with valid categories
        from typing import Literal
        
        category_literal = Literal[tuple(self.categories)]  # type: ignore
        DynamicGoalResponse = create_model(
            "DynamicGoalResponse",
            achievement_level=(category_literal, ...),
            confidence=(float, Field(ge=0.0, le=1.0)),
            reasoning=(str, ...),
            evidence=(List[str], ...),
            missing_criteria=(List[str], Field(default_factory=list)),
        )
        
        try:
            # Get LLM evaluation with structured output
            response = self.model.generate(prompt, schema=DynamicGoalResponse)
            response_obj = DynamicGoalResponse(**response)  # type: ignore
            
            # Determine if successful
            is_successful = response_obj.achievement_level in self.passing_categories  # type: ignore
            
            # Build detailed result
            details = {
                "score": response_obj.achievement_level,  # type: ignore
                "score_type": "categorical",
                "is_successful": is_successful,
                "confidence": response_obj.confidence,  # type: ignore
                "reasoning": response_obj.reasoning,  # type: ignore
                "evidence": response_obj.evidence,  # type: ignore
                "missing_criteria": response_obj.missing_criteria,  # type: ignore
                "categories": self.categories,
                "passing_categories": self.passing_categories,
                "prompt": prompt,
                "conversation_length": len(evaluation_input.conversation_history.turns),
                "goal": evaluation_input.goal,
            }
            
            return MetricResult(
                score=response_obj.achievement_level,  # type: ignore
                details=details
            )
            
        except Exception as e:
            # Return error result
            error_details = {
                "score": "error",
                "score_type": "categorical",
                "is_successful": False,
                "confidence": 0.0,
                "reasoning": f"Evaluation failed: {str(e)}",
                "evidence": [],
                "missing_criteria": [],
                "error": str(e),
                "exception_type": type(e).__name__,
            }
            
            return MetricResult(score="error", details=error_details)
```

### 4. Additional Multi-Turn Metrics

```python
# rhesis/sdk/metrics/providers/native/multi_turn/context_retention.py

class ContextRetentionMetric(BaseMultiTurnMetric):
    """
    Evaluates how well context is maintained across conversation turns.
    
    Assesses:
    - References to previous turns
    - Consistency in information
    - Proper use of pronouns/anaphora
    - Memory of earlier stated facts
    """
    # Implementation similar to GoalAchievementJudge
    pass


# rhesis/sdk/metrics/providers/native/multi_turn/conversation_coherence.py

class ConversationCoherenceMetric(BaseMultiTurnMetric):
    """
    Evaluates the natural flow and coherence of a conversation.
    
    Assesses:
    - Logical progression of topics
    - Smooth transitions between turns
    - Appropriate responses to questions
    - Overall conversation quality
    """
    # Implementation similar to GoalAchievementJudge
    pass
```

## Penelope's Analysis Tools: Optional Reasoning Scaffolding

### Design Philosophy

Penelope provides **optional reasoning tools** (`AnalyzeTool` and `ExtractTool`) that help the LLM agent systematically analyze responses from the system under test. These tools follow Anthropic's ACI principles by providing scaffolding for better reasoning without forcing a specific approach.

### Architecture

```python
# rhesis/penelope/tools/analysis.py

class AnalyzeTool(Tool):
    """
    Tool for analyzing endpoint responses.
    
    Helps Penelope systematically evaluate responses for patterns, tone,
    structure, and test-relevant characteristics.
    """
    
    def execute(self, response_text: str, analysis_focus: str, context: str = ""):
        """
        Current Implementation: Simple regex-based analysis
        - Word count and response length
        - Basic sentiment (positive/negative word counting)
        - Structure detection (bullets, numbers)
        - Focus-specific checks (policy language, context maintenance)
        
        Future Implementation: LLM-based deep analysis
        - Semantic understanding of responses
        - Intent detection and goal alignment
        - Context coherence evaluation
        - Quality scoring against test criteria
        """
        # Returns structured findings for Penelope to reason about


class ExtractTool(Tool):
    """
    Tool for extracting specific information from responses.
    
    Helps Penelope pull out facts, entities, and structured data
    from unstructured responses.
    """
    
    def execute(self, response_text: str, extraction_target: str):
        """
        Current Implementation: Regex-based extraction
        - Dates (various formats)
        - Numbers and quantities
        - Email addresses and phone numbers
        - Keyword-based sentence extraction
        
        Future Implementation: LLM-based extraction
        - Entity recognition (products, services, policies)
        - Relationship extraction
        - Fact verification
        - Structured data extraction
        """
        # Returns extracted entities and relevant content
```

### How They're Used

**Automatic Availability**: Both tools are automatically included in every test:

```python
# rhesis/penelope/agent.py

def _get_tools_for_test(self, target: Target) -> List[Tool]:
    """Get tools for a specific test."""
    tools = [
        TargetInteractionTool(target),  # PRIMARY: Send messages
        AnalyzeTool(),                   # OPTIONAL: Analyze responses
        ExtractTool(),                   # OPTIONAL: Extract information
    ]
    tools.extend(self.custom_tools)
    return tools
```

**LLM Decides When to Use**: Penelope (the LLM agent) autonomously chooses when to use these tools based on:
- Test goal requirements
- Response complexity
- Need for evidence extraction
- Systematic reasoning benefits

### Typical Workflow

```
1. Penelope sends message to target
   └─> Uses TargetInteractionTool
   
2. Receives response from system under test
   
3. OPTIONAL: Analyzes the response
   └─> Uses AnalyzeTool("Check if response maintains context from previous turn")
   └─> Gets structured findings: tone, length, structure, specific patterns
   
4. OPTIONAL: Extracts specific information
   └─> Uses ExtractTool("Extract refund timeframe mentioned")
   └─> Gets specific data: dates, numbers, relevant sentences
   
5. Uses analysis to decide next action
   └─> Build evidence for goal evaluation
   └─> Plan follow-up questions
   └─> Verify test criteria
```

### Example Usage Scenario

**Test Goal**: "Verify chatbot provides accurate refund policy information"

```python
# Turn 1: Initial question
Penelope: send_message_to_target("What's your refund policy?")
Target: "We offer 30-day returns for unopened items in original packaging..."

# Turn 2: Analyze response
Penelope: analyze_response(
    response_text="We offer 30-day returns...",
    analysis_focus="Check if timeframe and conditions are clearly stated"
)
Result: {
    "findings": [
        "Response length: 45 words",
        "Tone: Generally positive/helpful",
        "Structure: Contains numerical information",
        "Policy check: Contains policy language"
    ]
}

# Turn 3: Extract specific facts
Penelope: extract_information(
    response_text="We offer 30-day returns...",
    extraction_target="refund timeframe and conditions"
)
Result: {
    "numbers": ["30"],
    "relevant_content": [
        "30-day returns for unopened items",
        "original packaging required"
    ]
}

# Turn 4: Follow-up based on analysis
Penelope: send_message_to_target("What if I opened the box but didn't use it?")
# Uses extracted info to ask targeted follow-up
```

### Current Implementation: Simple but Effective

**AnalyzeTool** performs basic pattern matching:
```python
# Sentiment detection
positive_words = ["yes", "can", "will", "happy", "help", "certainly", "glad"]
negative_words = ["no", "cannot", "won't", "unable", "unfortunately", "sorry"]

# Structure analysis
has_bullets = "•" in response_text or "-" in response_text
has_numbers = any(c.isdigit() for c in response_text)

# Focus-specific checks
if "policy" in analysis_focus:
    check_for_policy_language(response_text)
```

**ExtractTool** uses regex patterns:
```python
# Date extraction
dates = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", response_text)

# Email/phone extraction
emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", response_text)
phones = re.findall(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", response_text)

# Keyword-based sentence extraction
relevant_sentences = [s for s in response_text.split(".") 
                     if any(keyword in s.lower() for keyword in keywords)]
```

### Future Implementation: LLM-Powered Analysis

**Phase 1 Enhancement**: Replace regex with LLM-based analysis:

```python
class AnalyzeTool(Tool):
    def __init__(self, model: Optional[BaseLLM] = None):
        """Initialize with optional LLM for deep analysis."""
        self.model = model
    
    def execute(self, response_text: str, analysis_focus: str, context: str = ""):
        """Execute analysis using LLM for semantic understanding."""
        
        if self.model:
            # LLM-powered deep analysis
            prompt = f"""Analyze this response for: {analysis_focus}

Response: {response_text}

Context: {context}

Provide structured analysis including:
1. Main points and claims
2. Tone and sentiment
3. Completeness relative to focus
4. Any concerns or issues
5. Relevance to test goals"""
            
            result = self.model.generate(prompt, schema=AnalysisResult)
            return ToolResult(
                success=True,
                output={
                    "findings": result.findings,
                    "sentiment": result.sentiment,
                    "completeness": result.completeness_score,
                    "concerns": result.concerns,
                    "recommendations": result.next_steps,
                }
            )
        else:
            # Fallback to simple pattern matching
            return self._simple_analysis(response_text, analysis_focus)
```

**Phase 2 Enhancement**: Specialized extraction with entity recognition:

```python
class ExtractTool(Tool):
    def __init__(self, model: Optional[BaseLLM] = None):
        self.model = model
    
    def execute(self, response_text: str, extraction_target: str):
        """Execute extraction with LLM for semantic understanding."""
        
        if self.model:
            # LLM-powered entity extraction
            prompt = f"""Extract all instances of: {extraction_target}

From this text: {response_text}

Return structured data with:
- Extracted values
- Context for each
- Confidence level
- Related information"""
            
            result = self.model.generate(prompt, schema=ExtractionResult)
            return ToolResult(
                success=True,
                output={
                    "extracted_entities": result.entities,
                    "context_for_each": result.contexts,
                    "confidence": result.confidence,
                    "relationships": result.relationships,
                }
            )
        else:
            # Fallback to regex patterns
            return self._simple_extraction(response_text, extraction_target)
```

### Integration with Goal Evaluation

Analysis tools help build evidence for goal achievement:

```python
class GoalEvaluator:
    def evaluate_progress(self, state: TestState, goal: str) -> GoalProgress:
        """
        Evaluate goal progress using conversation and analysis findings.
        
        The findings from AnalyzeTool and ExtractTool are stored in
        state.findings and can provide structured evidence for evaluation.
        """
        
        # Convert conversation to SDK format
        conversation = self._to_conversation_format(state.turns)
        
        # Include analysis findings as additional context
        analysis_context = {
            "findings": state.findings,  # Includes analysis tool outputs
            "turn_count": len(state.turns),
            "successful_interactions": sum(
                1 for t in state.turns 
                if t.tool_result.get("success", False)
            )
        }
        
        # Evaluate with enriched context
        result = self.goal_metric.evaluate(
            conversation_history=conversation,
            goal=goal,
            context=analysis_context,
        )
        
        return self._convert_to_goal_progress(result)
```

### Benefits of This Design

**1. Optional, Not Mandatory**
- Penelope can choose to use or skip these tools
- No forced workflow or rigid structure
- Adapts to simple or complex test scenarios

**2. Scaffolding for Reasoning**
- Helps LLM think systematically about responses
- Provides structure without constraining creativity
- Builds evidence trail for goal evaluation

**3. Extensible Architecture**
- Current: Simple regex-based (fast, predictable)
- Future: LLM-powered (semantic understanding)
- No API changes needed for enhancement

**4. Follows Anthropic's ACI Principles**
- Extensive documentation guides LLM on when/how to use
- Clear examples of good and bad usage
- Natural parameter formats

**5. Evidence Building**
- Structured findings support goal evaluation
- Creates audit trail of analysis
- Helps explain why tests pass or fail

### When Analysis Tools Are Most Useful

**High Value Scenarios**:
- Complex responses requiring interpretation
- Multi-criteria test goals needing evidence
- Responses with embedded data (dates, policies, numbers)
- Context retention verification across turns
- Quality assessment of responses

**Lower Value Scenarios**:
- Simple yes/no validation
- Single-criterion tests
- Short conversation tests (< 3 turns)
- Binary pass/fail checks

### Configuration Options (Future)

```python
# Agents can customize analysis behavior
agent = PenelopeAgent(
    model=model,
    
    # Enable LLM-powered analysis
    analysis_model=VertexAILLM("gemini-pro"),
    
    # Or disable analysis tools entirely
    enable_analysis_tools=False,  # For simple tests
    
    # Or provide custom analysis tools
    custom_tools=[CustomDomainAnalyzer(), SpecializedExtractor()],
)
```

### Comparison with Other Approaches

| Approach | Penelope (Optional Tools) | Hardcoded Analysis | No Analysis |
|----------|---------------------------|-------------------|-------------|
| **Flexibility** | High - LLM decides | Low - fixed steps | High - but less structured |
| **Evidence Quality** | Structured findings | Guaranteed but rigid | Implicit only |
| **Performance** | Fast (optional) | Slower (always runs) | Fastest |
| **Adaptability** | High - adapts to response | Low - same for all | High - but less systematic |
| **Transparency** | High - explicit analysis | High - logged | Low - LLM reasoning hidden |
| **Best For** | Complex multi-turn tests | Compliance testing | Simple validation |

### Implementation Status

**Current (Phase 0)**:
- ✅ AnalyzeTool with regex-based analysis
- ✅ ExtractTool with regex-based extraction
- ✅ Automatic availability in all tests
- ✅ Extensive ACI documentation for LLM

**Future (Phase 1)**:
- [ ] LLM-powered semantic analysis
- [ ] Entity recognition and relationship extraction
- [ ] Configurable analysis depth
- [ ] Custom domain-specific analyzers

**Future (Phase 2)**:
- [ ] Streaming analysis for long responses
- [ ] Multi-modal analysis (images, files)
- [ ] Comparative analysis across turns
- [ ] Metric integration for quality scoring

### Design Rationale

This approach balances:

1. **Immediate Utility**: Simple regex-based tools work now
2. **Future Sophistication**: Clear path to LLM-powered enhancement
3. **Autonomy**: LLM agent decides when tools are valuable
4. **Transparency**: Explicit analysis vs. implicit reasoning
5. **Performance**: Optional tools don't slow down simple tests
6. **Extensibility**: Easy to add domain-specific analyzers

The key insight: **Analysis tools are scaffolding, not requirements**. They help Penelope reason more systematically when needed, but don't constrain its ability to handle straightforward scenarios efficiently.

## Penelope Integration

### Updated Goal Progress Evaluation

```python
# rhesis/penelope/agent.py (updated)

from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.metrics.types import ConversationHistory, ConversationTurn

class PenelopeAgent:
    def __init__(
        self,
        model: BaseLLM,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 20,
        timeout_seconds: Optional[float] = None,
        enable_transparency: bool = True,
        verbose: bool = False,
        goal_metric: Optional[BaseMultiTurnMetric] = None,  # NEW
    ):
        """
        Initialize Penelope agent.
        
        Args:
            ...
            goal_metric: Optional custom metric for goal evaluation.
                Defaults to GoalAchievementJudge if not provided.
        """
        self.model = model
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.enable_transparency = enable_transparency
        self.verbose = verbose
        
        # Initialize goal metric
        if goal_metric is None:
            self.goal_metric = GoalAchievementJudge(model=model)
        else:
            self.goal_metric = goal_metric
        
        self.custom_tools = tools or []
        
        logger.info(f"Initialized PenelopeAgent with {model.get_model_name()}")
    
    def _to_conversation_format(self, turns: List[Turn]) -> ConversationHistory:
        """
        Extract actual conversation from Penelope's test turns for SDK metrics.
        
        This extracts the domain conversation (user ↔ assistant messages about
        the actual subject being tested) from Penelope's tool-based testing turns.
        
        Note: Penelope's turns use native Pydantic message schemas (AssistantMessage,
        ToolMessage) that are already in standard format. This method doesn't convert
        formats - it extracts the content being tested.
        
        Args:
            turns: List of Penelope Turn objects
            
        Returns:
            ConversationHistory for SDK metric evaluation
        """
        conversation_turns = []
        
        for turn in turns:
            # Extract actual conversation from send_message_to_target tool
            if turn.tool_name == "send_message_to_target":
                message = turn.tool_arguments.get("message", "")
                if message:
                    conversation_turns.append(
                        ConversationTurn(role="user", content=message)
                    )
                
                # Extract assistant response from tool result
                result = turn.tool_result
                if isinstance(result, dict) and result.get("success"):
                    response = result.get("output", {})
                    response_text = (
                        response.get("response", "")
                        if isinstance(response, dict)
                        else str(response)
                    )
                    if response_text:
                        conversation_turns.append(
                            ConversationTurn(role="assistant", content=response_text)
                        )
        
        return ConversationHistory(turns=conversation_turns)
    
    def _evaluate_goal_progress(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Evaluate progress toward goal using multi-turn metrics.
        
        Args:
            state: Current test state
            goal: The test goal
            
        Returns:
            GoalProgress with metric-based evaluation
        """
        # Need at least one turn to evaluate
        if not state.turns:
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.0,
                reasoning="No turns executed yet",
            )
        
        # Convert Penelope's conversation to SDK format
        conversation = self._to_conversation_format(state.turns)
        
        # Evaluate using the metric
        result = self.goal_metric.evaluate(
            conversation_history=conversation,
            goal=goal,
            instructions=state.context.instructions,
            context=state.context.context,
        )
        
        # Convert MetricResult to GoalProgress
        details = result.details
        
        # Determine if goal is impossible (if confidence is high and not achieved)
        is_impossible = (
            not details.get("is_successful", False)
            and details.get("confidence", 0.0) > 0.8
            and len(state.turns) >= 5
        )
        
        return GoalProgress(
            goal_achieved=details.get("is_successful", False),
            goal_impossible=is_impossible,
            confidence=details.get("confidence", 0.5),
            reasoning=details.get("reasoning", ""),
            findings=details.get("evidence", []),
        )
```

## Interim Solution: Simple Goal Evaluation

### Problem

Penelope currently needs accurate goal achievement detection **now**, but the full SDK multi-turn metrics will take time to implement properly. We need a bridge solution that:
- ✅ Works immediately (not placeholder heuristics)
- ✅ Uses actual LLM evaluation (not guesswork)
- ✅ Has a clean upgrade path to SDK metrics
- ✅ Requires minimal code (~40 lines)

### Interim Implementation in Penelope

```python
# rhesis/penelope/agent.py (interim solution)

class PenelopeAgent:
    def __init__(
        self,
        model: BaseLLM,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 20,
        timeout_seconds: Optional[float] = None,
        enable_transparency: bool = True,
        verbose: bool = False,
        goal_metric: Optional[BaseMultiTurnMetric] = None,  # For future SDK metrics
    ):
        """
        Initialize Penelope agent.
        
        Args:
            ...
            goal_metric: Optional SDK metric for goal evaluation.
                If None, uses interim LLM-based evaluation until SDK metrics are ready.
        """
        self.model = model
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.enable_transparency = enable_transparency
        self.verbose = verbose
        
        # Use SDK metric if provided, otherwise None (triggers interim evaluation)
        self.goal_metric = goal_metric
        
        self.custom_tools = tools or []
        
        logger.info(f"Initialized PenelopeAgent with {model.get_model_name()}")
    
    def _evaluate_goal_progress(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        Evaluate goal progress.
        
        Uses SDK multi-turn metrics if available (self.goal_metric),
        otherwise uses interim LLM-based evaluation.
        """
        # Need at least some conversation to evaluate
        if not state.turns or len(state.turns) < 2:
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.0,
                reasoning="Insufficient conversation for evaluation",
            )
        
        # === Path 1: Use SDK Metric (when available) ===
        if self.goal_metric:
            return self._evaluate_with_sdk_metric(state, goal)
        
        # === Path 2: Interim Simple LLM Evaluation ===
        return self._evaluate_with_simple_llm(state, goal)
    
    def _evaluate_with_sdk_metric(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """Use SDK multi-turn metric for evaluation."""
        # Convert Penelope's conversation to SDK format
        conversation = self._to_conversation_format(state.turns)
        
        # Evaluate using the metric
        result = self.goal_metric.evaluate(
            conversation_history=conversation,
            goal=goal,
            instructions=state.context.instructions,
            context=state.context.context,
        )
        
        # Convert MetricResult to GoalProgress
        details = result.details
        
        # Determine if goal is impossible
        is_impossible = (
            not details.get("is_successful", False)
            and details.get("confidence", 0.0) > 0.8
            and len(state.turns) >= 5
        )
        
        return GoalProgress(
            goal_achieved=details.get("is_successful", False),
            goal_impossible=is_impossible,
            confidence=details.get("confidence", 0.5),
            reasoning=details.get("reasoning", ""),
            findings=details.get("evidence", []),
        )
    
    def _evaluate_with_simple_llm(
        self,
        state: TestState,
        goal: str,
    ) -> GoalProgress:
        """
        INTERIM: Simple LLM-based goal evaluation.
        
        This is a temporary solution until SDK multi-turn metrics are ready.
        Uses a simple prompt + structured output to evaluate goal achievement.
        """
        # Format conversation for evaluation
        conversation = self._format_conversation_for_eval(state.turns)
        
        # Build evaluation prompt
        prompt = f"""Evaluate if this conversation achieved its stated goal.

GOAL:
{goal}

TEST INSTRUCTIONS:
{state.context.instructions or "None provided"}

CONVERSATION:
{conversation}

Has the goal been achieved? Consider:
- Are all stated criteria met?
- Is there clear evidence in the conversation?
- Are any critical elements missing?

Respond in JSON format:
{{
    "goal_achieved": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "evidence": ["supporting quote 1", "supporting quote 2"]
}}"""
        
        try:
            from pydantic import BaseModel, Field
            
            class SimpleGoalEval(BaseModel):
                goal_achieved: bool
                confidence: float = Field(ge=0.0, le=1.0)
                reasoning: str
                evidence: list[str] = []
            
            # Get structured response from LLM
            response = self.model.generate(prompt, schema=SimpleGoalEval)
            result = SimpleGoalEval(**response)
            
            return GoalProgress(
                goal_achieved=result.goal_achieved,
                goal_impossible=False,
                confidence=result.confidence,
                reasoning=result.reasoning,
                findings=result.evidence,
            )
        
        except Exception as e:
            logger.warning(f"Goal evaluation failed: {e}, using fallback")
            # Fallback to simple heuristic
            successful_turns = sum(
                1 for t in state.turns 
                if t.action_output.get("success", False)
            )
            return GoalProgress(
                goal_achieved=False,
                goal_impossible=False,
                confidence=0.3,
                reasoning=f"Evaluation failed: {e}. Observed {successful_turns} successful turns.",
            )
    
    def _format_conversation_for_eval(self, turns: List[Turn]) -> str:
        """Format Penelope turns as a readable conversation."""
        lines = []
        for turn in turns:
            if turn.action == "send_message_to_target":
                msg = turn.action_params.get("message", "")
                if msg:
                    lines.append(f"USER: {msg}")
                
                if turn.action_output.get("success"):
                    resp = turn.action_output.get("output", {})
                    resp_text = resp.get("response", "") if isinstance(resp, dict) else str(resp)
                    if resp_text:
                        lines.append(f"ASSISTANT: {resp_text}")
        
        return "\n".join(lines)
    
    def _to_conversation_format(self, turns: List[Turn]) -> ConversationHistory:
        """
        Extract actual conversation from Penelope's test turns for SDK metrics.
        
        Penelope's turns use native Pydantic message schemas. This method extracts
        the domain conversation being tested (not the test orchestration messages).
        """
        from rhesis.sdk.metrics.types import ConversationHistory, ConversationTurn
        
        conversation_turns = []
        
        for turn in turns:
            if turn.tool_name == "send_message_to_target":
                message = turn.tool_arguments.get("message", "")
                if message:
                    conversation_turns.append(
                        ConversationTurn(role="user", content=message)
                    )
                
                result = turn.tool_result
                if isinstance(result, dict) and result.get("success"):
                    response = result.get("output", {})
                    response_text = (
                        response.get("response", "") 
                        if isinstance(response, dict) 
                        else str(response)
                    )
                    if response_text:
                        conversation_turns.append(
                            ConversationTurn(role="assistant", content=response_text)
                        )
        
        return ConversationHistory(turns=conversation_turns)
```

### Migration Path

**Phase 1 (Now)**: Interim solution
```python
# Penelope uses simple LLM evaluation
agent = PenelopeAgent(model=model)  # goal_metric=None → uses interim evaluation
result = agent.execute_test(target, instructions, goal)
# ✅ Goals actually detected (not placeholder heuristics)
```

**Phase 2 (When SDK Metrics Ready)**: Automatic upgrade
```python
# SDK metrics are now available
from rhesis.sdk.metrics import GoalAchievementJudge

# Option A: Explicit metric
agent = PenelopeAgent(
    model=model,
    goal_metric=GoalAchievementJudge(model=model)  # Uses SDK metric
)

# Option B: Make SDK metric the default
# In agent.__init__:
#   if goal_metric is None:
#       try:
#           from rhesis.sdk.metrics import GoalAchievementJudge
#           self.goal_metric = GoalAchievementJudge(model=model)
#       except ImportError:
#           self.goal_metric = None  # Falls back to interim

agent = PenelopeAgent(model=model)  # Automatically uses SDK metric
result = agent.execute_test(target, instructions, goal)
# ✅ Same interface, more sophisticated evaluation
```

### Why This Approach Works

1. **Minimal Code**: ~40 lines for interim solution vs. hundreds for replicating all metrics
2. **Actually Evaluates**: Uses LLM to judge goal achievement (not heuristics)
3. **Clean Upgrade**: Just add `goal_metric` parameter when SDK is ready
4. **No Replication**: Doesn't duplicate SDK functionality
5. **Same Interface**: `GoalProgress` remains unchanged
6. **Graceful Fallback**: If evaluation fails, degrades to simple heuristic

### When SDK Metrics Are Ready

The multi-metric orchestration happens **in the SDK**, not Penelope:

```python
# SDK provides comprehensive evaluation
from rhesis.sdk.metrics import evaluate_conversation

sdk_evaluation = evaluate_conversation(
    conversation=conversation_history,
    metrics=['goal_achievement', 'context_retention', 'coherence'],
    goal=goal,
)

# Penelope just needs goal achievement for stopping condition
goal_metric_result = sdk_evaluation.get_metric('goal_achievement')
goal_progress = GoalProgress(
    goal_achieved=goal_metric_result.passed,
    confidence=goal_metric_result.score,
    reasoning=goal_metric_result.reasoning,
    findings=goal_metric_result.evidence,
)

# But test results store the full evaluation
test_result.evaluation = sdk_evaluation  # All metrics preserved for analysis
```

This keeps Penelope focused on **test orchestration** while the SDK handles **evaluation sophistication**.

## Usage Examples

### 1. Penelope with Default Metric

```python
from rhesis.penelope import PenelopeAgent, EndpointTarget
from rhesis.sdk.models import VertexAILLM

agent = PenelopeAgent(model=VertexAILLM())  # Uses default GoalAchievementJudge

result = agent.execute_test(
    target=EndpointTarget(endpoint_id="chatbot-prod"),
    instructions="Test multi-turn conversation",
    goal="Customer receives complete information about products",
)

print(f"Goal achieved: {result.goal_achieved}")  # Now accurate!
```

### 2. Penelope with Custom Metric

```python
from rhesis.sdk.metrics import GoalAchievementJudge

# Custom categories for specific domain
custom_metric = GoalAchievementJudge(
    categories=["failed", "passed", "exceeded_expectations"],
    passing_categories=["passed", "exceeded_expectations"],
    model=model,
)

agent = PenelopeAgent(model=model, goal_metric=custom_metric)
```

### 3. Standalone Conversation Evaluation

```python
from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.models import AnthropicLLM

# Evaluate any conversation
metric = GoalAchievementJudge(model=AnthropicLLM())

conversation = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user", "content": "I need insurance info"},
    {"role": "assistant", "content": "We offer auto, home, and life insurance."},
]

result = metric.evaluate(
    conversation_history=conversation,
    goal="Customer learns about available insurance types",
)

print(result.details["is_successful"])  # True
print(result.details["reasoning"])      # Detailed explanation
print(result.details["evidence"])       # Specific quotes from conversation
```

### 4. Batch Evaluation

```python
import json
from rhesis.sdk.metrics import GoalAchievementJudge

metric = GoalAchievementJudge(model=model)

# Load conversations from logs
with open("conversations.json") as f:
    conversations = json.load(f)

results = []
for conv in conversations:
    result = metric.evaluate(
        conversation_history=conv["messages"],
        goal=conv["goal"],
    )
    results.append({
        "conversation_id": conv["id"],
        "achieved": result.details["is_successful"],
        "confidence": result.details["confidence"],
        "evidence": result.details["evidence"],
    })

# Analyze results
success_rate = sum(r["achieved"] for r in results) / len(results)
print(f"Success rate: {success_rate:.1%}")
```

### 5. Platform Integration

```python
# In Rhesis Platform Backend
from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.metrics.types import ConversationHistory

async def evaluate_test_result(test_result_id: str):
    """Evaluate a completed test's conversation."""
    
    # Get test result from database
    test_result = await db.get_test_result(test_result_id)
    
    # Convert to ConversationHistory
    conversation = ConversationHistory.from_dict_list([
        {"role": turn.role, "content": turn.message}
        for turn in test_result.conversation
    ])
    
    # Evaluate
    metric = GoalAchievementJudge(model=get_default_model())
    result = metric.evaluate(
        conversation_history=conversation,
        goal=test_result.goal,
    )
    
    # Store evaluation
    await db.update_test_result(
        test_result_id,
        goal_achieved=result.details["is_successful"],
        confidence=result.details["confidence"],
        reasoning=result.details["reasoning"],
        evidence=result.details["evidence"],
    )
    
    return result.details
```

## Integrating with Penelope

### Overview

Penelope's integration with SDK multi-turn metrics follows a **bridge pattern**: an interim solution that works immediately, with a clean upgrade path to SDK metrics when they're ready.

### Current Architecture: Interim Solution

#### Phase 1: SimpleGoalEval (Now)

Penelope currently uses an interim schema for goal evaluation:

```python
# rhesis/penelope/schemas.py

class CriterionEvaluation(BaseModel):
    """Evaluation of a single goal criterion."""
    criterion: str = Field(description="The specific criterion being evaluated")
    met: bool = Field(description="Whether this criterion was met")
    evidence: str = Field(description="Specific evidence from the conversation")


class SimpleGoalEval(BaseModel):
    """
    INTERIM: Temporary schema until SDK multi-turn metrics are available.
    
    This provides structured, criterion-by-criterion evaluation that's more
    reliable than holistic judgments. When SDK metrics are ready, this will
    be replaced by SDK schemas, but the interface remains the same.
    """
    turn_count: int = Field(
        description="CRITICAL: Count the actual number of user-assistant exchanges"
    )
    criteria_evaluations: list[CriterionEvaluation] = Field(
        description="Evaluation of each specific criterion mentioned in the goal"
    )
    all_criteria_met: bool = Field(
        description="True only if ALL criteria evaluations have met=True"
    )
    goal_achieved: bool = Field(
        description="Overall assessment: True if all_criteria_met AND no critical issues"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence: list[str] = Field(default_factory=list)
```

#### How It Works

```python
# rhesis/penelope/agent.py

class PenelopeAgent:
    def __init__(self, model, goal_metric=None, ...):
        self.model = model
        self.goal_metric = goal_metric  # Optional SDK metric
    
    def _evaluate_goal_progress(self, state, goal):
        """Route to SDK metric or interim evaluation."""
        if self.goal_metric:
            # Path 1: Use SDK metric (when available)
            return self._evaluate_with_sdk_metric(state, goal)
        else:
            # Path 2: Use interim LLM evaluation
            return self._evaluate_with_simple_llm(state, goal)
    
    def _evaluate_with_simple_llm(self, state, goal):
        """INTERIM: Simple LLM-based evaluation until SDK metrics ready."""
        conversation = self._format_conversation_for_eval(state.turns)
        
        prompt = f"""Evaluate this conversation against the stated goal.

GOAL:
{goal}

CONVERSATION:
{conversation}

INSTRUCTIONS:
1. Count the user-assistant exchanges
2. Break down the goal into specific measurable criteria
3. Evaluate each criterion individually with evidence
4. Determine if ALL criteria are met"""
        
        response = self.model.generate(prompt, schema=SimpleGoalEval)
        result = SimpleGoalEval(**response)
        
        # Convert to GoalProgress (same interface as SDK path)
        findings = []
        for criterion in result.criteria_evaluations:
            status = "MET" if criterion.met else "NOT MET"
            findings.append(f"[{status}] {criterion.criterion}: {criterion.evidence}")
        
        return GoalProgress(
            goal_achieved=result.goal_achieved,
            confidence=result.confidence,
            reasoning=f"Turn count: {result.turn_count}. {result.reasoning}",
            findings=findings,
        )
```

### Future Architecture: SDK Metrics

#### Phase 2: SDK GoalAchievementJudge (When Ready)

```python
# rhesis/sdk/metrics/providers/native/multi_turn.py

class GoalAchievementResponse(BaseModel):
    """SDK's structured response for goal evaluation."""
    achievement_level: str  # "not_achieved" | "partially_achieved" | "fully_achieved"
    confidence: float
    reasoning: str
    evidence: List[str]
    missing_criteria: List[str]


class GoalAchievementJudge(BaseMultiTurnMetric):
    """SDK's production-grade goal achievement metric."""
    
    def evaluate_conversation(self, evaluation_input):
        # SDK manages prompt templates, LLM calls, caching, etc.
        prompt = self._render_template("prompt_multi_turn_goal.jinja", ...)
        response = self.model.generate(prompt, schema=GoalAchievementResponse)
        
        # Return standardized MetricResult
        return MetricResult(
            score=response.achievement_level,
            details={
                "is_successful": response.achievement_level in self.passing_categories,
                "confidence": response.confidence,
                "reasoning": response.reasoning,
                "evidence": response.evidence,
                "missing_criteria": response.missing_criteria,
                # ... more details
            }
        )
```

#### How Penelope Uses SDK Metrics

```python
# rhesis/penelope/agent.py

def _evaluate_with_sdk_metric(self, state, goal):
    """Use SDK multi-turn metric for evaluation."""
    # Convert Penelope's Turn objects to SDK's ConversationHistory
    conversation = self._to_conversation_format(state.turns)
    
    # Call SDK metric
    result = self.goal_metric.evaluate(
        conversation_history=conversation,
        goal=goal,
        test_instructions=state.context.test_instructions,
        context=state.context.context,
    )
    
    # Convert SDK's MetricResult to Penelope's GoalProgress
    details = result.details
    return GoalProgress(
        goal_achieved=details.get("is_successful", False),
        confidence=details.get("confidence", 0.5),
        reasoning=details.get("reasoning", ""),
        findings=details.get("evidence", []),
    )

def _to_conversation_format(self, turns):
    """Convert Penelope Turns to SDK ConversationHistory."""
    from rhesis.sdk.metrics.types import ConversationHistory, ConversationTurn
    
    conversation_turns = []
    for turn in turns:
        if turn.action == "send_message_to_target":
            message = turn.action_input.get("message", "")
            if message:
                conversation_turns.append(
                    ConversationTurn(role="user", content=message)
                )
            
            if turn.action_output.get("success"):
                response = turn.action_output.get("output", {})
                response_text = response.get("response", "")
                if response_text:
                    conversation_turns.append(
                        ConversationTurn(role="assistant", content=response_text)
                    )
    
    return ConversationHistory(turns=conversation_turns)
```

### Migration Path

#### Step 1: Today (Interim Solution)

```python
from rhesis.penelope import PenelopeAgent
from rhesis.sdk.models import VertexAILLM

# No SDK metrics needed - works out of the box
agent = PenelopeAgent(model=VertexAILLM())

result = agent.execute_test(
    target=target,
    instructions="Test chatbot context retention",
    goal="Successfully complete 4-turn conversation with context",
)

# ✅ Uses SimpleGoalEval for evaluation
# ✅ Goal achievement is accurately detected
# ✅ Criterion-by-criterion transparency
```

#### Step 2: SDK Metrics Available

```python
from rhesis.penelope import PenelopeAgent
from rhesis.sdk.models import VertexAILLM
from rhesis.sdk.metrics import GoalAchievementJudge  # NEW!

# Option A: Explicit metric
agent = PenelopeAgent(
    model=VertexAILLM(),
    goal_metric=GoalAchievementJudge(model=VertexAILLM())  # Just add this!
)

# Option B: Default SDK metric (if we make it the default)
agent = PenelopeAgent(model=VertexAILLM())
# Automatically uses SDK metric if available, falls back to interim

result = agent.execute_test(...)

# ✅ Uses SDK GoalAchievementJudge
# ✅ Same interface - no other changes needed
# ✅ More sophisticated evaluation
# ✅ Reusable across Rhesis platform
```

#### Step 3: Deprecation (Optional)

```python
# Option A: Keep SimpleGoalEval as fallback
# Good for users without SDK or for specific use cases

# Option B: Remove SimpleGoalEval entirely
# Requires SDK multi-turn metrics to be installed
# Cleaner codebase, one less maintenance path
```

### Schema Comparison

| Feature | SimpleGoalEval (Interim) | GoalAchievementResponse (SDK) |
|---------|--------------------------|-------------------------------|
| **Location** | `rhesis.penelope.schemas` | `rhesis.sdk.metrics` |
| **Purpose** | Bridge solution for Penelope | Production-grade reusable metric |
| **Turn Counting** | `turn_count: int` | Implicit in conversation analysis |
| **Criterion Breakdown** | `criteria_evaluations: List[CriterionEvaluation]` | Managed internally by SDK |
| **Output** | `goal_achieved: bool` | `achievement_level: str` (categorical) |
| **Evidence** | `evidence: List[str]` | `evidence: List[str]` (same concept) |
| **Missing Info** | Implicit in criterion.met=False | `missing_criteria: List[str]` (explicit) |
| **Reusability** | Penelope-specific | Framework-agnostic |
| **Prompt Management** | F-string in code | Jinja templates |
| **Caching** | No | Yes (SDK feature) |
| **Batch Evaluation** | No | Yes (SDK feature) |

### Key Design Principles

1. **Same Interface**: Both paths return `GoalProgress` with identical fields
2. **Routing Logic**: Single `if self.goal_metric` check handles the switch
3. **No Breaking Changes**: Existing Penelope code continues to work
4. **Opt-in Upgrade**: Users choose when to adopt SDK metrics
5. **Transparent Fallback**: If SDK metrics unavailable, interim solution works

### Why This Approach Works

**For Development:**
- Penelope can be developed and tested independently of SDK metrics
- No blocking dependencies on SDK team
- Faster iteration on Penelope features

**For Users:**
- Works immediately without SDK updates
- Clear upgrade path when SDK is ready
- No forced migration - both paths coexist

**For Maintenance:**
- Single interface (`GoalProgress`) to maintain
- Clear separation of concerns
- Easy to add more metrics in future

**For the Platform:**
- Interim solution proves the concept
- Informs SDK metric design with real usage
- Smooth transition for all users

### What Gets Replaced

When SDK metrics are adopted:

| Component | Status | Notes |
|-----------|--------|-------|
| `SimpleGoalEval` | **Replaced** by SDK schemas | Can be deprecated or removed |
| `CriterionEvaluation` | **Replaced** by SDK internals | No longer needed |
| `_evaluate_with_simple_llm()` | **Replaced** by `goal_metric.evaluate()` | Routing handles this |
| `_format_conversation_for_eval()` | **Replaced** by `_to_conversation_format()` | Different format needed |
| `GoalProgress` | **Unchanged** | Same interface! |
| `_evaluate_goal_progress()` | **Unchanged** | Routing logic stays |
| `_evaluate_with_sdk_metric()` | **Unchanged** | Already implemented |

The beauty: **Most of Penelope's code doesn't change** - just the evaluation path it takes!

## Multi-Metric Architecture: Separation of Concerns

### Design Philosophy

**Problem**: A test might need multiple types of evaluation:
1. **Stopping Decision**: "Should we stop testing?" (goal achieved?)
2. **Quality Assessment**: "How good was the conversation?" (context retention, coherence, safety, etc.)

**Solution**: Separate these concerns with distinct parameters and evaluation timing.

### Architecture Overview

```python
class PenelopeAgent:
    def __init__(
        self,
        model: BaseLLM,
        goal_metric: Optional[BaseMultiTurnMetric] = None,
        evaluation_metrics: Optional[List[BaseMultiTurnMetric]] = None,
        evaluate_during_test: bool = False,
        ...
    ):
        """
        Args:
            goal_metric: SINGULAR metric that determines if goal is achieved.
                This drives the stopping condition. If None, defaults to
                GoalAchievementJudge. Only this metric controls when testing stops.
                
            evaluation_metrics: MULTIPLE metrics for comprehensive quality assessment.
                These evaluate conversation quality but don't affect stopping.
                Examples: ContextRetentionMetric, CoherenceMetric, SafetyMetric.
                
            evaluate_during_test: If True, run evaluation_metrics periodically
                during the test. If False (default), only run at the end for
                efficiency.
        """
        self.goal_metric = goal_metric or GoalAchievementJudge(model)
        self.evaluation_metrics = evaluation_metrics or []
        self.evaluate_during_test = evaluate_during_test
```

### Metric Types and Purposes

#### 1. Goal Metric (Stopping Condition)

**Purpose**: Determines when to stop testing

**Characteristics**:
- **Singular**: Only ONE metric drives stopping
- **Decisive**: Its result directly controls `GoalAchievedCondition`
- **Periodic**: Evaluated every N turns during test execution
- **Question**: "Has the test goal been achieved?"

**Example**:
```python
goal_metric = GoalAchievementJudge(
    categories=["not_achieved", "partially_achieved", "fully_achieved"],
    passing_categories=["fully_achieved"],
    model=model
)
```

#### 2. Evaluation Metrics (Quality Assessment)

**Purpose**: Assess conversation quality across multiple dimensions

**Characteristics**:
- **Plural**: Can have MANY metrics
- **Informative**: Results don't affect stopping, only test results
- **End-of-test**: Typically run after test completion (configurable)
- **Question**: "How good was the conversation?"

**Examples**:
```python
evaluation_metrics = [
    ContextRetentionMetric(model=model, threshold=0.7),
    ConversationCoherenceMetric(model=model, threshold=0.8),
    ToxicityMetric(model=model, max_toxicity=0.1),
    ResponseQualityMetric(model=model),
]
```

### When Metrics Run

#### During Test Execution

```python
def execute_test(self, target, test_instructions, goal, ...):
    """Execute multi-turn test with metric evaluation."""
    
    while not should_stop:
        # Execute one turn
        self._execute_turn(state, tools, goal)
        
        # Evaluate goal progress (for stopping)
        if len(state.turns) >= 2 and len(state.turns) % 2 == 0:
            progress = self._evaluate_goal_progress(state, goal)
            # Uses self.goal_metric
            goal_condition.update_progress(progress)
            
            # Optional: also run evaluation metrics during test
            if self.evaluate_during_test:
                self._run_evaluation_metrics_incremental(state, goal)
        
        # Check all stopping conditions
        should_stop = any(c.should_stop(state) for c in conditions)
    
    # Test complete - run comprehensive evaluation
    final_evaluation = self._run_final_evaluation(state, goal)
    
    return TestResult(
        status=self._determine_status(state, conditions),
        goal_achieved=progress.goal_achieved,  # From goal_metric
        evaluation=final_evaluation,            # From ALL metrics
        turns_used=len(state.turns),
        findings=state.findings,
        history=state.turns,
        ...
    )
```

#### Final Evaluation Method

```python
def _run_final_evaluation(
    self,
    state: TestState,
    goal: str,
) -> Dict[str, MetricResult]:
    """
    Run comprehensive evaluation with all metrics.
    
    Returns:
        Dictionary mapping metric names to their results
    """
    results = {}
    conversation = self._to_conversation_format(state.turns)
    
    # Always include goal achievement metric
    goal_result = self.goal_metric.evaluate(
        conversation_history=conversation,
        goal=goal,
        instructions=state.context.instructions,
        context=state.context.context,
    )
    results['goal_achievement'] = goal_result
    
    # Run all evaluation metrics
    for metric in self.evaluation_metrics:
        try:
            metric_result = metric.evaluate(
                conversation_history=conversation,
                goal=goal,
                instructions=state.context.instructions,
                context=state.context.context,
            )
            results[metric.name] = metric_result
        except Exception as e:
            logger.warning(f"Evaluation metric {metric.name} failed: {e}")
            # Store error but continue with other metrics
            results[metric.name] = MetricResult(
                score="error",
                details={"error": str(e)}
            )
    
    return results
```

### Usage Examples

#### Example 1: Default (Goal Only)

```python
# Simplest case - just goal achievement
agent = PenelopeAgent(model=VertexAILLM())

result = agent.execute_test(
    target=endpoint,
    goal="Complete 4-turn conversation about insurance"
)

# Only goal metric is evaluated
print(f"Goal achieved: {result.goal_achieved}")
print(f"Evaluation: {result.evaluation['goal_achievement'].details}")
```

#### Example 2: Goal + Quality Metrics

```python
from rhesis.sdk.metrics import (
    GoalAchievementJudge,
    ContextRetentionMetric,
    ConversationCoherenceMetric,
    SafetyMetric,
)

agent = PenelopeAgent(
    model=VertexAILLM(),
    
    # Stopping metric
    goal_metric=GoalAchievementJudge(
        passing_categories=["fully_achieved"],
        model=VertexAILLM()
    ),
    
    # Quality metrics (run at end)
    evaluation_metrics=[
        ContextRetentionMetric(model=VertexAILLM(), threshold=0.7),
        ConversationCoherenceMetric(model=VertexAILLM(), threshold=0.8),
        SafetyMetric(model=VertexAILLM()),
    ],
)

result = agent.execute_test(
    target=endpoint,
    goal="Complete 4-turn conversation with context retention"
)

# Stopping decision
print(f"Goal achieved: {result.goal_achieved}")

# Quality assessment
print(f"\nQuality Metrics:")
for metric_name, metric_result in result.evaluation.items():
    if metric_name != 'goal_achievement':
        score = metric_result.score
        passed = metric_result.details.get('is_successful', 'N/A')
        print(f"  {metric_name}: {score} (passed: {passed})")

# Overall quality check
quality_metrics = [r for n, r in result.evaluation.items() if n != 'goal_achievement']
all_passed = all(m.details.get('is_successful', False) for m in quality_metrics)
print(f"\nAll quality metrics passed: {all_passed}")
```

#### Example 3: Real-time Monitoring

```python
# Evaluate metrics during test for real-time monitoring
agent = PenelopeAgent(
    model=model,
    goal_metric=GoalAchievementJudge(model=model),
    evaluation_metrics=[
        ContextRetentionMetric(model=model),
        ToxicityMetric(model=model),  # Monitor for safety issues
    ],
    evaluate_during_test=True,  # Run during test
)

result = agent.execute_test(...)

# Can see metric progression over time
# (stored in state.metrics_history)
```

### TestResult Schema Update

```python
class TestResult(BaseModel):
    """Result of a test execution."""
    
    status: TestStatus
    goal_achieved: bool  # From goal_metric
    turns_used: int
    findings: List[str]
    history: List[Turn]
    metadata: Dict[str, Any]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    
    # NEW: Comprehensive evaluation results
    evaluation: Dict[str, MetricResult] = Field(
        default_factory=dict,
        description="Results from goal_metric and all evaluation_metrics"
    )
    
    def get_metric_result(self, metric_name: str) -> Optional[MetricResult]:
        """Get result for a specific metric."""
        return self.evaluation.get(metric_name)
    
    def get_quality_score(self) -> float:
        """
        Calculate overall quality score from evaluation metrics.
        Excludes goal_achievement (stopping metric).
        """
        quality_metrics = [
            result for name, result in self.evaluation.items()
            if name != 'goal_achievement'
        ]
        if not quality_metrics:
            return 1.0
        
        # Average confidence/score across quality metrics
        scores = [
            result.details.get('confidence', 0.5)
            for result in quality_metrics
        ]
        return sum(scores) / len(scores)
    
    def all_metrics_passed(self) -> bool:
        """Check if all metrics (goal + quality) passed."""
        return all(
            result.details.get('is_successful', False)
            for result in self.evaluation.values()
        )
```

### Benefits of This Design

#### 1. Clear Separation of Concerns
- **Goal metric**: Controls test execution (when to stop)
- **Evaluation metrics**: Assess quality (how good it was)
- No confusion about which metric does what

#### 2. Efficient Resource Usage
- Only run goal metric during test (lightweight, frequent)
- Run evaluation metrics at end (comprehensive, once)
- Option to monitor critical metrics during test

#### 3. Flexible Composition
```python
# Security-focused test
agent = PenelopeAgent(
    model=model,
    goal_metric=GoalAchievementJudge(model),
    evaluation_metrics=[
        ToxicityMetric(model),
        PromptInjectionMetric(model),
        DataLeakageMetric(model),
    ]
)

# Quality-focused test
agent = PenelopeAgent(
    model=model,
    goal_metric=GoalAchievementJudge(model),
    evaluation_metrics=[
        ContextRetentionMetric(model),
        CoherenceMetric(model),
        ResponseQualityMetric(model),
        TurnEfficiencyMetric(model),
    ]
)
```

#### 4. Backward Compatible
```python
# Old way (still works)
agent = PenelopeAgent(model=model)  # Uses default goal metric

# New way (when you need it)
agent = PenelopeAgent(
    model=model,
    evaluation_metrics=[...]  # Add quality metrics
)
```

#### 5. Platform Integration
```python
# Platform can run comprehensive evaluations
from rhesis.sdk.metrics import evaluate_test_result

# Evaluate stored test results with multiple metrics
comprehensive_eval = evaluate_test_result(
    test_result_id="test-123",
    metrics=[
        GoalAchievementJudge(model),
        ContextRetentionMetric(model),
        CoherenceMetric(model),
        SafetyMetric(model),
    ]
)

# Store evaluation in database
await db.store_evaluation(test_result_id, comprehensive_eval)
```

### Implementation Phases

This multi-metric architecture will be implemented in phases:

#### Phase 1 (Current): Single Goal Metric
- ✅ `goal_metric` parameter in `PenelopeAgent`
- ✅ Drives stopping condition
- ✅ Interim `SimpleGoalEval` or SDK `GoalAchievementJudge`

#### Phase 2 (Future): Multiple Evaluation Metrics
- [ ] Add `evaluation_metrics` parameter
- [ ] Implement `_run_final_evaluation()`
- [ ] Update `TestResult` with `evaluation` field
- [ ] Add helper methods (`get_quality_score()`, etc.)

#### Phase 3 (Future): Real-time Monitoring
- [ ] Add `evaluate_during_test` parameter
- [ ] Implement `_run_evaluation_metrics_incremental()`
- [ ] Store metrics history in `TestState`
- [ ] Add visualization/logging for metric trends

### Design Considerations

**Why not make evaluation_metrics affect stopping?**
- **Clarity**: One source of truth for stopping decisions
- **Performance**: Don't want expensive quality metrics slowing down test execution
- **Flexibility**: Can add/remove quality metrics without changing test behavior
- **Debugging**: Easy to identify why test stopped

**When to run evaluation metrics during test?**
- **Safety-critical**: Run `ToxicityMetric` during test to catch issues early
- **Monitoring**: Track `ContextRetentionMetric` to see degradation over time
- **Default**: Run at end for efficiency

**How to handle metric failures?**
- **Goal metric fails**: Test continues, uses fallback heuristics
- **Evaluation metric fails**: Log warning, continue with other metrics
- **Neither blocks test**: Robust execution

## Implementation Plan

### Phase 1: SDK Foundation (Priority 1)
- [ ] Add `ConversationTurn`, `ConversationHistory`, `MultiTurnEvaluationInput` to SDK types
- [ ] Implement `BaseMultiTurnMetric` in SDK
- [ ] Add `ConversationType` enum

### Phase 2: Goal Achievement Metric (Priority 1)
- [ ] Implement `GoalAchievementJudge` with full Pydantic schemas
- [ ] Create evaluation prompt template
- [ ] Add unit tests for the metric
- [ ] Add integration tests with real LLMs

### Phase 3: Penelope Integration (Priority 1)
- [ ] Add `goal_metric` parameter to `PenelopeAgent.__init__()`
- [ ] Implement `_to_conversation_format()` converter
- [ ] Update `_evaluate_goal_progress()` to use metrics
- [ ] Update stopping conditions to properly detect goal achievement
- [ ] Test with existing Penelope test suite

### Phase 4: Additional Metrics (Priority 2)
- [ ] Implement `ContextRetentionMetric`
- [ ] Implement `ConversationCoherenceMetric`
- [ ] Add metric factory for multi-turn metrics

### Phase 5: Documentation & Examples (Priority 2)
- [ ] Add SDK documentation for multi-turn metrics
- [ ] Add Penelope examples using custom metrics
- [ ] Update platform documentation
- [ ] Create integration guides for LangChain, CrewAI, etc.

### Phase 6: Platform Integration (Priority 3)
- [ ] Add API endpoints for conversation evaluation
- [ ] Integrate with test result storage
- [ ] Add UI for viewing evaluation results
- [ ] Add batch evaluation capabilities

## Benefits

### For Penelope
✅ Accurate goal achievement detection  
✅ Sophisticated conversation analysis  
✅ Configurable evaluation criteria  
✅ Transparent reasoning for decisions  

### For SDK Users
✅ Framework-agnostic conversation evaluation  
✅ Reusable across any conversation system  
✅ Pydantic-based type safety  
✅ Consistent with existing metrics API  

### For Rhesis Platform
✅ Automated test evaluation  
✅ Conversation quality analytics  
✅ Historical trend analysis  
✅ API for third-party integrations  

## Open Questions

1. **Metric Composition**: Should we support combining multiple metrics (e.g., goal achievement + context retention)?
2. **Streaming Evaluation**: Should metrics support streaming conversations (evaluate after each turn)?
3. **Caching**: Should we cache LLM evaluations for identical conversations?
4. **Custom Prompts**: Should users be able to override evaluation prompts?
5. **Async Support**: Should metrics support async evaluation for better performance?

## Future Enhancements

- **Metric Chains**: Compose multiple metrics for comprehensive evaluation
- **Streaming Support**: Evaluate conversations as they happen
- **Custom Evaluators**: Allow users to define custom evaluation logic
- **Metric Aggregation**: Combine scores from multiple metrics
- **Time-based Metrics**: Evaluate conversation efficiency/speed
- **Sentiment Analysis**: Track sentiment changes across conversation
- **Topic Tracking**: Analyze topic coherence and transitions

## Native Message Format: Architecture Details

### Why Native Format Matters

Penelope's native Pydantic message schemas provide several architectural advantages:

#### 1. **Zero Conversion Overhead**

```python
# Direct access to message fields (no dict parsing)
for turn in result.history:
    print(turn.assistant_message.role)          # Type-safe access
    print(turn.assistant_message.content)       # IDE autocomplete
    print(turn.assistant_message.tool_calls)    # Full validation
```

#### 2. **Provider Agnostic**

The same native format works with all major LLM providers:

```python
# OpenAI API
openai_messages = [msg.model_dump(exclude_none=True) for turn in result.history 
                   for msg in [turn.assistant_message, turn.tool_message]]

# Anthropic API (same format!)
anthropic_messages = [msg.model_dump(exclude_none=True) for turn in result.history 
                      for msg in [turn.assistant_message, turn.tool_message]]

# Vertex AI (same format!)
vertex_messages = [msg.model_dump(exclude_none=True) for turn in result.history 
                   for msg in [turn.assistant_message, turn.tool_message]]
```

#### 3. **Type Safety Throughout**

```python
from rhesis.penelope.schemas import AssistantMessage, ToolMessage

def process_turn(turn: Turn):
    # Full type checking and IDE support
    assistant: AssistantMessage = turn.assistant_message
    tool: ToolMessage = turn.tool_message
    
    # No runtime type errors
    if assistant.tool_calls:
        func_name = assistant.tool_calls[0].function.name  # Type-safe!
```

#### 4. **No Format Conversions in Penelope**

```python
# ❌ OLD APPROACH (other frameworks):
# Store as dicts → convert to objects → convert back to dicts → validate

# ✅ PENELOPE APPROACH:
# Store as Pydantic objects → use directly → convert only when needed
```

### Message Schema Location

All message schemas are centralized in `rhesis.penelope.schemas`:

```python
from rhesis.penelope.schemas import (
    AssistantMessage,      # Assistant message with tool calls
    ToolMessage,           # Tool response message
    FunctionCall,          # Function specification
    MessageToolCall,       # Tool call specification
)
```

### Comparison: Penelope vs Other Frameworks

| Aspect | Penelope | LangChain | CrewAI |
|--------|----------|-----------|---------|
| **Message Storage** | Native Pydantic | Dict-based | Custom objects |
| **Type Safety** | Full (Pydantic) | Partial | Varies |
| **Conversion Needed** | No | Yes (dict ↔ object) | Yes |
| **Provider Support** | All (via standard format) | OpenAI-focused | OpenAI-focused |
| **Performance** | Zero overhead | Conversion overhead | Conversion overhead |
| **IDE Support** | Full autocomplete | Limited | Limited |

### Integration with SDK Metrics

When SDK metrics are ready, they receive the actual conversation content (not Penelope's test orchestration):

```python
# Penelope's native format
turn.assistant_message  # AssistantMessage (test orchestration)
turn.tool_message       # ToolMessage (test results)

# SDK metrics receive the domain conversation
conversation = _to_conversation_format(turns)
# → ConversationTurn(role="user", content="What insurance do you offer?")
# → ConversationTurn(role="assistant", content="We offer auto, home, life...")

# Note: This is content extraction, NOT format conversion!
```

### Future Extensibility

The native Pydantic approach makes it easy to extend:

```python
# Add new message types
class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str

# Add provider-specific extensions
class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[MessageToolCall]] = None
    
    # Provider-specific fields via Config
    class Config:
        extra = "allow"  # Allows provider extensions
```

## References

- Existing SDK Metrics: `rhesis/sdk/src/rhesis/sdk/metrics/`
- Penelope Agent: `rhesis/penelope/src/rhesis/penelope/agent.py`
- Penelope Schemas: `rhesis/penelope/src/rhesis/penelope/schemas.py`
- Penelope Context: `rhesis/penelope/src/rhesis/penelope/context.py`
- Anthropic's Agent Design Principles

