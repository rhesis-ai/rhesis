You are an AI testing and evaluation expert analyzing the codebase of a generative AI or AI agent application. Your goal is to perform a comprehensive analysis to extract persona metadata by examining user-facing functionality.

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

#### Extract Personas
Considering system purpose, agents, requirements, and scenarios:

**User Characteristics:**
- Who are the target users of the system?
- What system capabilities do they need?
- How do they engage with multiple agents?
- What expertise matches system complexity?

**Usage Patterns:**
- How do users navigate between agents?
- Which agent combinations are most frequent?
- What complexity of multi-agent tasks are attempted?
- How do usage patterns vary by expertise level?

**Expectations:**
- What response quality is expected from each agent?
- How do users perceive agent handoffs?
- What prior experience affects agent preferences?
- How do users understand agent limitations?

Aim to identify at least 5 distinct personas that represent your user base across all agents.

### Output Format:
```json
{
  "personas": [
    {
      "name": "Persona Name",
      "description": "User archetype characteristics"
    }
  ]
}
```

---
### Code Base:
{codebase}
---

### Output:
