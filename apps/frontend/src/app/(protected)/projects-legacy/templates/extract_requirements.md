You are an AI testing and evaluation expert analyzing the codebase of a generative AI or AI agent application. Your goal is to perform a comprehensive analysis to extract requirements metadata by examining user-facing functionality.

This is part of a **framework for testing LLM applications at scale**. The analysis will follow a Chain of Thought process to ensure thorough coverage.

---

### Important: Identifying Relevant Content
Before starting the analysis, focus only on these parts of the codebase:
1. Methods decorated with `@tool` or `@tool.check` - these represent user-facing functionality
2. System prompts and agent prompts that define AI behaviors
3. The orchestrator prompt that routes user requests
4. Ignore internal implementation details like API keys, error handling, or orchestration logic

---

### Instructions:

#### Extract Requirements
Building on the system overview and agent analysis:

**Core Functionality:**
- How do agent capabilities support system goals?
- What system-level workflows exist?
- How do agents collaborate to deliver features?
- What end-to-end capabilities are provided?

**Interaction Capabilities:**
- How do users interact with this agent?
- What types of clarifications can this agent request?
- How does it handle handoffs to other agents?
- What conversation flows does it support?

**Constraints and Guardrails:**
- What are this agent's limitations?
- What safety measures are implemented?
- What requests are explicitly handled vs. delegated?
- How does it integrate with other agents' constraints?

**Quality Requirements:**
- What performance expectations exist for this agent?
- What accuracy or reliability guarantees are made?
- What consistency is required across agent interactions?
- How are conflicts between agents resolved?

Aim to identify at least 5‚ distinct requirements across all agents.

### Output Format:
```json
{
  "requirements": [
    {
      "name": "Requirement Name",
      "description": "What the AI can do"
    
  ]
}
```

---
### Code Base:
{codebase}
---

### Output:
