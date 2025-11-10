# MCP Agents

This directory contains all MCP agent implementations.

## Structure

```
agents/
├── __init__.py           # Exports all agents
├── base_agent.py         # MCPAgent - General-purpose agent
├── search_agent.py       # MCPSearchAgent - Specialized for searching
└── extract_agent.py      # MCPExtractAgent - Specialized for extraction
```

## Agents

### MCPAgent (base_agent.py)
General-purpose autonomous agent for any task.

**Usage:**
```python
from rhesis.sdk.services.mcp import MCPAgent

agent = MCPAgent(llm, mcp_client)
result = agent.run("Find and summarize the PRD")
```

**Returns:** `AgentResult` with text answer

### MCPSearchAgent (search_agent.py)
Specialized agent for searching and listing pages.

**Usage:**
```python
from rhesis.sdk.services.mcp import MCPSearchAgent

agent = MCPSearchAgent(llm, mcp_client)
result = agent.run("Find PRD documents")
```

**Returns:** `SearchResult` with structured `PageMetadata` list

### MCPExtractAgent (extract_agent.py)
Specialized agent for extracting full content from pages.

**Usage:**
```python
from rhesis.sdk.services.mcp import MCPExtractAgent

agent = MCPExtractAgent(llm, mcp_client)
result = agent.run(page_ids=["id1", "id2"])
```

**Returns:** `ExtractionResult` with full content as markdown/text

## Adding New Agents

To add a new specialized agent:

1. Create a new file in this directory (e.g., `summarize_agent.py`)
2. Implement your agent class
3. Export it in `__init__.py`
4. Export it in the parent `mcp/__init__.py`

Example:
```python
# agents/summarize_agent.py
class MCPSummarizeAgent:
    def __init__(self, llm, mcp_client):
        # ...

    def run(self, page_ids: List[str]) -> SummarizeResult:
        # ...

# agents/__init__.py
from rhesis.sdk.services.mcp.agents.summarize_agent import MCPSummarizeAgent

__all__ = [..., "MCPSummarizeAgent"]
```
