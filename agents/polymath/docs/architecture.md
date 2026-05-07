# Polymath Multi-Agent Architecture

Polymath is a three-agent system built on **Microsoft Agent Framework (MAF)** using `HandoffBuilder` in autonomous mode. Its sole purpose is to exercise the Rhesis SDK's `auto_instrument("agent_framework")` integration end-to-end.

## Agent Overview

```mermaid
flowchart TB
    subgraph User["User"]
        Query[User Query]
    end

    subgraph Coordinator["COORDINATOR"]
        C[Routes & synthesises<br/>final answer]
    end

    subgraph Specialists["Specialist Agents"]
        subgraph Math["MATH SPECIALIST"]
            M_Tools["Tools:<br/>- add<br/>- multiply<br/>- power<br/>- square_root"]
        end

        subgraph Info["INFO SPECIALIST"]
            I_Tools["Tools:<br/>- get_current_time HTTP<br/>- wikipedia_summary HTTP"]
        end
    end

    Query --> C
    C -->|"handoff_to_math_specialist"| Math
    C -->|"handoff_to_info_specialist"| Info

    Math -->|"handoff_to_coordinator"| C
    Info -->|"handoff_to_coordinator"| C

    C -->|Response| Query
```

## Handoff Topology

```mermaid
flowchart LR
    Coord((Coordinator))
    Math((Math))
    Info((Info))

    Coord ==>|routes| Math
    Coord ==>|routes| Info
    Math -->|return| Coord
    Info -->|return| Coord
```

## Tool Layers

```mermaid
flowchart TB
    subgraph Local["Local Python Tools"]
        L1[add]
        L2[multiply]
        L3[power]
        L4[square_root]
    end

    subgraph Network["HTTP Tools"]
        N1["get_current_time<br/>worldtimeapi.org"]
        N2["wikipedia_summary<br/>wikipedia REST"]
    end

    Math --> Local
    Info --> Network
```

## Example Workflow: Mixed Query

```mermaid
sequenceDiagram
    participant U as User
    participant C as Coordinator
    participant M as Math Specialist
    participant I as Info Specialist

    U->>C: "What is 17 squared, and what time is it in Berlin?"
    C->>C: Plan handoffs
    C->>M: handoff_to_math_specialist
    M->>M: power(17, 2) -> 289
    M->>C: handoff_to_coordinator
    C->>I: handoff_to_info_specialist
    I->>I: get_current_time("Europe/Berlin")
    I->>C: handoff_to_coordinator
    C-->>U: "17 squared is 289, and the time in Berlin is 14:32 CEST."
```

## Trace Surface Generated

A single user query produces (per the SDK's [MAF translator](../../../sdk/src/rhesis/sdk/telemetry/integrations/agent_framework/mapping.py)):

| Rhesis span name | Source MAF operation |
|---|---|
| `function.workflow.run` | `workflow.run` |
| `function.workflow.executor.process` | `executor.process` |
| `function.workflow.edge_group.process` | `edge_group.process` |
| `ai.agent.invoke` | `invoke_agent` (one per agent activation) |
| `ai.llm.invoke` | `chat` (one per chat completion) |
| `ai.tool.invoke` (with `ai.tool.input` / `ai.tool.output` events) | `execute_tool` |

A "mixed" query that touches both specialists typically generates 1 workflow root span, ~6-10 executor spans, 4-6 agent-invoke spans, 4-6 LLM spans, and 2-4 tool-invoke spans. That's enough to make the Rhesis trace UI light up while staying easy to reason about.

## Agent Capabilities Summary

| Agent | Tools | Can Hand Off To |
|-------|-------|-----------------|
| **Coordinator** | (handoff tools auto-injected) | Math Specialist, Info Specialist |
| **Math Specialist** | `add`, `multiply`, `power`, `square_root` | Coordinator |
| **Info Specialist** | `get_current_time`, `wikipedia_summary` | Coordinator |
