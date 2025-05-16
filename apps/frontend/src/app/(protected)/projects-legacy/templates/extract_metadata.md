You are an AI testing and evaluation expert analyzing the codebase of a generative AI or AI agent application. Your goal is to perform a comprehensive analysis to extract testing metadata by examining user-facing functionality.

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

#### Step 0: Analyze System Overview
First, understand the overall AI application by examining:
- What is the system's main purpose?
- What are its primary goals?
- What key capabilities does it offer?
- What architectural patterns are used?
- How are different components connected?

Use this system-level understanding to guide the rest of the analysis.

#### Step 1: Extract Agents
Using the system overview as context, identify all distinct AI agents:

**1. Search for Agent Definitions:**
- Look for agents that fulfill the system's key capabilities
- Identify how agents are organized to meet system goals
- Map agent relationships within the system architecture
- Look for agent-related classes/functions (Agent, AgentFactory, BaseAgent)
- Convert agent names from code format to readable format (e.g., "Supervisor_Agent" becomes "Supervisor Agent")

**2. Analyze Agent Behaviors:**
- How does each agent contribute to system goals?
- What system capabilities does each agent support?
- How do agents work together in the architecture?
- Review configuration settings that define agent behavior

**3. For Each Agent Found, Document:**
- How does it align with system goals?
- What system capabilities does it implement?
- How does it fit in the overall architecture?
- What system prompts define its behavior?

**4. Pay Special Attention To:**
- How agents collectively achieve system goals
- Division of responsibilities across agents
- Integration points between agents
- System-level orchestration patterns

#### Step 2: Extract Requirements
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

Aim to identify at least 5 distinct requirements across all agents.

#### Step 3: Extract Scenarios
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

Aim to identify at least 15-20 distinct scenarios covering single and multi-agent interactions.

#### Step 4: Extract Personas
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

Aim to identify 5-8 distinct personas that represent your user base across all agents.

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
  },
  "agents": [
    {
      "name": "Agent Name",
      "description": "Primary purpose and capabilities of the agent",
      "responsibilities": [
        "Key task or responsibility 1",
        "Key task or responsibility 2"
      ]
    }
  ],
  "requirements": [
    {
      "name": "Requirement Name",
      "description": "What the AI can do"
    }
  ],
  "scenarios": [
    {
      "name": "Scenario Name", 
      "description": "Context or situation the AI handles"
    }
  ],
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
