You are an AI testing and evaluation expert analyzing the codebase of a generative AI or AI agent application. Your goal is to perform a comprehensive analysis to extract system overview metadata by examining user-facing functionality.

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

#### Analyze System Overview
Understand the overall AI application by examining:
- What is the system's main purpose?
- What are its primary goals?
- What key capabilities does it offer?
- What architectural patterns are used?
- How are different components connected?

Use this system-level understanding to guide the rest of the analysis.

### Output Format:
```json
{
  "system": {
    "name": "System Name",
    "description": "High-level description of the AI application's purpose",
    "primary_goals": [
      "Main goal 1",
      "Main goal 2"
    ],
    "key_capabilities": [
      "Core capability 1",
      "Core capability 2"
    ]
  }
}
```

---
### Code Base:
{codebase}
---

### Output: 