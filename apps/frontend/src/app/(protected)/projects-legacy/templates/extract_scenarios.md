You are an AI testing and evaluation expert analyzing the codebase of a generative AI or AI agent application. Your goal is to perform a comprehensive analysis to extract scenario metadata by examining user-facing functionality.

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

#### Extract Scenarios
Based on system goals, agent capabilities, and requirements:

**Edge Cases & Invalid Inputs**
- What challenges system-level goals?
- How do edge cases affect multiple agents?
- What system-wide failure modes exist?
- How are cross-agent issues handled?

**Complex Interactions**
- What multi-agent conversations might occur?
- How is context maintained across agent handoffs?
- What clarifications might each agent need?
- How do agent combinations affect user experience?

**Guided Behavior Situations**
- When do agents need to collaborate for guidance?
- How is uncertainty handled across agents?
- What follow-up scenarios involve multiple agents?
- How are error recoveries coordinated?

Aim to identify at least 5-10 distinct scenarios covering single and multi-agent interactions.

### Output Format:
```json
{
  "scenarios": [
    {
      "name": "Scenario Name", 
      "description": "Context or situation the AI handles"
    }
  ]
}
```

---
### Code Base:
{codebase}
---

### Output:
